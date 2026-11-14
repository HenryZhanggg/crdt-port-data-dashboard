"""Everyday Liverpool overview, rendered from fetched source data only."""
from hashlib import sha1
from html import escape
import math
from urllib.parse import urlparse

from bs4 import BeautifulSoup
import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st

from monitoring_views import chart_style
from port_map import MARITIME_STYLE
from workspace_data import clean_water_series, water_chart_series


_SOURCE_HOSTS = {'api.met.no','met.no','www.met.no','weather.metoffice.gov.uk','www.metoffice.gov.uk',
    'metoffice.gov.uk','environment.data.gov.uk','check-for-flooding.service.gov.uk',
    'nationalhighways.co.uk','www.nationalhighways.co.uk','www.peelports.com','peelports.com',
    'creativecommons.org'}


def _plain(value):
    return BeautifulSoup(str(value or ''), 'html.parser').get_text(' ', strip=True)


def _time(value):
    return pd.to_datetime(value, utc=True, errors='coerce')


def _when(value):
    moment = _time(value)
    if isinstance(value, str) and len(value)==10 and pd.notna(moment):
        return moment.strftime('%d %b %Y')
    return moment.strftime('%d %b, %H:%M UTC') if pd.notna(moment) else 'Not supplied'


def _number(value, decimals=1):
    try:
        return f'{float(value):.{decimals}f}' if math.isfinite(float(value)) else 'Not available'
    except (ValueError, TypeError):
        return 'Not available'


def _safe_url(value):
    url = str(value or '')
    try:
        parsed = urlparse(url)
        valid = parsed.scheme=='https' and parsed.hostname in _SOURCE_HOSTS and parsed.port in (None,443) and not parsed.username and not parsed.password
    except ValueError:
        return None
    return url if valid else None


def _link(label, url):
    target = _safe_url(url)
    if target:
        st.link_button(label, target, width='stretch')


def _source(section):
    label = _plain(section.get('source_name', 'Official source'))
    if section.get('checked_at'):
        label += ' · Checked ' + _when(section['checked_at'])
    st.caption(label)


def _place_label(series):
    name = _plain(series['name']).split(' · ')[0]
    return name+' · '+_plain(series.get('datum','Unknown reference'))+' ('+_plain(series.get('unit',''))+')'


def _change_place():
    st.session_state['daily_map_revision'] = st.session_state.get('daily_map_revision', 0)+1


def _choose_place(place_id):
    st.session_state['daily_place_id'] = place_id
    _change_place()


def _save_place(place_id):
    saved = list(st.session_state.get('daily_saved_places', []))
    if place_id not in saved and len(saved)<4:
        st.session_state['daily_saved_places'] = saved+[place_id]


def _remove_place(place_id):
    st.session_state['daily_saved_places'] = [x for x in st.session_state.get('daily_saved_places', []) if x!=place_id]


def _water_frame(series, now):
    frame = pd.DataFrame(series.get('rows', []))
    if frame.empty:
        return pd.DataFrame(columns=['date_time','value'])
    frame = clean_water_series(frame.rename(columns={'time':'date_time'}))
    return frame.loc[frame['date_time'].le(now)].copy()


def _forecast_frame(section, now):
    frame = pd.DataFrame(section.get('rows', [])) if section.get('status')=='available' else pd.DataFrame()
    if frame.empty:
        return frame
    frame['time'] = pd.to_datetime(frame['time'], utc=True, errors='coerce')
    return frame.loc[frame['time'].ge(now)].sort_values('time').head(12).copy()


