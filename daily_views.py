"""Liverpool forecasts, observations and official updates with dated fallbacks."""
from calendar import month_abbr, month_name
from hashlib import sha1
from html import escape
import json
import math
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup
import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st

import daily_service
from port_map import MARITIME_STYLE
from workspace_data import clean_water_series
from workspace_links import water_handoff_context, open_water_observations
from public_media import render_public_media


OVERVIEW_WORKSPACE_BUILD='2026-11-25.2'
_SOURCE_HOSTS = {'api.met.no','met.no','www.met.no','weather.metoffice.gov.uk','www.metoffice.gov.uk',
    'metoffice.gov.uk','environment.data.gov.uk','check-for-flooding.service.gov.uk',
    'nationalhighways.co.uk','www.nationalhighways.co.uk','www.peelports.com','peelports.com',
    'creativecommons.org','www.nationalarchives.gov.uk'}
_DATA_DIR = Path(__file__).resolve().parent / 'data'
_OFFICIAL_WEATHER = 'https://weather.metoffice.gov.uk/forecast/gcmzggpxq'
_ARCHIVE_MEASURE = 'http://environment.data.gov.uk/flood-monitoring/id/measures/E70139-north_west-level-tidal_level-Mean-15_min-mAOD'
_WATER_COLOR = '#206095'
_WEATHER_COLOR = '#13776F'


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
    checked = pd.notna(_time(section.get('checked_at')))
    if section.get('status')=='link_only':
        label += ' · Link only · Not checked'
    elif section.get('status')=='unavailable':
        label += ' · Unavailable · '+('Attempted '+_when(section['checked_at']) if checked else 'Not checked')
    elif section.get('status')=='available' and checked:
        label += ' · Checked ' + _when(section['checked_at'])
    else:
        label += ' · Not checked'
    st.caption(label)
    if section.get('forecast_only') and pd.notna(_time(section.get('updated_at'))):
        st.caption('Forecast issued '+_when(section.get('updated_at')))
    if pd.notna(_time(section.get('feed_updated_at'))):
        st.caption('Feed published '+_when(section.get('feed_updated_at')))


