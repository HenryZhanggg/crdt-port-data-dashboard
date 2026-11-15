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
from workspace_links import water_handoff_context, open_water_observations
from public_media import render_public_media


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
    if section.get('forecast_only'):
        st.caption('Forecast issued '+_when(section.get('updated_at')))
    if 'feed_updated_at' in section:
        st.caption('Feed published '+_when(section.get('feed_updated_at')))


def _observation_age(moment, now):
    minutes = max(0, int((now-moment).total_seconds()//60))
    hours, minutes = divmod(minutes,60)
    return (f'{hours}h {minutes:02d}m' if hours else f'{minutes}m')+' old'


def _place_label(series):
    name = _plain(series['name']).split(' · ')[0]
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
            'offset':[17,-16+offset*30], 'color':[124,131,253] if entry['id']==chosen else [149,162,181],
            'border':1 if entry['id']==chosen else 0})
    layers = [pdk.Layer('ScatterplotLayer', points, id='daily-water', get_position='[lon, lat]',
        radius_units=pdk.types.String('pixels'), get_radius=7, get_fill_color='color', pickable=True),
        pdk.Layer('TextLayer', points, id='daily-water-labels', get_position='[lon, lat]', get_text='label',
            get_pixel_offset='offset', get_size=12, get_color=[230,241,248],
            get_text_anchor=pdk.types.String('start'), background=True,
            get_background_color=[10,29,43,235], background_padding=[5,3],
            get_border_width='border', get_border_color=[124,131,253], pickable=True)]
    selected = [point for point in points if point['id']==chosen]
    if selected:
        layers.append(pdk.Layer('ScatterplotLayer', selected, id='daily-selection', get_position='[lon, lat]',
            radius_units=pdk.types.String('pixels'), get_radius=12, filled=False, stroked=True,
            get_line_color=[124,131,253], line_width_min_pixels=2))
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
        return 'Historical / expired · Check the official source for current notices'
    if pd.notna(start) and start>now:
        return 'Upcoming · Check stated validity in the official source'
    if pd.notna(start) and pd.notna(end):
        return 'Within stated validity · Confirm details in the official source'
    return 'Validity unconfirmed · Check the official source'


def _update_feed(snapshot, category):
    links = [(key,group) for key,group in _UPDATE_SECTIONS
             if key in {'port_notices','traffic'} and category in ('All',group)]
    if links:
        columns = st.columns(len(links),gap='small')
        for column,(key,group) in zip(columns,links):
            with column:
                section = snapshot[key]
                _source(section)
                st.caption(_plain(section.get('message')) or 'Check the official source for current notices.')
                _link('Open '+_plain(section['source_name'])+' · '+('port notices' if key=='port_notices' else 'travel'),section.get('source_url'))
    for key,group in _UPDATE_SECTIONS:
        if key in {'port_notices','traffic'} or category not in ('All',group):
            continue
        section = snapshot[key]
        _source(section)
        if key=='port_news':
            published = [item['published_at'] for item in section.get('items',[]) if pd.notna(_time(item.get('published_at')))]
            st.caption('Latest publication '+_when(max(published,key=_time) if published else None))
        if section.get('status')!='available' or not section.get('items'):
            if section.get('status')=='unavailable':
                st.info(_plain(section.get('message')) or 'Source temporarily unavailable.')
            elif section.get('status')=='link_only':
                st.caption(_plain(section.get('message')) or 'Automatic feed not connected.')
            elif not section.get('items'):
                st.caption('No items returned by '+_plain(section['source_name'])+'. Check the source for current coverage.')
            _link('Open '+_plain(section['source_name'])+' · '+group.lower(),section.get('source_url'))
    rows = [item for item in update_items(snapshot, category) if snapshot[item['source_key']].get('status')!='link_only']
    for item in rows[:6]:
        section = snapshot[item['source_key']]
        title = escape(_plain(item.get('title')) or 'Source update')
        url = _safe_url(item.get('url'))
        if url:
            title = '<a href="'+escape(url,quote=True)+'" target="_blank" rel="noopener noreferrer">'+title+'</a>'
        st.markdown('<article class="daily-update"><span class="daily-category">'+item['category']+'</span>'
            '<div class="daily-update-title">'+title+'</div><div class="daily-source">'
            +escape(_plain(section['source_name']))+' · '+escape('Published '+_when(item['published_at']) if item.get('published_at') else 'Publication date not supplied')
            +'</div></article>',unsafe_allow_html=True)
        if item['source_key']!='port_news':
            st.caption(_validity(item,pd.Timestamp.now(tz='UTC')))
        if item.get('valid_from') or item.get('valid_to'):
            st.caption('Validity: '+_when(item.get('valid_from'))+' → '+_when(item.get('valid_to')))
        if item.get('description'):
            st.caption(_plain(item['description'])[:240])