def _map(series, chosen, place):
    counts = {}
    points = []
    for entry in series:
        lat, lon = entry.get('lat'), entry.get('lon')
        if lat is None or lon is None or not math.isfinite(float(lat)) or not math.isfinite(float(lon)) or abs(float(lat))>90 or abs(float(lon))>180:
            continue
        location = (lat,lon)
        offset = counts.get(location,0)
        counts[location] = offset+1
        points.append({'id':entry['id'], 'lat':lat, 'lon':lon, 'name':escape(_place_label(entry)),
            'label':_plain(entry['name']).split(' · ')[0]+' · '+_plain(entry.get('unit','')),
            'offset':[17,-16+offset*30], 'color':[51,203,214] if entry['id']==chosen else [150,183,202],
            'border':1 if entry['id']==chosen else 0})
    layers = [pdk.Layer('ScatterplotLayer', points, id='daily-water', get_position='[lon, lat]',
        radius_units=pdk.types.String('pixels'), get_radius=7, get_fill_color='color', pickable=True),
        pdk.Layer('TextLayer', points, id='daily-water-labels', get_position='[lon, lat]', get_text='label',
            get_pixel_offset='offset', get_size=12, get_color=[230,241,248],
            get_text_anchor=pdk.types.String('start'), background=True,
            get_background_color=[10,29,43,235], background_padding=[5,3],
            get_border_width='border', get_border_color=[51,203,214], pickable=True)]
    selected = [point for point in points if point['id']==chosen]
    if selected:
        layers.append(pdk.Layer('ScatterplotLayer', selected, id='daily-selection', get_position='[lon, lat]',
            radius_units=pdk.types.String('pixels'), get_radius=12, filled=False, stroked=True,
            get_line_color=[235,247,250], line_width_min_pixels=2))
    if not points:
        layers = [pdk.Layer('ScatterplotLayer', [{'lat':place['lat'],'lon':place['lon']}],
            get_position='[lon, lat]', radius_units=pdk.types.String('pixels'), get_radius=6,
            get_fill_color=[150,183,202])]
    deck = pdk.Deck(layers=layers, map_style=MARITIME_STYLE,
        initial_view_state=pdk.ViewState(latitude=place['lat'], longitude=place['lon'], zoom=11.8),
        tooltip={'html':'<b>{name}</b><br>Water level reference'})
    membership = sha1('|'.join(p['id'] for p in points).encode()).hexdigest()[:10]
    event = st.pydeck_chart(deck, height=390, width='stretch', on_select='rerun',
        selection_mode='single-object', key=f"daily_map_{membership}_{st.session_state.get('daily_map_revision',0)}")
    for records in (event or {}).get('selection',{}).get('objects',{}).values():
        if records:
            return records[0].get('id')
    return None


def _items(section, empty_message='No items returned by this source.', limit=3):
    _source(section)
    if section.get('status')=='unavailable':
        st.info(_plain(section.get('message')) or 'Source temporarily unavailable.')
    elif section.get('status')=='link_only':
        st.caption(_plain(section.get('message')) or 'Open the official source for current information.')
    elif not section.get('items'):
        st.caption(empty_message)
    for item in section.get('items', [])[:limit]:
        st.markdown('<div class="daily-update-title">'+escape(_plain(item.get('title')) or 'Official update')+'</div>', unsafe_allow_html=True)
        details = [_plain(item.get('area')), _plain(item.get('status'))]
        if item.get('published_at'):
            details.append('Published '+_when(item['published_at']))
        if item.get('valid_from') or item.get('valid_to'):
            details.append('Valid '+_when(item.get('valid_from'))+' to '+_when(item.get('valid_to')))
        st.caption(' · '.join(x for x in details if x))
        if item.get('description'):
            st.caption(_plain(item['description'])[:320])
        _link('Read original', item.get('url'))
    if section.get('feed_updated_at'):
        st.caption('Feed timestamp: '+_when(section['feed_updated_at']))


