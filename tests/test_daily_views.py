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

    def test_everyday_home_has_plain_sections_and_no_technical_controls(self):
        app=self.app()
        self.assertTrue(any(x.value=='Around Liverpool' for x in app.subheader))
        self.assertTrue({'Weather','Tides & water','Travel','Port news','Reminders','My places'} <= {x.label for x in app.tabs})
        labels={x.label for x in app.selectbox}
        self.assertIn('Water level',labels)
        self.assertFalse({'Object type','Relationship','Scenario'} & labels)
        self.assertFalse(any(x.label=='Run model' for x in app.button))

    def test_past_forecast_is_not_used_as_current_outlook(self):
        app=self.app()
        self.assertIn('12',self.metric(app,'Weather outlook').value)
        self.assertNotIn('999',self.metric(app,'Weather outlook').value)
        self.assertTrue(any('Forecast' in x.value for x in app.caption))

    def test_empty_warning_response_does_not_claim_all_clear(self):
        app=self.app()
        self.assertEqual(self.metric(app,'Weather & flood').value,'None listed')
        text=' '.join(str(x.value) for kind in (app.caption,app.markdown,app.info) for x in kind)
        self.assertIn('No items returned',text)
        self.assertNotIn('all clear',text.lower())
        self.assertNotIn('No warnings',text)

    def test_failed_warning_feed_is_not_zero_alerts(self):
        snapshot=daily_fixture()
        snapshot['weather_warnings'].update(status='unavailable',message='Source temporarily unavailable.')
        app=self.app(snapshot)
        self.assertEqual(self.metric(app,'Weather & flood').value,'Check sources')
        self.assertTrue(any('temporarily unavailable' in str(x.value) for x in app.info))

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

    def test_manual_choice_clears_retained_map_selection(self):
        event={'selection':{'objects':{'daily-water':[{'id':'gauge:a'}]}}}
        def chart(deck, **kwargs):
            return event if kwargs['key'].endswith('_0') else {'selection':{'objects':{}}}
        with patch('streamlit.pydeck_chart',side_effect=chart):
            app=self.app()
            next(x for x in app.selectbox if x.label=='Water level').set_value('gauge:b').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['daily_place_id'],'gauge:b')

    def test_place_can_be_saved_without_changing_other_workspaces(self):
        app=self.app(semantic_entity_id='demo:terminal_a',workbench_entity_id='water:old')
        next(x for x in app.button if x.label=='Save this place').click().run()
        self.assertEqual(app.session_state['daily_saved_places'],['gauge:a'])
        self.assertEqual(app.session_state['semantic_entity_id'],'demo:terminal_a')
        self.assertEqual(app.session_state['workbench_entity_id'],'water:old')

    def test_unavailable_tide_has_location_reference_without_fake_reading(self):
        snapshot=daily_fixture()
        snapshot['tide'].update(status='unavailable',series=[],message='Water readings temporarily unavailable.')
        app=self.app(snapshot)
        self.assertEqual(self.metric(app,'Latest water level').value,'Not available')
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
        self.assertEqual(self.metric(app,'Weather outlook').value,'Not available')

    def test_date_only_news_does_not_invent_midnight_or_timezone(self):
        snapshot=daily_fixture()
        snapshot['port_news']['items'][0]['published_at']='2026-11-13'
        app=self.app(snapshot)
        published=[x.value for x in app.caption if 'Published' in x.value]
        self.assertTrue(any('Published 13 Nov 2026' in value for value in published))
        self.assertFalse(any('00:00' in value or 'UTC' in value for value in published))

    def test_forecast_attribution_links_the_data_licence(self):
        app=self.app()
        self.assertTrue(any(x.url=='https://creativecommons.org/licenses/by/4.0/' for x in app.get('link_button')))

    def test_malformed_and_credential_links_are_withheld(self):
        from daily_views import _safe_url
        for value in ['https://[broken','https://user@www.peelports.com/news/',
                      'https://www.peelports.com.evil.example/news/', 'https://www.peelports.com:123/news/']:
            self.assertIsNone(_safe_url(value))


if __name__=='__main__':
    unittest.main()
