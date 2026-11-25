import unittest
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest


def daily_fixture():
    now = pd.Timestamp.now(tz='UTC').floor('min')
    section = lambda name, url: {'status':'available', 'source_name':name, 'source_url':url,
        'checked_at':now.isoformat(), 'message':'', 'items':[]}
    weather = section('MET Norway', 'https://api.met.no/weatherapi/locationforecast/2.0/documentation')
    weather.update(forecast_only=True, updated_at=now.isoformat())
    weather['rows'] = [{'time':(now-pd.Timedelta(hours=2)).isoformat(), 'temp_c':999,
        'wind_m_s':9, 'rain_mm':0, 'description':'Past forecast'}] + [
        {'time':(now+pd.Timedelta(hours=i)).isoformat(), 'temp_c':11+i, 'wind_m_s':4,
         'rain_mm':.2, 'description':'Cloudy'} for i in range(1,7)]
    tide = section('Environment Agency', 'https://environment.data.gov.uk/flood-monitoring')
    tide['series'] = [{'id':sid, 'name':name, 'lat':53.44967, 'lon':-3.01815,
        'unit':unit, 'datum':datum, 'source_url':tide['source_url'],
        'period_seconds':900,
        'station_reference':'E70139' if sid=='gauge:a' else 'E70124',
        'datum_uri':'http://environment.data.gov.uk/flood-monitoring/def/core/datumAOD' if sid=='gauge:a' else 'https://example.org/test/local-datum',
        'rows':[{'time':(now-pd.Timedelta(minutes=15*(2-i))).isoformat(), 'value':base+i/10}
                for i in range(3)]}
        for sid,name,unit,datum,base in [('gauge:a','Liverpool A','mAOD','Ordnance Datum Newlyn',1),
                                      ('gauge:b','Liverpool B','m','Local tide gauge datum',5)]]
    weather_alerts=section('Met Office', 'https://weather.metoffice.gov.uk/guides/rss')
    weather_alerts['feed_updated_at']=(now-pd.Timedelta(days=3)).isoformat()
    flood_alerts=section('Environment Agency', 'https://check-for-flooding.service.gov.uk/alerts-and-warnings')
    notices=section('Peel Ports', 'https://www.peelports.com/marine/our-ports/liverpool/')
    notices.update(status='link_only', checked_at=None, message='Automatic notice feed not connected.')
    news=section('Peel Ports Group', 'https://www.peelports.com/news-articles/')
    news['items']=[{'id':'news:1', 'title':'Port services update', 'url':'https://www.peelports.com/news-articles/port-update/',
        'description':'Latest group news.', 'published_at':now.isoformat(), 'area':'Peel Ports Group',
        'valid_from':None, 'valid_to':None, 'status':'Published', 'severity':None}]
    traffic=section('National Highways', 'https://nationalhighways.co.uk/roads-and-travel/live-travel-updates/')
    traffic.update(status='link_only', checked_at=None, message='Live road incident feed not connected.')
    return {'checked_at':now.isoformat(), 'place':{'name':'Liverpool & Merseyside','lat':53.448,'lon':-3.015},
        'weather':weather, 'tide':tide, 'weather_warnings':weather_alerts, 'flood_warnings':flood_alerts,
        'port_notices':notices, 'port_news':news, 'traffic':traffic}