def render_daily_home(snapshot):
    now = pd.Timestamp.now(tz='UTC')
    place = snapshot['place']
    weather, tide = snapshot['weather'], snapshot['tide']
    series = tide.get('series', []) if tide.get('status')=='available' else []
    lookup = {row['id']:row for row in series}
    pending = st.session_state.pop('daily_pending_place', None)
    if pending in lookup:
        _choose_place(pending)
    if lookup and st.session_state.get('daily_place_id') not in lookup:
        st.session_state['daily_place_id'] = next(iter(lookup))
    selected = lookup.get(st.session_state.get('daily_place_id'))
    frame = _water_frame(selected, now) if selected else pd.DataFrame(columns=['date_time','value'])
    available = frame.dropna(subset=['value'])
    latest = available.iloc[-1] if not available.empty else None
    forecast = _forecast_frame(weather, now)
    next_hour = forecast.iloc[0] if not forecast.empty else None
    with st.container(key='daily_heading'):
        st.subheader('Around Liverpool')
        st.caption(now.tz_convert('Europe/London').strftime('%A, %d %B %Y')+' · Liverpool & Merseyside · Last checked '+_when(snapshot.get('checked_at')))
    with st.container(key='daily_summary'):
        cards = st.columns(4, gap='small')
        cards[0].metric('Weather outlook', _number(next_hour['temp_c'])+' °C' if next_hour is not None and _number(next_hour['temp_c'])!='Not available' else 'Not available')
        cards[0].caption('Forecast '+_when(next_hour['time'])+' · Wind '+_number(next_hour.get('wind_m_s'))+' m/s' if next_hour is not None else 'Weather forecast not available')
        cards[1].metric('Latest water level', _number(latest['value'],2)+' '+selected.get('unit','') if latest is not None else 'Not available')
        cards[1].caption('Observed '+_when(latest['date_time']) if latest is not None else 'No current reading returned')
        warning_sections = [snapshot['weather_warnings'],snapshot['flood_warnings']]
        complete = all(s.get('status')=='available' for s in warning_sections)
        listed = sum(len(s.get('items',[])) for s in warning_sections)
        cards[2].metric('Weather & flood', (str(listed)+' listed' if listed else 'None listed') if complete else 'Check sources')
        cards[2].caption('North West weather / Liverpool-area flood feeds')
        notices = snapshot['port_notices']
        cards[3].metric('Port notices', str(len(notices.get('items',[])))+' listed' if notices.get('status')=='available' else 'Official list')
        cards[3].caption('Peel Ports · check each notice for validity')
    left, right = st.columns([2,1], gap='small')
    with left, st.container(border=True, key='daily_spatial'):
        st.markdown('**Explore the waterfront**')
        if lookup:
            st.selectbox('Water level', list(lookup), format_func=lambda value:_place_label(lookup[value]),
                key='daily_place_id', on_change=_change_place)
        picked = _map(series, st.session_state.get('daily_place_id'), place)
        if picked in lookup and picked!=st.session_state.get('daily_place_id'):
            st.session_state['daily_pending_place'] = picked
            st.rerun()
        st.caption('Select a water reference to view its latest readings.' if lookup else 'Location reference: Liverpool area. Water readings are not available.')
        if selected:
            st.caption('Reference: '+_plain(selected.get('datum','Unknown reference'))+' · '+_plain(selected.get('unit','')))
    with right, st.container(border=True, key='daily_updates'):
        st.markdown('**Local updates**')
        reminders, saved = st.tabs(['Reminders','My places'])
        with reminders, st.container(height=430, border=False):
            st.markdown('**Weather alerts**')
            _items(snapshot['weather_warnings'], 'No items returned for North West England.')
            _link('Check Met Office warnings', snapshot['weather_warnings'].get('source_url'))
            st.markdown('**Flood alerts**')
            _items(snapshot['flood_warnings'], 'No items returned for the Liverpool-area search.')
            _link('Check flood warnings', snapshot['flood_warnings'].get('source_url'))
            st.markdown('**Port notices**')
            _items(snapshot['port_notices'])
            _link('Open official port notices', snapshot['port_notices'].get('source_url'))
        with saved, st.container(key='daily_places'):
            st.caption('Keep up to four water references here during this visit.')
            pins = st.session_state.get('daily_saved_places', [])
            st.button('Save this place', key='daily_pin_place', disabled=not selected or (selected and selected['id'] in pins) or len(pins)>=4,
                on_click=_save_place, args=(selected['id'] if selected else None,), width='stretch')
            for place_id in pins:
                entry = lookup.get(place_id)
                st.button(_place_label(entry) if entry else 'Saved reference temporarily unavailable', key='daily_saved_'+place_id,
                    disabled=entry is None, on_click=_choose_place, args=(place_id,), width='stretch')
                st.button('Remove saved place', key='daily_remove_'+place_id, on_click=_remove_place, args=(place_id,))
    with st.container(border=True, key='daily_content'):
        weather_tab, tide_tab, travel_tab, news_tab = st.tabs(['Weather','Tides & water','Travel','Port news'])
        with weather_tab:
            st.markdown('**Weather outlook**')
            _source(weather)
            st.caption('Forecast model estimates from MET Norway · valid times shown in UTC · CC BY 4.0')
            if forecast.empty:
                st.info(_plain(weather.get('message')) or 'No future forecast hours returned.')
            else:
                cols = st.columns(2, gap='small')
                for column,key,label,unit in [(cols[0],'temp_c','Temperature','°C'),(cols[1],'wind_m_s','Wind speed','m/s')]:
                    values = pd.to_numeric(forecast[key],errors='coerce')
                    fig = go.Figure(go.Scatter(x=forecast['time'],y=values,mode='lines+markers',connectgaps=False,line={'color':'#157985','width':2}))
                    fig.update_layout(xaxis_title='Forecast time (UTC)', yaxis_title=label+' ('+unit+')')
                    column.plotly_chart(chart_style(fig,225),width='stretch',key='daily_forecast_'+key)
                table = forecast[['time','description','temp_c','wind_m_s','rain_mm']].copy()
                table['time'] = table['time'].dt.strftime('%d %b %H:%M UTC')
                st.dataframe(table.rename(columns={'time':'Time','description':'Outlook','temp_c':'Temperature (°C)','wind_m_s':'Wind (m/s)','rain_mm':'Rain, next hour (mm)'}), hide_index=True,width='stretch')
            st.caption('Forecast updated: '+_when(weather.get('updated_at')))
            _link('Weather data and attribution', weather.get('source_url'))
            _link('CC BY 4.0 licence', weather.get('license_url','https://creativecommons.org/licenses/by/4.0/'))
        with tide_tab:
            st.markdown('**Tides & water levels**')
            _source(tide)
            if latest is None:
                st.info(_plain(tide.get('message')) or 'No water readings returned.')
            else:
                st.write(_place_label(selected))
                st.caption('Observed '+_when(latest['date_time'])+' · Reference: '+_plain(selected.get('datum','Unknown reference')))
                if now-latest['date_time']>pd.Timedelta(hours=1):
                    st.info('The latest available reading is older than one hour.')
                tail = frame.tail(2)
                if len(tail)==2 and tail['value'].notna().all() and tail['date_time'].diff().iloc[-1]==pd.Timedelta(minutes=15):
                    change = tail['value'].iloc[-1]-tail['value'].iloc[0]
                    st.caption('Rose between latest readings' if change>0 else 'Fell between latest readings' if change<0 else 'Unchanged between latest readings')
                chart = water_chart_series(frame)
                fig = go.Figure(go.Scatter(x=chart.index,y=chart.values,mode='lines',connectgaps=False,line={'color':'#157985','width':2.5}))
                fig.update_layout(xaxis_title='Observation time (UTC)',yaxis_title='Water level ('+selected.get('unit','')+')')
                st.plotly_chart(chart_style(fig,260),width='stretch',key='daily_water_history')
                st.caption('Recent readings returned by the source. Tide predictions and next high/low times are not connected.')
            _link('Open Environment Agency water information', tide.get('source_url'))
        with travel_tab:
            st.markdown('**Nearby travel**')
            _items(snapshot['traffic'], limit=4)
            _link('Check traffic updates and planned closures', snapshot['traffic'].get('source_url'))
        with news_tab:
            st.markdown('**Port news**')
            _items(snapshot['port_news'],limit=4)
            st.caption('Peel Ports Group news; stories may concern ports outside Liverpool.')
            _link('Latest stories on Peel Ports', snapshot['port_news'].get('source_url'))
    with st.expander('About these updates'):
        st.caption('Forecasts, water observations and official notices keep their own dates and sources. No port operating status or flood impact is inferred from a water reading or an empty alert feed.')
        for key in ['weather','tide','weather_warnings','flood_warnings','port_notices','port_news','traffic']:
            section = snapshot[key]
            st.caption(_plain(section['source_name'])+' · '+section['status']+' · '+_when(section.get('checked_at')))
