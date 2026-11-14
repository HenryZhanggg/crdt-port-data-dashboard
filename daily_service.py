"""Small, separately cached official sources for the everyday port overview."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import math
from time import monotonic
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
import pandas as pd
import requests
import streamlit as st

from api_connectors import fetch_liverpool_tide_water_levels, request_session
from workspace_data import clean_water_series


WEATHER_URL = 'https://api.met.no/weatherapi/locationforecast/2.0/compact?lat=53.448&lon=-3.015'
WEATHER_SOURCE = 'https://api.met.no/weatherapi/locationforecast/2.0/documentation'
WARNINGS_URL = 'https://weather.metoffice.gov.uk/public/data/PWSCache/WarningsRSS/Region/nw'
WARNINGS_SOURCE = 'https://weather.metoffice.gov.uk/warnings-and-advice/uk-warnings'
FLOODS_URL = 'https://environment.data.gov.uk/flood-monitoring/id/floods?min-severity=3&lat=53.448&long=-3.015&dist=30'
TIDE_SOURCE = 'https://environment.data.gov.uk/flood-monitoring/doc/reference'
PORT_SOURCE = 'https://www.peelports.com/marine/our-ports/liverpool/'
NEWS_SOURCE = 'https://www.peelports.com/news-articles/'
TRAFFIC_SOURCE = 'https://nationalhighways.co.uk/roads-and-travel/live-travel-updates/'
HEADERS = {'User-Agent':'CRDT-Port-Dashboard/1.0 (https://github.com/HenryZhanggg/crdt-port-data-dashboard)'}


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _section(name, url, status='available', message=''):
    return {'status':status, 'source_name':name, 'source_url':url, 'checked_at':None,
            'message':message, 'items':[]}


def _time(value):
    if not value:
        return None
    try:
        instant = datetime.fromisoformat(str(value).replace('Z','+00:00'))
    except ValueError:
        try:
            instant = parsedate_to_datetime(str(value))
        except (ValueError, TypeError):
            return None
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return instant.astimezone(timezone.utc).isoformat()


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (ValueError, TypeError):
        return None
    return value if math.isfinite(value) else None


def _safe_url(value, source):
    value = urljoin(source, str(value or ''))
    parsed = urlparse(value)
    host = parsed.hostname or ''
    trusted = ('metoffice.gov.uk','environment.data.gov.uk','peelports.com','nationalhighways.co.uk')
    if parsed.scheme in ('http','https') and any(host == domain or host.endswith('.'+domain) for domain in trusted):
        return value.replace('http://','https://',1)
    return source


def _download(url):
    response = requests.get(url, headers=HEADERS, timeout=(3.05, 10))
    response.raise_for_status()
    return response


class _TideRequests:
    """Keep the existing gauge adapter within the overview's request budget."""
    def __init__(self, session):
        self.session = session
        self.deadline = monotonic()+20

    def get(self, url, **kwargs):
        remaining = self.deadline-monotonic()
        if remaining <= 0:
            raise requests.Timeout('Tide request budget exhausted')
        kwargs['timeout'] = (min(3.05,remaining),min(8,remaining))
        return self.session.get(url,**kwargs)


def _description(code):
    code = str(code or '').split('_')[0]
    for token, label in [('thunder','Thunder showers'),('snow','Snow'),('sleet','Sleet'),
        ('rainshowers','Rain showers'),('heavyrain','Heavy rain'),('lightrain','Light rain'),
        ('rain','Rain'),('partlycloudy','Partly cloudy'),('cloudy','Cloudy'),
        ('clearsky','Clear sky'),('fair','Fair'),('fog','Fog')]:
        if token in code:
            return label
    return 'Forecast'


def parse_weather(payload, now=None):
    now = now or datetime.now(timezone.utc)
    now = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc)
    properties = payload.get('properties', {})
    meta = properties.get('meta', {})
    for field, unit in [('air_temperature','celsius'),('wind_speed','m/s')]:
        actual = meta.get('units', {}).get(field)
        if actual is not None and actual != unit:
            raise ValueError('Unexpected weather unit')
    rows = []
    for point in properties.get('timeseries', []):
        valid = _time(point.get('time'))
        if valid is None or not now <= datetime.fromisoformat(valid) <= now+timedelta(hours=48):
            continue
        data = point.get('data', {})
        instant = data.get('instant', {}).get('details', {})
        next_hour = data.get('next_1_hours', {})
        rows.append({'time':valid, 'temp_c':_number(instant.get('air_temperature')),
            'wind_m_s':_number(instant.get('wind_speed')),
            'rain_mm':_number(next_hour.get('details', {}).get('precipitation_amount')),
            'description':_description(next_hour.get('summary', {}).get('symbol_code'))})
    if not rows:
        raise ValueError('No upcoming forecast points')
    return {**_section('MET Norway',WEATHER_SOURCE, message='Model forecast for the Liverpool location; not a measured weather observation.'),
        'rows':sorted(rows,key=lambda row:row['time']), 'updated_at':_time(meta.get('updated_at')),
        'forecast_only':True, 'attribution':'Weather forecast: MET Norway, CC BY 4.0; selected variables and readable descriptions.',
        'license_url':'https://creativecommons.org/licenses/by/4.0/'}