class DailyViewTests(unittest.TestCase):
    def app(self, snapshot=None, **state):
        app=AppTest.from_string("import streamlit as st\nfrom daily_views import render_daily_home\nrender_daily_home(st.session_state['test_snapshot'])", default_timeout=30)
        app.session_state['test_snapshot']=snapshot or daily_fixture()
        for key,value in state.items():
            app.session_state[key]=value
        app.run()
        self.assertFalse(app.exception)
        return app

    def metric(self, app, label):
        return next(x for x in app.metric if x.label==label)

    def visible_text(self, app):
        def values(node):
            if node.type=='expander':
                return []
            if hasattr(node,'children'):
                return [value for child in node.children.values() for value in values(child)]
            if node.type=='link_button':
                return [node.label]
            return [str(node.value)] if node.type in {'caption','markdown','info','warning'} else []
        return '\n'.join(values(app.main))

    def test_provider_times_are_in_details_and_public_status_stays_visible(self):
        snapshot=daily_fixture()
        now=pd.Timestamp.now(tz='UTC').floor('min')
        snapshot['weather'].update(checked_at=(now-pd.Timedelta(hours=2)).isoformat(),
                                   updated_at=(now-pd.Timedelta(hours=4)).isoformat())
        snapshot['tide']['series'][0]['rows']=[{'time':(now-pd.Timedelta(hours=3)).isoformat(),'value':1.2}]
        snapshot['weather_warnings'].update(checked_at=None)
        snapshot['flood_warnings'].update(status='unavailable',message='Flood source unavailable.')
        snapshot['port_news']['checked_at']=(now-pd.Timedelta(hours=1)).isoformat()
        app=self.app(snapshot)
        text=self.visible_text(app)
        self.assertNotRegex(text,r'Forecast (valid|issued)|· Checked|Feed published|expected readings|forecast wind')
        self.assertIn('Delayed reading',text)
        self.assertIn('Check official source',text)
        details='\n'.join(item.value for item in app.caption)
        self.assertIn('Forecast issued '+(now-pd.Timedelta(hours=4)).strftime('%d %b, %H:%M UTC'),details)
        self.assertIn('MET Norway · Checked '+(now-pd.Timedelta(hours=2)).strftime('%d %b, %H:%M UTC'),details)
        self.assertIn('Observed '+(now-pd.Timedelta(hours=3)).strftime('%d %b, %H:%M UTC'),details)
        self.assertIn('Peel Ports Group · Checked '+(now-pd.Timedelta(hours=1)).strftime('%d %b, %H:%M UTC'),details)
        self.assertEqual(self.metric(app,'Weather & flood').value,'Check sources')

    def test_old_feed_publication_is_shown_without_invalidating_a_fresh_check(self):
        app=self.app()
        text=self.visible_text(app)
        self.assertNotIn('Feed published',text)
        self.assertTrue(any('Feed published' in item.value for item in app.caption))
        self.assertNotIn('feed is stale',text.lower())
        self.assertEqual(self.metric(app,'Weather & flood').value,'None listed')

    def test_official_reminders_precede_six_newer_group_news_items(self):
        snapshot=daily_fixture()
        now=pd.Timestamp.now(tz='UTC')
        snapshot['port_news']['items']=[{**snapshot['port_news']['items'][0], 'id':str(i),'title':'Group story '+str(i)} for i in range(6)]
        snapshot['weather_warnings']['items']=[{'title':'Check regional wind notice',
            'published_at':(now-pd.Timedelta(days=2)).isoformat(), 'valid_from':None,'valid_to':None}]
        app=self.app(snapshot)
        text=self.visible_text(app)
        self.assertIn('Check regional wind notice',text)
        self.assertLess(text.index('Check regional wind notice'),text.index('Group story 0'))
        self.assertIn('Validity unconfirmed',text)
        self.assertNotIn('Active',text)
        self.assertIn('Port notices',text)
        self.assertIn('Road updates',text)
        self.assertEqual(text.count('Group story'),3)

    def test_expired_official_item_is_labelled_historical(self):
        snapshot=daily_fixture()
        now=pd.Timestamp.now(tz='UTC')
        snapshot['weather_warnings']['items']=[{'title':'Earlier rain notice',
            'published_at':(now-pd.Timedelta(hours=3)).isoformat(),
            'valid_from':(now-pd.Timedelta(hours=3)).isoformat(),
            'valid_to':(now-pd.Timedelta(hours=1)).isoformat(),'status':'Actual'}]
        app=self.app(snapshot)
        text=self.visible_text(app)
        self.assertNotIn('Earlier rain notice',text)
        self.assertIn('Met Office · No current advisories listed',text)
        self.assertTrue(any('Earlier rain notice' in str(item.value) for item in app.markdown))
        self.assertNotIn('Active',text)

    def test_local_flood_headline_has_space_alongside_regional_weather(self):
        snapshot=daily_fixture()
        now=pd.Timestamp.now(tz='UTC')
        snapshot['weather_warnings']['items']=[{'title':f'Regional weather notice {index}',
            'valid_from':now-pd.Timedelta(hours=1),'valid_to':now+pd.Timedelta(hours=1)} for index in range(3)]
        snapshot['flood_warnings']['items']=[{'title':'Liverpool flood bulletin'}]
        text=self.visible_text(self.app(snapshot))
        self.assertIn('Liverpool flood bulletin',text)
        self.assertEqual(text.count('Regional weather notice'),2)

    def test_news_source_dates_remain_visible_when_official_reminders_fill_feed(self):
        snapshot=daily_fixture()
        now=pd.Timestamp.now(tz='UTC').floor('min')
        snapshot['port_news']['items'][0]['published_at']='2026-11-10'
        snapshot['weather_warnings']['items']=[{'title':'Official reminder '+str(i)} for i in range(6)]
        app=self.app(snapshot)
        text=self.visible_text(app)
        self.assertNotIn('Peel Ports Group · Checked',text)
        self.assertIn('Port services update',text)
        self.assertIn('Published 10 Nov 2026',text)
        self.assertEqual(text.count('Official reminder'),3)

    def test_explore_readings_is_enabled_only_for_an_exact_water_reference(self):
        app=self.app()
        buttons=[x for x in app.button if x.label=='Explore readings']
        self.assertEqual(len(buttons),1)
        self.assertFalse(buttons[0].disabled)
        snapshot=daily_fixture()
        snapshot['tide']['series'][0].pop('station_reference')
        app=self.app(snapshot)
        self.assertTrue(next(x for x in app.button if x.label=='Explore readings').disabled)

    def test_everyday_home_has_plain_sections_and_no_technical_controls(self):
        app=self.app()
        self.assertTrue(any(x.value=='Around Liverpool' for x in app.subheader))
        self.assertEqual({x.label for x in app.tabs},{'Photos','Video'})
        self.assertEqual({x.label for x in app.metric}, {'Weather outlook','Latest water level','Weather & flood'})
        self.assertTrue({'Weather forecast details','Water observation details'} <= {x.label for x in app.expander})
        labels={x.label for x in app.selectbox}
        self.assertIn('Water level',labels)
        self.assertFalse({'Object type','Relationship','Scenario'} & labels)
        self.assertFalse(any(x.label=='Run model' for x in app.button))

    def test_past_forecast_is_not_used_as_current_outlook(self):
        app=self.app()
        self.assertIn('12',self.metric(app,'Weather outlook').value)
        self.assertNotIn('999',self.metric(app,'Weather outlook').value)
        self.assertTrue(any('Forecast' in x.value for x in app.caption))

    def test_weather_summary_uses_only_actual_points_in_the_next_12_hours(self):
        snapshot=daily_fixture()
        now=pd.Timestamp.now(tz='UTC').floor('min')
        snapshot['weather']['rows'].append({'time':(now+pd.Timedelta(hours=18)).isoformat(),
            'temp_c':600,'wind_m_s':5,'rain_mm':0,'description':'Outside window'})
        app=self.app(snapshot)
        self.assertEqual(self.metric(app,'Weather outlook').value,'12.0–17.0 °C')
        self.assertIn('Partial forecast',self.visible_text(app))
        self.assertNotIn('hourly temperature points',self.visible_text(app))
        self.assertTrue(any('6 of 12 hourly temperature points' in item.value for item in app.caption))

    def test_water_change_requires_complete_same_series_hour(self):
        snapshot=daily_fixture()
        last=pd.Timestamp.now(tz='UTC').floor('min')
        series=snapshot['tide']['series'][0]
        series['rows']=[{'time':(last-pd.Timedelta(minutes=60-i*15)).isoformat(),'value':1+i/10} for i in range(5)]
        app=self.app(snapshot)
        self.assertIn('Rising',self.visible_text(app))
        self.assertNotIn('expected readings',self.visible_text(app))
        self.assertTrue(any('5 of 48 expected readings' in item.value for item in app.caption))
        series['rows'].pop(2)
        self.assertNotIn('Rising',self.visible_text(self.app(snapshot)))

    def test_advisories_report_per_feed_availability(self):
        snapshot=daily_fixture()
        snapshot['flood_warnings'].update(status='unavailable',items=[])
        app=self.app(snapshot)
        text=self.visible_text(app)
        self.assertIn('Met Office · No advisories returned',text)
        self.assertIn('Environment Agency · Check official source',text)

    def test_empty_warning_response_does_not_claim_all_clear(self):
        app=self.app()
        self.assertEqual(self.metric(app,'Weather & flood').value,'None listed')
        text=' '.join(str(x.value) for kind in (app.caption,app.markdown,app.info) for x in kind)
        self.assertIn('No advisories returned',text)
        self.assertNotIn('all clear',text.lower())
        self.assertNotIn('No warnings',text)

    def test_failed_warning_feed_is_not_zero_alerts(self):
        snapshot=daily_fixture()
        snapshot['weather_warnings'].update(status='unavailable',message='Source temporarily unavailable.')
        app=self.app(snapshot)
        self.assertEqual(self.metric(app,'Weather & flood').value,'Check sources')
        self.assertIn('Met Office · Check official source',self.visible_text(app))

    def test_reference_choice_keeps_units_and_values_separate(self):
        app=self.app()
        next(x for x in app.selectbox if x.label=='Water level').set_value('gauge:b').run()
        self.assertFalse(app.exception)
        self.assertEqual(self.metric(app,'Latest water level').value,'5.20 m')
        self.assertTrue(any('Local tide gauge datum' in x.value for x in app.caption))

    def test_native_map_pick_changes_the_same_reference(self):
        event={'selection':{'objects':{'daily-water':[{'id':'gauge:b'}]}}}
        with patch('streamlit.pydeck_chart',return_value=event):
            app=self.app()
        self.assertEqual(app.session_state['daily_place_id'],'gauge:b')
        self.assertEqual(self.metric(app,'Latest water level').value,'5.20 m')

    def test_rain_chart_and_hour_control_use_exact_hour_including_zero(self):
        snapshot=daily_fixture()
        row=snapshot['weather']['rows'][1]
        row['rain_mm']=0.0
        with patch('streamlit.pydeck_chart',return_value={}) as maps, patch('streamlit.plotly_chart',return_value={}) as charts:
            app=self.app(snapshot,daily_weather_variable='Rain')
            first_bar=charts.call_args.args[0].data[0]
            self.assertEqual(first_bar.customdata[0][0],row['time'])
            self.assertEqual(first_bar.x[0]-pd.Timestamp(row['time']),pd.Timedelta(minutes=30))
            app.selectbox(key='daily_rain_hour').set_value(row['time']).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['daily_map_focus'],('rain',row['time']))
        self.assertIn('0.0 mm',self.visible_text(app))
        self.assertIn('selected-forecast-point',[layer.id for layer in maps.call_args.args[0].layers])

    def test_native_rain_selection_uses_custom_interval_not_bar_centre(self):
        import daily_views
        hour='2026-11-25T15:00:00+00:00'
        state={'daily_rain_chart':{'selection':{'points':[{'customdata':[hour,'15:00–16:00 UTC'],
                                                           'x':'2026-11-25T15:30:00+00:00'}]}}}
        with patch.object(daily_views.st,'session_state',state):
            daily_views._choose_rain_bar({})
            self.assertNotIn('daily_map_focus',state)
            daily_views._choose_rain_bar({hour:{'rain_mm':0}})
        self.assertEqual(state['daily_map_focus'],('rain',hour))

    def test_flood_area_lookup_is_lazy_and_draws_the_exact_selected_area(self):
        snapshot=daily_fixture()
        snapshot['flood_warnings']['items']=[{'id':'013WATMEWLW','flood_area_id':'013WATMEWLW',
            'title':'Mersey flood alert','severity':'Flood Alert','severity_level':3}]
        geometry={'type':'FeatureCollection','features':[{'type':'Feature','properties':{},'geometry':{
            'type':'Polygon','coordinates':[[[-3.02,53.44],[-3.01,53.44],[-3.01,53.45],[-3.02,53.44]]]}}]}
        with patch('daily_views.daily_service.load_flood_area_geometry',return_value={'geojson':geometry}) as load, \
             patch('streamlit.pydeck_chart',return_value={}) as maps:
            app=self.app(snapshot)
            load.assert_not_called()
            app.button(key='daily_flood_013WATMEWLW').click().run()
        self.assertFalse(app.exception)
        load.assert_called_once_with('013WATMEWLW')
        self.assertIn('Flood Alert',self.visible_text(app))
        self.assertIn('selected-flood-area',[layer.id for layer in maps.call_args.args[0].layers])

    def test_reference_boundary_remains_reference_when_no_warning_is_listed(self):
        with patch('daily_views.daily_service.load_flood_area_geometry',return_value={'geojson':None}):
            app=self.app()
            app.button(key='daily_flood_reference').click().run()
        self.assertFalse(app.exception)
        self.assertIn('Flood alert reference area',self.visible_text(app))
        self.assertIn('Boundary could not be loaded',self.visible_text(app))
        self.assertNotIn('Flood Alert · Official listing',self.visible_text(app))

    def test_manual_choice_clears_retained_map_selection(self):
        event={'selection':{'objects':{'daily-water':[{'id':'gauge:a'}]}}}
        def chart(deck, **kwargs):
            return event if kwargs['key'].endswith('_0') else {'selection':{'objects':{}}}
        with patch('streamlit.pydeck_chart',side_effect=chart):
            app=self.app()
            next(x for x in app.selectbox if x.label=='Water level').set_value('gauge:b').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['daily_place_id'],'gauge:b')

    def test_overview_does_not_create_saved_places_or_change_other_workspaces(self):
        app=self.app(semantic_entity_id='demo:terminal_a',workbench_entity_id='water:old')
        self.assertFalse({'Save this place','Remove saved place'} & {x.label for x in app.button})
        self.assertNotIn('daily_saved_places',app.session_state)
        self.assertEqual(app.session_state['semantic_entity_id'],'demo:terminal_a')
        self.assertEqual(app.session_state['workbench_entity_id'],'water:old')

    def test_unavailable_tide_displays_separate_observed_archive(self):
        snapshot=daily_fixture()
        snapshot['tide'].update(status='unavailable',series=[],message='Water readings temporarily unavailable.')
        app=self.app(snapshot)
        self.assertNotIn('Latest water level',{x.label for x in app.metric})
        self.assertNotEqual(self.metric(app,'Archived water level').value,'Not available')
        self.assertIn('Environment Agency archive',self.visible_text(app))
        self.assertIn('2025',self.visible_text(app))
        self.assertTrue(any('Location reference' in x.value for x in app.caption))

    def test_untrusted_news_markup_and_non_official_link_are_not_rendered(self):
        snapshot=daily_fixture()
        snapshot['port_news']['items'][0].update(title='<img src=x onerror=alert(1)>News',url='javascript:alert(1)')
        app=self.app(snapshot)
        text=' '.join(str(x.value) for x in app.markdown)
        self.assertNotIn('<img',text)
        self.assertFalse(any(str(x.url).startswith('javascript:') for x in app.get('link_button')))

    def test_missing_forecast_never_displays_a_fabricated_zero(self):
        snapshot=daily_fixture()
        snapshot['weather'].update(status='unavailable',rows=[],message='Forecast unavailable.')
        app=self.app(snapshot)
        self.assertNotIn('Weather outlook',{x.label for x in app.metric})
        self.assertIn('Crosby climate normals',self.visible_text(app))
        self.assertIn('1991–2020',self.visible_text(app))
        self.assertTrue(any(x.label=='Open Met Office forecast' for x in app.get('link_button')))

    def test_date_only_news_does_not_invent_midnight_or_timezone(self):
        snapshot=daily_fixture()
        snapshot['port_news']['items'][0]['published_at']='2026-11-13'
        app=self.app(snapshot)
        published=[x.value for x in app.markdown if 'Published' in x.value]
        self.assertTrue(any('Published 13 Nov 2026' in value for value in published))
        self.assertFalse(any('00:00' in value or 'UTC' in value for value in published))

    def test_updates_appear_once_and_official_notices_remain_reachable(self):
        app=self.app()
        text=' '.join(x.value for x in app.markdown)
        self.assertEqual(text.count('Port services update'),1)
        self.assertTrue(any(x.label=='Port notices' for x in app.get('link_button')))
        self.assertTrue(any('Automatic notice feed not connected' in x.value for x in app.caption))

    def test_only_two_trends_preserve_water_gaps_and_stale_reading(self):
        snapshot=daily_fixture()
        now=pd.Timestamp.now(tz='UTC')
        snapshot['tide']['series'][0]['rows']=[
            {'time':(now-pd.Timedelta(hours=3)).isoformat(),'value':1.0},
            {'time':(now-pd.Timedelta(hours=2,minutes=30)).isoformat(),'value':1.2}]
        with patch('streamlit.plotly_chart',return_value={}) as chart:
            app=self.app(snapshot)
        self.assertEqual([call.kwargs['key'] for call in chart.call_args_list],
                         ['daily_water_mini','daily_weather_mini'])
        water=chart.call_args_list[0].args[0].data[0]
        self.assertFalse(water.connectgaps)
        self.assertTrue(pd.isna(water.y[1]))
        self.assertIn('Delayed reading',self.visible_text(app))

    def test_record_details_keep_forecast_fields_and_observation_reference(self):
        app=self.app()
        forecasts=next(x.value for x in app.dataframe if 'Outlook' in x.value.columns)
        self.assertEqual(set(forecasts.columns),
                         {'Time','Outlook','Temperature (°C)','Wind (m/s)','Rain, next hour (mm)'})
        self.assertEqual(set(forecasts['Outlook']),{'Cloudy'})
        records=[x.value for x in app.dataframe if 'Observed time (UTC)' in x.value.columns]
        self.assertEqual(len(records),1)
        observations=records[0]
        self.assertEqual(list(observations['Water level (mAOD)']),[1.0,1.1,1.2])
        self.assertTrue(any('Ordnance Datum Newlyn' in x.value for x in app.caption))
        self.assertTrue(any('Environment Agency' in x.value and 'Checked' in x.value for x in app.caption))
        self.assertTrue(any(x.label=='Download water observations CSV' for x in app.get('download_button')))

    def test_missing_water_values_remain_missing_in_record_details(self):
        snapshot=daily_fixture()
        snapshot['tide']['series'][0]['rows'][1]['value']=None
        app=self.app(snapshot)
        records=[x.value for x in app.dataframe if 'Observed time (UTC)' in x.value.columns]
        self.assertEqual(len(records),1)
        observations=records[0]
        self.assertTrue(pd.isna(observations['Water level (mAOD)'].iloc[1]))

    def test_water_source_link_keeps_section_fallback(self):
        snapshot=daily_fixture()
        snapshot['tide']['series'][0].pop('source_url')
        app=self.app(snapshot)
        self.assertTrue(any(x.label=='Open Environment Agency water information' and
                            x.url==snapshot['tide']['source_url'] for x in app.get('link_button')))

    def test_forecast_attribution_links_the_data_licence(self):
        app=self.app()
        self.assertTrue(any(x.url=='https://creativecommons.org/licenses/by/4.0/' for x in app.get('link_button')))

    def test_malformed_and_credential_links_are_withheld(self):
        from daily_views import _safe_url
        for value in ['https://[broken','https://user@www.peelports.com/news/',
                      'https://www.peelports.com.evil.example/news/', 'https://www.peelports.com:123/news/']:
            self.assertIsNone(_safe_url(value))

    def test_updates_prioritize_official_reminders_and_filter_by_category(self):
        from daily_views import update_items
        snapshot=daily_fixture()
        snapshot['port_news']['items'][0]['published_at']='2026-11-10'
        snapshot['weather_warnings']['items']=[{'title':'Weather bulletin','published_at':'2026-11-12T10:00:00Z'}]
        snapshot['traffic']['items']=[{'title':'No timestamp'}]
        self.assertEqual([x['title'] for x in update_items(snapshot,'All')],
                         ['Weather bulletin','No timestamp','Port services update'])
        self.assertEqual([x['title'] for x in update_items(snapshot,'Port')],['Port services update'])

    def test_official_road_link_is_visible_and_connection_details_are_collapsed(self):
        app=self.app()
        self.assertIn('Road updates',self.visible_text(app))
        self.assertNotIn('Live road incident feed not connected',self.visible_text(app))
        self.assertTrue(any('Live road incident feed not connected' in x.value for x in app.caption))

    def test_weather_chart_changes_variable_without_adding_more_plots(self):
        app=self.app()
        choices=next(item for item in app.radio if item.label=='Weather variable')
        self.assertEqual(choices.value,'Temperature')
        self.assertEqual(choices.options,['Temperature','Wind','Rain'])
        choices.set_value('Wind').run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.get('plotly_chart')),2)


if __name__=='__main__':
    unittest.main()