def _observation_age(moment, now):
    minutes = max(0, int((now-moment).total_seconds()//60))
    hours, minutes = divmod(minutes,60)
    return (f'{hours}h {minutes:02d}m' if hours else f'{minutes}m')+' old'


def _place_label(series):
    name = _plain(series['name']).split(' · ')[0]
    station = series.get('station_reference','')
    measure = (series.get('measure_uri') or '').rsplit('/',1)[-1]
    if measure and station:
        variant, sep, _ = measure.removeprefix(station+'-').partition('-level-')
        name += ' · '+station
        if sep:
            name += ' '+_plain(variant.replace('_',' ').title())
    return name+' · '+_plain(series.get('datum','Unknown reference'))+' ('+_plain(series.get('unit',''))+')'


def _change_place():
    st.session_state['daily_map_revision'] = st.session_state.get('daily_map_revision', 0)+1


def _choose_place(place_id):
    st.session_state['daily_place_id'] = place_id
    _change_place()


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
    end = now+pd.Timedelta(hours=12)
    frame = frame.loc[frame['time'].gt(now) & frame['time'].le(end)].copy()
    frame.loc[frame['time']+pd.Timedelta(hours=1)>end,'rain_mm'] = None
    return frame.sort_values('time').drop_duplicates('time').dropna(subset=['temp_c','wind_m_s','rain_mm'],how='all')


@st.cache_data(show_spinner=False)
def _climate_normals():
    return json.loads((_DATA_DIR/'crosby_climate_normals.json').read_text(encoding='utf-8'))


@st.cache_data(show_spinner=False)
def _archived_water():
    records = pd.read_csv(_DATA_DIR/'ea_liverpool_archive.csv')
    records = records.loc[records['measure'].eq(_ARCHIVE_MEASURE)].rename(columns={'dateTime':'date_time'})
    records = clean_water_series(records)
    return records.loc[records['date_time'].gt(records['date_time'].max()-pd.Timedelta(days=2))]


def _water_window(frame, period_seconds, end):
    start = end-pd.Timedelta(hours=12)
    measured = frame.set_index('date_time')['value'].sort_index()
    window = measured.loc[(measured.index>start) & (measured.index<=end)]
    if not period_seconds or period_seconds>43200 or window.empty:
        return window, None
    period = pd.Timedelta(seconds=period_seconds)
    anchor = window.dropna().index.max() if window.notna().any() else window.index.max()
    last_slot = anchor + ((end-anchor)//period)*period
    slots = pd.date_range(end=last_slot, periods=pd.Timedelta(hours=12)//period, freq=period)
    trace = window.reindex(window.index.union(slots).sort_values())
    return trace, slots


def _recent_water_change(trace, period_seconds, now):
    valid = trace.dropna()
    if valid.empty or not period_seconds or 3600 % period_seconds:
        return None
    last = valid.index[-1]
    if now-last>pd.Timedelta(hours=1):
        return None
    points = valid.reindex(pd.date_range(end=last, periods=3600//period_seconds+1,
        freq=pd.Timedelta(seconds=period_seconds)))
    return points.iloc[-1]-points.iloc[0] if points.notna().all() else None


def _map(series, chosen, place, focus=None, *, key_prefix='daily_map', height=310):
    counts = {}
    points = []
    for entry in series:
        lat, lon = entry.get('lat'), entry.get('lon')
        if lat is None or lon is None or not math.isfinite(float(lat)) or not math.isfinite(float(lon)) or abs(float(lat))>90 or abs(float(lon))>180:
            continue
        location = (lat,lon)
        offset = counts.get(location,0)
        counts[location] = offset+1
        reference = _place_label(entry)
        points.append({'id':entry['id'], 'lat':lat, 'lon':lon, 'name':escape(reference),
            'label':reference.rsplit(' · ',1)[0]+' · '+_plain(entry.get('unit','')),
            'offset':[17,-16+offset*30], 'color':[124,131,253] if entry['id']==chosen else [149,162,181],
            'border':1 if entry['id']==chosen else 0})
    layers = [pdk.Layer('ScatterplotLayer', points, id='daily-water', get_position='[lon, lat]',
        radius_units=pdk.types.String('pixels'), get_radius=7, get_fill_color='color', pickable=True),
        pdk.Layer('TextLayer', points, id='daily-water-labels', get_position='[lon, lat]', get_text='label',
            get_pixel_offset='offset', get_size=12, get_color=[230,241,248],
            get_text_anchor=pdk.types.String('start'), background=True,
            get_background_color=[10,29,43,235], background_padding=[5,3],
            get_border_width='border', get_border_color=[124,131,253], pickable=True)] if points else []
    selected = [point for point in points if point['id']==chosen]
    if selected:
        layers.append(pdk.Layer('ScatterplotLayer', selected, id='daily-selection', get_position='[lon, lat]',
            radius_units=pdk.types.String('pixels'), get_radius=12, filled=False, stroked=True,
            get_line_color=[124,131,253], line_width_min_pixels=2))
    lat, lon, zoom = place['lat'], place['lon'], 11.8
    focus = focus or {}
    if focus.get('geojson'):
        geometry = focus['geojson']
        colour = [191,204,220] if focus.get('reference') else [255,181,71]
        layers.insert(0,pdk.Layer('GeoJsonLayer',geometry,id='selected-flood-area',
            filled=not focus.get('reference'),stroked=True,get_line_color=colour,
            get_fill_color=colour+[52],line_width_min_pixels=2,pickable=False))
        positions = []
        for feature in geometry['features']:
            shape = feature['geometry']
            polygons = shape['coordinates'] if shape['type']=='MultiPolygon' else [shape['coordinates']]
            positions.extend(position for polygon in polygons for ring in polygon for position in ring)
        xs,ys = zip(*[(point[0],point[1]) for point in positions])
        lon,lat = (min(xs)+max(xs))/2,(min(ys)+max(ys))/2
        spread = max(max(xs)-min(xs),1.7*(max(ys)-min(ys)),.02)
        zoom = min(12,math.log2(145/spread))
    if focus.get('stops'):
        layers.append(pdk.Layer('ScatterplotLayer',focus['stops'],id='transport-access-points',
            get_position='[lon, lat]',radius_units=pdk.types.String('pixels'),get_radius=4,
            get_fill_color=[228,225,255],stroked=True,get_line_color=[111,103,224],line_width_min_pixels=1,
            pickable=False))
    deck = pdk.Deck(layers=layers, map_style=MARITIME_STYLE,
        initial_view_state=pdk.ViewState(latitude=lat, longitude=lon, zoom=zoom),
        tooltip={'html':'<b>{name}</b><br>Water level reference'})
    membership = sha1('|'.join([str(focus.get('area_id','')),*[p['id'] for p in points]]).encode()).hexdigest()[:10]
    event = st.pydeck_chart(deck, height=height, width='stretch', on_select='rerun',
        selection_mode='single-object', key=f"{key_prefix}_{membership}_{st.session_state.get('daily_map_revision',0)}")
    for records in (event or {}).get('selection',{}).get('objects',{}).values():
        if records:
            return records[0].get('id')
    return None


_UPDATE_SECTIONS = [('port_notices','Port'),('port_news','Port'),
                    ('weather_warnings','Weather'),('flood_warnings','Weather'),('traffic','Travel')]


def update_items(snapshot, category='All'):
    rows = [dict(item, category=group, source_key=key)
            for key,group in _UPDATE_SECTIONS if category in ('All',group)
            for item in snapshot[key].get('items', [])]
    def published(row):
        moment = _time(row.get('published_at'))
        return moment.value if pd.notna(moment) else -1
    return sorted(rows, key=lambda row:(row['source_key']!='port_news',published(row)), reverse=True)


def _validity(item, now):
    start, end = _time(item.get('valid_from')), _time(item.get('valid_to'))
    if (pd.notna(end) and end<now) or item.get('severity_level')==4:
        return 'Historical / expired'
    if pd.notna(start) and start>now:
        return 'Upcoming'
    if pd.notna(start) and pd.notna(end):
        return 'In effect'
    return 'Validity unconfirmed'


def _rain_period(start):
    moment = _time(start)
    return f"{moment:%d %b, %H:%M}–{moment+pd.Timedelta(hours=1):%H:%M} UTC"


def _current_flood_areas(section, now):
    if section.get('status')!='available':
        return {}
    return {item['flood_area_id']:item for item in section.get('items',[])
            if item.get('flood_area_id') and _validity(item,now)!='Historical / expired'}


def _flood_map_focus(area_id, areas):
    area = daily_service.load_flood_area_geometry(area_id)
    return {'geojson':area.get('geojson'),'reference':area_id not in areas,'area_id':area_id}


def _update_headline(item, source, context):
    title = escape(_plain(item.get('title')) or 'Source update')
    url = _safe_url(item.get('url'))
    if url:
        title = '<a href="'+escape(url,quote=True)+'" target="_blank" rel="noopener noreferrer">'+title+'</a>'
    byline = escape(' · '.join(part for part in [_plain(source), context] if part))
    st.markdown('<article class="daily-update"><div class="daily-update-title">'+title+
        '</div><div class="daily-source">'+byline+'</div></article>',unsafe_allow_html=True)


def _daily_updates(snapshot, advisories, complete):
    advisories_column, news_column = st.columns(2,gap='small')
    with advisories_column, st.container(border=True,key='daily_advisories'):
        st.markdown('**Official advisories**')
        st.caption('North West weather · Liverpool-area floods')
        current = [(item,state) for item,state in advisories if state!='Historical / expired']
        if current:
            order = {'In effect':0,'Upcoming':1,'Validity unconfirmed':2}
            ranked = sorted(current,key=lambda row:order[row[1]])
            by_source = {}
            for entry in ranked:
                by_source.setdefault(entry[0]['source_key'],entry)
            first = list(by_source.values())
            for item,state in (first+[entry for entry in ranked if entry not in first])[:3]:
                _update_headline(item,snapshot[item['source_key']]['source_name'],state)
        elif complete:
            st.caption('No current advisories listed in the checked feeds.')
        else:
            st.caption('Check the official sources for current advisories.')
        weather, flood = st.columns(2,gap='small')
        with weather:
            _link('Weather warnings',snapshot['weather_warnings'].get('source_url'))
        with flood:
            _link('Flood warnings',snapshot['flood_warnings'].get('source_url'))
    with news_column, st.container(border=True,key='daily_updates'):
        st.markdown('**Port news**')
        news = snapshot['port_news']
        articles = [item for item in update_items(snapshot,'Port') if item['source_key']=='port_news']
        if articles and news.get('status')=='available':
            for article in articles[:3]:
                date = _time(article.get('published_at'))
                published = 'Published '+date.strftime('%d %b %Y') if pd.notna(date) else ''
                _update_headline(article,news['source_name'],published)
        else:
            st.caption('Find the latest stories on the Peel Ports website.')
        _link('More from Peel Ports',news.get('source_url'))


def _overview_chart(fig, height):
    fig.update_layout(template='plotly_white',height=height,margin={'l':10,'r':14,'t':12,'b':18},
        paper_bgcolor='#FFFFFF',plot_bgcolor='#FFFFFF',font={'color':'#23384F','size':12},
        hovermode='x unified',hoverlabel={'bgcolor':'#FFFFFF','font_color':'#23384F'},
        legend={'orientation':'h','y':1.10})
    axis = {'gridcolor':'#E1E8EF','automargin':True,'zeroline':False,
            'tickfont':{'color':'#42566E'},'title_font':{'color':'#23384F'}}
    fig.update_xaxes(**axis)
    fig.update_yaxes(**axis)
    return fig


def _weather_chart(forecast, climate, month):
    if forecast.empty:
        st.markdown('**Crosby climate normals**')
        st.caption(f"Met Office · {climate['period_start']}–{climate['period_end']} monthly averages")
        months = [month_abbr[row['month']] for row in climate['monthly']]
        fig = go.Figure()
        for field, label, color in [('mean_daily_max_c','Avg daily high',_WEATHER_COLOR),
                                     ('mean_daily_min_c','Avg daily low',_WATER_COLOR)]:
            fig.add_scatter(x=months,y=[row[field] for row in climate['monthly']],name=label,mode='lines+markers',
                line={'color':color},hovertemplate='%{y:.2f} °C')
        fig.add_vline(x=month-1,line={'color':'#64748B','dash':'dot','width':1})
        fig.update_yaxes(title_text='Temperature (°C)')
        _overview_chart(fig,255).update_layout(margin={'t':37})
        st.plotly_chart(fig,width='stretch',theme=None,key='daily_weather_mini')
        st.caption(climate['attribution'])
        st.markdown('[Met Office climate data]('+climate['source_url']+') · [OGL v3.0]('+climate['licence_url']+')')
        _link('Open Met Office forecast',_OFFICIAL_WEATHER)
        return

    st.markdown('**Weather forecast**')
    variables = {'Temperature':('temp_c','Temperature (°C)'),
                 'Wind':('wind_m_s','Wind speed (m/s)'), 'Rain':('rain_mm','Rain in one hour (mm)')}
    choices = [name for name,(field,_) in variables.items() if forecast[field].notna().any()]
    if len(choices)>1:
        if st.session_state.get('daily_weather_variable') not in choices:
            st.session_state['daily_weather_variable']=choices[0]
        chosen = st.radio('Weather variable',choices,horizontal=True,label_visibility='collapsed',key='daily_weather_variable')
    else:
        chosen = choices[0]
    field,unit = variables[chosen]
    times = pd.DatetimeIndex(forecast['time'])
    grid = pd.date_range(times.min(),times.max(),freq='h')
    hourly = forecast.set_index('time').reindex(times.union(grid).sort_values())
    if field=='rain_mm':
        labels = [[hour.isoformat(),_rain_period(hour)] for hour in hourly.index]
        data = go.Bar(x=hourly.index+pd.Timedelta(minutes=30),y=hourly[field],
            customdata=labels,width=45*60*1000,marker_color=_WATER_COLOR,name='Next-hour rain',
            hovertemplate='%{customdata[1]}<br>%{y:.1f} mm<extra></extra>')
    else:
        data = go.Scatter(x=hourly.index,y=hourly[field],mode='lines+markers',connectgaps=False,
            line={'color':_WEATHER_COLOR,'width':2},marker={'size':5},name=unit)
    fig = go.Figure(data)
    fig.update_layout(xaxis_title='Forecast time (UTC)',yaxis_title=unit,showlegend=False)
    _overview_chart(fig,270)
    if chosen=='Rain':
        fig.update_yaxes(rangemode='nonnegative')
    st.plotly_chart(fig,width='stretch',theme=None,key='daily_weather_mini')
    st.caption('MET Norway forecast · CC BY 4.0'+(' · Each bar covers one hour' if chosen=='Rain' else ''))


def _water_chart(trace, slots, selected, archive):
    if archive is not None:
        st.caption('Liverpool · E70139 North West · Ordnance Datum Newlyn (mAOD)')
        trace = archive.set_index('date_time')['value']
        trace = trace.reindex(trace.index.union(pd.date_range(trace.index.min(),trace.index.max(),freq='15min')).sort_values())
        unit = 'mAOD'
    else:
        unit = selected.get('unit','')
    fig = go.Figure(go.Scatter(x=trace.index,y=trace.values,mode='markers' if slots is None and archive is None else 'lines+markers',
        line={'color':_WATER_COLOR,'width':2},marker={'size':4},connectgaps=False,name='Water level'))
    fig.update_layout(yaxis_title=f'Water level ({unit})',xaxis_title='Observation time (UTC)')
    st.plotly_chart(_overview_chart(fig,270),width='stretch',theme=None,key='daily_water_mini')
    if archive is not None:
        st.caption(f'Archived observations · {trace.index.min():%d %b} to {trace.index.max():%d %b %Y}')
        st.caption('This uses Environment Agency flood and river level data from the real-time data API (Beta).')
        _link('Open Environment Agency archive', 'https://environment.data.gov.uk/flood-monitoring/archive')
        return
    st.caption('Environment Agency'+(' · Gaps show missing readings' if trace.isna().any() else ''))
    st.button('Explore readings',on_click=open_water_observations,args=(selected,),
        disabled=water_handoff_context(selected) is None,key='daily_explore_water')


def render_daily_home(snapshot):
    from weather_map_views import render_layer_map

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
    archive = _archived_water() if latest is None else None
    period = selected.get('period_seconds') if selected else None
    trace, slots = _water_window(frame,period,now) if latest is not None else (None,None)
    if latest is not None and not trace.notna().any():
        trace, slots = _water_window(frame,period,latest['date_time'])
    change = _recent_water_change(trace,period,now) if trace is not None else None
    forecast = _forecast_frame(weather, now)
    climate = _climate_normals() if forecast.empty else None
    month = now.tz_convert('Europe/London').month
    temperatures = forecast.get('temp_c',pd.Series(dtype=float)).dropna()
    wind = forecast.get('wind_m_s',pd.Series(dtype=float)).dropna()
    warning_sections = [snapshot['weather_warnings'],snapshot['flood_warnings']]
    complete = all(s.get('status')=='available' and pd.notna(_time(s.get('checked_at'))) for s in warning_sections)
    advisories = [(item,_validity(item,now)) for item in update_items(snapshot,'Weather')
                  if snapshot[item['source_key']].get('status')=='available']
    listed = any(state!='Historical / expired' for _,state in advisories)
    with st.container(key='daily_heading'):
        st.subheader('Around Liverpool')
        st.caption(now.tz_convert('Europe/London').strftime('%A, %d %B %Y')+' · Liverpool & Merseyside')
    with st.container(key='daily_summary'):
        cards = st.columns(3, gap='small')
        with cards[0], st.container(border=True,key='daily_weather_summary'):
            if climate:
                usual = climate['monthly'][month-1]
                st.metric(f'Typical {month_name[month]} temperatures',
                    f"{usual['mean_daily_min_c']:.1f}–{usual['mean_daily_max_c']:.1f} °C")
                st.caption('Crosby · 1991–2020 climate averages')
            else:
                if not temperatures.empty:
                    st.metric('Weather outlook',f'{temperatures.min():.1f}–{temperatures.max():.1f} °C'
                        if len(temperatures)>1 else f'{temperatures.iloc[0]:.1f} °C')
                elif not wind.empty:
                    st.metric('Peak wind forecast',f'{wind.max():.1f} m/s')
                else:
                    st.metric('Rain outlook',f"{forecast['rain_mm'].dropna().iloc[0]:.1f} mm in one hour")
                partial = 0<len(temperatures)<12 or len(forecast)<12
                st.caption('Next 12 hours'+(' · Partial forecast' if partial else ''))
        with cards[1], st.container(border=True,key='daily_water_summary'):
            if archive is not None:
                last_archived = archive.dropna(subset=['value']).iloc[-1]
                st.metric('Archived water level',f"{last_archived['value']:.2f} mAOD")
                st.caption(f"Liverpool archive · {last_archived['date_time']:%d %b %Y}")
            else:
                unit = selected.get('unit','')
                st.metric('Latest water level',f"{latest['value']:.2f} {unit}")
                station = _plain(selected['name']).split(' · ')[0]
                if now-latest['date_time']>pd.Timedelta(hours=1):
                    station += ' · Delayed reading'
                elif change is not None:
                    station += ' · '+('Rising' if change>0 else 'Falling' if change<0 else 'Steady')
                st.caption(station)
        with cards[2], st.container(border=True,key='daily_advisory_summary'):
            st.metric('Weather & flood',('Advisories listed' if listed else 'None listed') if complete else 'Check sources')
            for key,section in zip(('weather_warnings','flood_warnings'),warning_sections):
                count = sum(item['source_key']==key and state!='Historical / expired' for item,state in advisories)
                result = 'Check official source'
                if section.get('status')=='available' and pd.notna(_time(section.get('checked_at'))):
                    if count:
                        result = '1 advisory listed' if count==1 else f'{count} advisories listed'
                    else:
                        result = 'No current advisories listed' if section.get('items') else 'No advisories returned'
                st.caption(f"{section['source_name']} · {result}")
    water_chart, weather_chart = st.columns([1.2,1],gap='small')
    with water_chart, st.container(border=True,key='daily_water_trend'):
        st.markdown('**Environment Agency archive**' if archive is not None else '**Water levels**')
        if lookup:
            st.selectbox('Water level',list(lookup),format_func=lambda value:_place_label(lookup[value]),
                key='daily_place_id',on_change=_change_place,label_visibility='collapsed')
        _water_chart(trace,slots,selected,archive)
    with weather_chart, st.container(border=True,key='daily_weather_trend'):
        _weather_chart(forecast,climate,month)
    _daily_updates(snapshot,advisories,complete)
    with st.container(border=True,key='daily_spatial'):
        st.markdown('<h3 id="waterfront-map">Explore the waterfront</h3>',unsafe_allow_html=True)
        picked = render_layer_map(snapshot, 'overview', series=series, selected=st.session_state.get('daily_place_id'))
        if picked in lookup and picked!=st.session_state.get('daily_place_id'):
            st.session_state['daily_pending_place'] = picked
            st.rerun()
        port,roads = st.columns(2,gap='small')
        with port:
            _link('Port notices',snapshot['port_notices'].get('source_url'))
        with roads:
            _link('Road updates',snapshot['traffic'].get('source_url'))
    weather_details, water_details = st.columns(2, gap='small')
    with weather_details:
        with st.expander('Weather forecast details'):
            _source(weather)
            st.caption('Forecast model estimates from MET Norway · valid times shown in UTC · CC BY 4.0')
            if forecast.empty:
                st.info(_plain(weather.get('message')) or 'No future forecast hours returned.')
            else:
                st.caption('Forecast valid '+_when(forecast['time'].min())+' to '+_when(forecast['time'].max()))
                st.caption(f'{len(temperatures)} of 12 hourly temperature points returned')
                if not wind.empty:
                    peak = forecast.loc[wind.idxmax()]
                    st.caption(f"Peak forecast wind {peak['wind_m_s']:.1f} m/s · {_when(peak['time'])}")
                table = forecast[['time','description','temp_c','wind_m_s','rain_mm']].copy()
                table['time'] = table['time'].dt.strftime('%d %b %H:%M UTC')
                st.dataframe(table.rename(columns={'time':'Time','description':'Outlook','temp_c':'Temperature (°C)','wind_m_s':'Wind (m/s)','rain_mm':'Rain, next hour (mm)'}), hide_index=True,width='stretch')
            _link('Weather data and attribution', weather.get('source_url'))
            _link('CC BY 4.0 licence', weather.get('license_url','https://creativecommons.org/licenses/by/4.0/'))
    with water_details:
        with st.expander('Water observation details'):
            _source(tide)
            if selected:
                st.caption(_place_label(selected))
            if latest is None:
                st.info(_plain(tide.get('message')) or 'No water readings returned.')
            else:
                st.caption('Observed '+_when(latest['date_time'])+' · '+_observation_age(latest['date_time'],now))
                if change is not None:
                    st.caption(f"1-hour change {change:+.2f} {selected.get('unit','')}")
                if slots is not None:
                    st.caption(f'{trace.reindex(slots).count()} of {len(slots)} expected readings · 12 hours ending {_when(slots[-1])}')
                else:
                    st.caption(f'{trace.count()} valid readings · sampling interval unverified')
            if not frame.empty:
                table = frame[['date_time','value']].copy()
                table['date_time'] = table['date_time'].dt.strftime('%d %b %Y %H:%M UTC')
                table = table.rename(columns={'date_time':'Observed time (UTC)','value':'Water level ('+selected.get('unit','')+')'})
                st.dataframe(table,hide_index=True,width='stretch')
                export = frame[['date_time','value']].assign(reference=_plain(selected['name']),
                    unit=selected.get('unit',''),datum=selected.get('datum','Unknown reference'),
                    measure_uri=selected.get('measure_uri',''),
                    source_url=selected.get('source_url') or tide.get('source_url'))
                st.download_button('Download water observations CSV',export.to_csv(index=False),
                    file_name='water-observations.csv',mime='text/csv',key='daily_water_csv')
            st.caption('Recent readings returned by the source. Tide predictions and next high/low times are not connected.')
            _link('Open Environment Agency water information', (selected.get('source_url') if selected else None) or tide.get('source_url'))
    render_public_media()
    with st.expander('Advisory and news sources'):
        st.caption('Weather warnings cover North West England. Flood warnings cover the Liverpool area. Peel Ports Group news can cover other ports.')
        for key in ('weather_warnings','flood_warnings','port_notices','port_news','traffic'):
            section = snapshot[key]
            _source(section)
            if section.get('message'):
                st.caption(_plain(section['message']))
        for item,state in advisories:
            _update_headline(item,snapshot[item['source_key']]['source_name'],state)
            timestamp_label = 'Reviewed' if item['source_key']=='flood_warnings' else 'Published'
            for field,label in (('published_at',timestamp_label),('updated_at','Updated')):
                if pd.notna(_time(item.get(field))):
                    st.caption(label+' '+_when(item[field]))
            if item.get('valid_from') or item.get('valid_to'):
                st.caption('Validity: '+_when(item.get('valid_from'))+' → '+_when(item.get('valid_to')))
            if item.get('description'):
                st.caption(_plain(item['description'])[:240])