def _child_text(element, name):
    return next((child.text or '' for child in element if child.tag.split('}')[-1] == name), '')


def parse_warning_feed(xml):
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise ValueError('Invalid warning feed') from exc
    kind = root.tag.split('}')[-1]
    if kind == 'rss':
        channel = root.find('channel')
        if channel is None:
            raise ValueError('Missing warning channel')
        entries = channel.findall('item')
        updated = _time(_child_text(channel,'pubDate'))
    elif kind == 'feed':
        entries = [item for item in root if item.tag.split('}')[-1]=='entry']
        updated = _time(_child_text(root,'updated'))
    else:
        raise ValueError('Not a warning feed')
    items = []
    for entry in entries:
        title = _child_text(entry,'title').strip()
        if not title:
            continue
        link = _child_text(entry,'link')
        if not link:
            link = next((item.get('href','') for item in entry if item.tag.split('}')[-1]=='link' and item.get('rel','alternate')=='alternate'), '')
        items.append({'id':_child_text(entry,'guid') or _child_text(entry,'id') or title,
            'title':title, 'url':_safe_url(link,WARNINGS_SOURCE),
            'description':BeautifulSoup(_child_text(entry,'description') or _child_text(entry,'summary'),'html.parser').get_text(' ',strip=True)[:600],
            'published_at':_time(_child_text(entry,'pubDate') or _child_text(entry,'published') or _child_text(entry,'updated')),
            'valid_from':_time(_child_text(entry,'onset') or _child_text(entry,'effective')),
            'valid_to':_time(_child_text(entry,'expires')), 'area':'North West England',
            'status':_child_text(entry,'status') or 'Check validity in original',
            'severity':_child_text(entry,'severity') or _child_text(entry,'category') or None})
    return {**_section('Met Office',WARNINGS_SOURCE,
        message='Regional feed for North West England. Empty results are not an all-clear statement; check the official page.'),
        'items':items, 'feed_updated_at':updated}


def parse_flood_warnings(payload):
    if not isinstance(payload.get('items'), list):
        raise ValueError('Missing flood warnings list')
    items = []
    for item in payload['items']:
        area = item.get('floodArea', {})
        area = area if isinstance(area, dict) else {}
        items.append({'id':str(item.get('floodAreaID','')), 'title':str(item.get('description','Flood warning area')),
            'url':_safe_url(item.get('@id') or area.get('@id'),TIDE_SOURCE),
            'description':str(item.get('message','')), 'published_at':_time(item.get('timeRaised')),
            'updated_at':_time(item.get('timeMessageChanged') or item.get('timeSeverityChanged')),
            'valid_from':None, 'valid_to':None, 'area':str(item.get('description','Liverpool area search')),
            'status':str(item.get('severity','Official warning')), 'severity':item.get('severity'),
            'severity_level':item.get('severityLevel')})
    return {**_section('Environment Agency',FLOODS_URL,
        message='Warnings returned for an approximately 30 km search around Liverpool; not confirmed impacts on individual assets.'),
        'items':items, 'feed_updated_at':_time(payload.get('meta',{}).get('dateTime'))}


def normalise_tide(frame):
    if frame.empty:
        return []
    frame = frame.copy()
    for field in ('station_reference','unit','datum','datum_uri'):
        frame[field] = frame.get(field,pd.Series('',index=frame.index)).fillna('').astype(str)
    frame['date_time'] = pd.to_datetime(frame.get('date_time'), utc=True, errors='coerce')
    frame = frame.dropna(subset=['date_time'])
    series = []
    for (station,unit,datum,datum_uri), rows in frame.groupby(['station_reference','unit','datum','datum_uri'],dropna=False):
        rows = clean_water_series(rows)
        first = rows.iloc[0]
        series.append({'id':f'water:{station}|{unit}|{datum_uri}',
            'name':str(first.get('station_label','Liverpool'))+' · '+station+' · '+(datum or 'Unknown reference'),
            'lat':_number(first.get('lat')), 'lon':_number(first.get('lon')), 'unit':unit,
            'datum':datum or 'Unknown datum', 'datum_uri':datum_uri,
            'source_url':str(first.get('api_endpoint',TIDE_SOURCE)),
            'rows':[{'time':row['date_time'].isoformat(),'value':_number(row.get('value')),
                     'duplicate_conflict':bool(row.get('duplicate_conflict',False))} for _,row in rows.iterrows()]})
    return series