def _compact_trends(forecast, frame, selected):
    cols = st.columns(2, gap='small')
    with cols[0], st.container(border=True, key='daily_weather_trend'):
        st.markdown('**Next hours · weather**')
        if forecast.empty:
            st.caption('Forecast currently unavailable.')
        else:
            fig = go.Figure(go.Scatter(x=forecast['time'],y=forecast['temp_c'], mode='lines',
                line={'color':'#7C83FD','width':2},connectgaps=False,fill='tozeroy',fillcolor='rgba(124,131,253,.08)'))
            fig.update_layout(yaxis_title='Temperature (°C)', xaxis_title='Forecast time (UTC)')
            st.plotly_chart(chart_style(fig,175),width='stretch',key='daily_weather_mini')
        st.caption('MET Norway forecast · CC BY 4.0 · model estimates')
    with cols[1], st.container(border=True, key='daily_water_trend'):
        st.markdown('**Recent hours · water**')
        if frame.empty or not selected:
            st.caption('Water observations currently unavailable.')
        else:
            chart = water_chart_series(frame)
            fig = go.Figure(go.Scatter(x=chart.index,y=chart.values,mode='lines',
                line={'color':'#62B8C9','width':2},connectgaps=False))
            fig.update_layout(yaxis_title='Water level ('+selected.get('unit','')+')',xaxis_title='Observation time (UTC)')
            st.plotly_chart(chart_style(fig,175),width='stretch',key='daily_water_mini')
            st.caption(_place_label(selected))
        st.button('Explore readings',on_click=open_water_observations,args=(selected,),
            disabled=water_handoff_context(selected) is None,key='daily_explore_water')


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
        st.caption(now.tz_convert('Europe/London').strftime('%A, %d %B %Y')+' · Liverpool & Merseyside · Sources checked separately')
    with st.container(key='daily_summary'):
        cards = st.columns(3, gap='small')
        cards[0].metric('Weather outlook', _number(next_hour['temp_c'])+' °C' if next_hour is not None and _number(next_hour['temp_c'])!='Not available' else 'Not available')
        cards[0].caption('Forecast valid '+_when(next_hour['time'])+' · Wind '+_number(next_hour.get('wind_m_s'))+' m/s' if next_hour is not None else 'Weather forecast not available')
        with cards[0]:
            _source(weather)
        cards[1].metric('Latest water level', _number(latest['value'],2)+' '+selected.get('unit','') if latest is not None else 'Not available')
        cards[1].caption('Observed '+_when(latest['date_time'])+' · '+_observation_age(latest['date_time'],now) if latest is not None else 'No current reading returned')
        if latest is not None and now-latest['date_time']>pd.Timedelta(hours=1):
            cards[1].info('Late · older than one hour')
        with cards[1]:
            _source(tide)
        warning_sections = [snapshot['weather_warnings'],snapshot['flood_warnings']]
        complete = all(s.get('status')=='available' and pd.notna(_time(s.get('checked_at'))) for s in warning_sections)
        listed = sum(len(s.get('items',[])) for s in warning_sections)
        cards[2].metric('Weather & flood', (str(listed)+' listed' if listed else 'None listed') if complete else 'Check sources')
        cards[2].caption('North West weather / Liverpool-area flood feeds')
        with cards[2]:
            for section in warning_sections:
                _source(section)
    left, right = st.columns([1.85,1], gap='small')
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
        st.markdown('**Latest updates**')
        category = st.radio('Latest updates',['All','Port','Weather','Travel'],horizontal=True,
            label_visibility='collapsed',key='daily_update_category')
        with st.container(height=390, border=False):
            _update_feed(snapshot,category)
    _compact_trends(forecast,frame,selected)
    weather_details, water_details = st.columns(2, gap='small')
    with weather_details:
        with st.expander('Weather forecast details'):
            _source(weather)
            st.caption('Forecast model estimates from MET Norway · valid times shown in UTC · CC BY 4.0')
            if forecast.empty:
                st.info(_plain(weather.get('message')) or 'No future forecast hours returned.')
            else:
                table = forecast[['time','description','temp_c','wind_m_s','rain_mm']].copy()
                table['time'] = table['time'].dt.strftime('%d %b %H:%M UTC')
                st.dataframe(table.rename(columns={'time':'Time','description':'Outlook','temp_c':'Temperature (°C)','wind_m_s':'Wind (m/s)','rain_mm':'Rain, next hour (mm)'}), hide_index=True,width='stretch')
            st.caption('Forecast updated: '+_when(weather.get('updated_at')))
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
                st.caption('Observed '+_when(latest['date_time'])+' · Reference: '+_plain(selected.get('datum','Unknown reference')))
                tail = frame.tail(2)
                if len(tail)==2 and tail['value'].notna().all() and tail['date_time'].diff().iloc[-1]==pd.Timedelta(minutes=15):
                    change = tail['value'].iloc[-1]-tail['value'].iloc[0]
                    st.caption('Rose between latest readings' if change>0 else 'Fell between latest readings' if change<0 else 'Unchanged between latest readings')
            if not frame.empty:
                table = frame[['date_time','value']].copy()
                table['date_time'] = table['date_time'].dt.strftime('%d %b %Y %H:%M UTC')
                table = table.rename(columns={'date_time':'Observed time (UTC)','value':'Water level ('+selected.get('unit','')+')'})
                st.dataframe(table,hide_index=True,width='stretch')
                export = frame[['date_time','value']].assign(reference=_plain(selected['name']),
                    unit=selected.get('unit',''),datum=selected.get('datum','Unknown reference'),
                    source_url=selected.get('source_url') or tide.get('source_url'))
                st.download_button('Download water observations CSV',export.to_csv(index=False),
                    file_name='water-observations.csv',mime='text/csv',key='daily_water_csv')
            st.caption('Recent readings returned by the source. Tide predictions and next high/low times are not connected.')
            _link('Open Environment Agency water information', (selected.get('source_url') if selected else None) or tide.get('source_url'))
    render_public_media()
    with st.expander('About these updates'):
        st.caption('Forecasts, water observations and official notices keep their own dates and sources. No port operating status or flood impact is inferred from a water reading or an empty alert feed.')
        st.caption('Peel Ports Group news may concern ports outside Liverpool. Check each port notice for validity.')
        for key in ['weather','tide','weather_warnings','flood_warnings','port_notices','port_news','traffic']:
            section = snapshot[key]
            st.caption(_plain(section['source_name'])+' · '+section['status']+' · '+_when(section.get('checked_at')))
