"""Visual previews of source tables without changing their download rows."""

import pandas as pd
import plotly.express as px
import streamlit as st

from monitoring_views import chart_style


LOCATIONS = {
    'ea_stations': ('lat', 'lon'),
    'webtris_sites': ('lat', 'lon'),
    'naptan': ('Latitude', 'Longitude'),
}
TIMELINES = {
    'port_traffic': ('year', 'tonnage_thousand_tonnes', 'Freight (thousand tonnes)', 'port'),
    'ship_arrivals': ('Year', 'Number', 'Ship arrivals', 'Ship Type'),
    'weekly_shipping': ('week_ending', 'liverpool_visits', 'Liverpool ship visits', 'metric'),
    'webtris_daily': ('timestamp', 'Total Volume', 'Traffic volume (vehicles)', 'site_id'),
    'water_levels': ('date_time', 'value', 'Water level', None),
    'ea_liverpool_archive': ('dateTime', 'value', 'Archived water level', 'Provider measurement'),
}
WATER_REFERENCE = ['station_reference', 'unit', 'datum', 'datum_uri', 'measure_uri', 'parameter', 'qualifier']
DATE_LABELS = {'year': 'Year', 'Year': 'Year', 'week_ending': 'Week ending',
               'timestamp': 'Source time (timezone unverified)', 'date_time': 'Observation time',
               'dateTime': 'Archive observation time (UTC)'}


def returned_period(table, records):
    if table in LOCATIONS:
        return 'Reference locations · no observation period'
    if table in TIMELINES:
        time = TIMELINES[table][0]
    elif table == 'ea_readings':
        time = 'date_time'
    else:
        return None
    if time not in records:
        return None
    if time in ('year', 'Year'):
        values = pd.to_numeric(records[time], errors='coerce').dropna()
        if not values.empty:
            return f"Returned years · {values.min():g} to {values.max():g}"
    else:
        # Display source calendar dates. In particular, don't reinterpret WebTRIS local timestamps.
        dates = records[time].astype(str).str.extract(r'^(\d{4}-\d{2}-\d{2})')[0]
        days = pd.to_datetime(dates, format='%Y-%m-%d', errors='coerce').dropna()
        if not days.empty:
            return f"Returned dates · {days.min():%d %b %Y} to {days.max():%d %b %Y}"
    return None


def _plot_timeline(table, records):
    time, value, label, series = TIMELINES[table]
    if not {time, value}.issubset(records.columns):
        return False
    rows = records.copy()
    facets = None
    if table == 'ea_liverpool_archive' and 'measure' in rows:
        rows[series] = rows['measure'].str.rsplit('/', n=1).str[-1]
        facets = 'Native reference'
        rows[facets] = rows[series].str.rsplit('-', n=1).str[-1]
    if table == 'water_levels':
        ref = [field for field in ('unit', 'datum_uri', 'datum') if field in rows]
        if len(rows[ref].drop_duplicates()) > 1:
            st.caption('The sample shows measurements with different units or vertical references.')
            return False
        series = 'Measurement'
        fields = [field for field in WATER_REFERENCE if field in rows]
        if fields:
            rows[series] = rows[fields].fillna('').astype(str).agg(' · '.join, axis=1)
        if 'unit' in rows and pd.notna(rows['unit'].iloc[0]) and rows['unit'].iloc[0]:
            label += f" ({rows['unit'].iloc[0]})"
    rows[value] = pd.to_numeric(rows[value], errors='coerce')
    if time in ('year', 'Year'):
        rows[time] = pd.to_numeric(rows[time], errors='coerce')
    else:
        rows[time] = pd.to_datetime(rows[time], format='mixed', utc=table=='ea_liverpool_archive', errors='coerce')
    rows = rows.dropna(subset=[time, value])
    if rows.empty:
        return False
    fig = px.scatter(rows, x=time, y=value, color=series if series in rows else None, facet_row=facets,
                     labels={time: DATE_LABELS[time], value: label, 'metric': 'Visit category'})
    if time in ('year', 'Year'):
        fig.update_xaxes(tickformat='d')
    if facets:
        fig.update_yaxes(matches=None, title_text=None)
        fig.for_each_annotation(lambda item: item.update(text=item.text.partition('=')[2]))
        fig.update_layout(showlegend=False, hovermode='closest')
        st.caption('Each point retains its provider measurement. Native references use separate axes.')
    st.plotly_chart(chart_style(fig, 390 if facets else 300), width='stretch', key=f'data_preview_{table}')
    return True


def render_table_preview(table, records):
    visual = False
    if table in LOCATIONS:
        latitude, longitude = LOCATIONS[table]
        if {latitude, longitude}.issubset(records.columns):
            coordinates = records[[latitude, longitude]].apply(pd.to_numeric, errors='coerce')
            points = coordinates.loc[coordinates[latitude].between(-90, 90) &
                                     coordinates[longitude].between(-180, 180)]
            if not points.empty:
                st.caption('Reference locations · up to 1,500 points with valid coordinates')
                st.map(points.head(1500), latitude=latitude, longitude=longitude, height=300)
                visual = True
    elif table in TIMELINES:
        visual = _plot_timeline(table, records)
    elif table == 'ea_readings' and 'parameter' in records:
        counts = records['parameter'].value_counts().rename_axis('Parameter').reset_index(name='Readings')
        if not counts.empty:
            st.plotly_chart(chart_style(px.bar(counts, x='Parameter', y='Readings'), 250),
                            width='stretch', key='data_preview_ea_readings')
            visual = True
    with st.expander('Sample records', expanded=not visual):
        st.caption('Up to 200 rows from the downloadable table.')
        st.dataframe(records.head(200), hide_index=True, width='stretch')