def parse_port_news(html):
    soup = BeautifulSoup(html,'html.parser')
    items, seen = [], set()
    for link in soup.select('a[href]'):
        title = link.find('h5')
        url = _safe_url(link.get('href'),NEWS_SOURCE)
        parsed = urlparse(url)
        if (title is None or parsed.hostname not in ('peelports.com','www.peelports.com')
                or not parsed.path.startswith('/news-articles/') or url.rstrip('/')==NEWS_SOURCE.rstrip('/') or url in seen):
            continue
        seen.add(url)
        date = link.select_one('.eyebrow')
        published = None
        if date:
            try:
                published = datetime.strptime(date.get_text(' ',strip=True),'%d %b %Y').date().isoformat()
            except ValueError:
                pass
        items.append({'id':url, 'title':title.get_text(' ',strip=True), 'url':url,
            'description':'', 'published_at':published, 'valid_from':None, 'valid_to':None,
            'area':'Peel Ports Group', 'status':'Published news', 'severity':None})
    if not items:
        raise ValueError('No news cards found')
    return {**_section('Peel Ports Group',NEWS_SOURCE,message='Group news; stories are not necessarily specific to Liverpool or current operational notices.'),
        'items':items[:8]}


@st.cache_data(ttl=10800, show_spinner=False)
def load_weather():
    try:
        result = parse_weather(_download(WEATHER_URL).json())
    except (requests.RequestException,ValueError,TypeError,KeyError):
        result = {**_section('MET Norway',WEATHER_SOURCE,'unavailable','Weather forecast could not be checked.'),
                  'rows':[], 'updated_at':None, 'forecast_only':True}
    return {**result,'checked_at':_now()}


@st.cache_data(ttl=900, show_spinner=False)
def load_weather_warnings():
    try:
        result = parse_warning_feed(_download(WARNINGS_URL).text)
    except (requests.RequestException,ValueError,TypeError):
        result = _section('Met Office',WARNINGS_SOURCE,'unavailable','Weather warnings could not be checked. Open the official source.')
    return {**result,'checked_at':_now()}


@st.cache_data(ttl=900, show_spinner=False)
def load_flood_warnings():
    try:
        result = parse_flood_warnings(_download(FLOODS_URL).json())
    except (requests.RequestException,ValueError,TypeError,KeyError):
        result = _section('Environment Agency',FLOODS_URL,'unavailable','Flood warnings could not be checked. Open the official source.')
    return {**result,'checked_at':_now()}


@st.cache_data(ttl=300, show_spinner=False)
def load_tide():
    try:
        with request_session() as session:
            frame, _ = fetch_liverpool_tide_water_levels(_TideRequests(session))
        series = normalise_tide(frame)
        result = {**_section('Environment Agency',TIDE_SOURCE,
            'available' if series else 'unavailable','Recent measured water levels; high/low tide predictions are not connected.'), 'series':series}
    except (requests.RequestException,ValueError,TypeError,KeyError):
        result = {**_section('Environment Agency',TIDE_SOURCE,'unavailable','Water-level readings could not be checked.'),'series':[]}
    return {**result,'checked_at':_now()}


@st.cache_data(ttl=3600, show_spinner=False)
def load_port_news():
    try:
        result = parse_port_news(_download(NEWS_SOURCE).text)
    except (requests.RequestException,ValueError,TypeError):
        result = _section('Peel Ports Group',NEWS_SOURCE,'unavailable','Port news could not be checked. Open the official news page.')
    return {**result,'checked_at':_now()}


def _link_section(name, url, message, title):
    return {**_section(name,url,'link_only',message), 'items':[{'id':url,'title':title,'url':url,
        'description':'','published_at':None,'valid_from':None,'valid_to':None,'area':'',
        'status':'Official source','severity':None}]}


def load_daily_snapshot():
    loaders = {'weather':load_weather, 'tide':load_tide, 'weather_warnings':load_weather_warnings,
               'flood_warnings':load_flood_warnings, 'port_news':load_port_news}
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {name:pool.submit(loader) for name,loader in loaders.items()}
        snapshot = {name:future.result() for name,future in futures.items()}
    weather = snapshot['weather']
    if weather.get('forecast_only') and weather['status']=='available':
        now = datetime.now(timezone.utc)
        upcoming = [row for row in weather.get('rows',[]) if datetime.fromisoformat(row['time']) >= now]
        snapshot['weather'] = {**weather,'rows':upcoming}
        if not upcoming:
            snapshot['weather'].update(status='unavailable',message='No upcoming forecast remains in the cached source.')
    snapshot['port_notices'] = _link_section('Peel Ports',PORT_SOURCE,
        'Automatic port-notice updates are not connected. Check the official list and each notice for validity.',
        'Liverpool notices to mariners')
    snapshot['traffic'] = _link_section('National Highways',TRAFFIC_SOURCE,
        'Live road conditions are not connected. Use official traffic updates and planned closures.',
        'Official road incidents and closures')
    checked = [section['checked_at'] for section in snapshot.values() if section['status']=='available' and section.get('checked_at')]
    return {**snapshot,'checked_at':max(checked) if checked else None,
        'place':{'name':'Liverpool & Merseyside','lat':53.448,'lon':-3.015}}
