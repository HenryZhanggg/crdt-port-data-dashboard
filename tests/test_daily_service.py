import importlib.util
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pandas as pd
import requests


NOW = datetime(2026, 11, 14, 12, 30, tzinfo=timezone.utc)


class DailyServiceTests(unittest.TestCase):
    def service(self):
        self.assertIsNotNone(importlib.util.find_spec('daily_service'))
        import daily_service
        return daily_service

    def test_weather_is_forecast_with_only_upcoming_valid_points(self):
        service = self.service()
        def point(time, temperature, wind=5):
            return {'time':time,'data':{'instant':{'details':{'air_temperature':temperature,'wind_speed':wind}},
                'next_1_hours':{'summary':{'symbol_code':'partlycloudy_day'},'details':{'precipitation_amount':0}}}}
        payload = {'properties':{'meta':{'updated_at':'2026-11-14T11:00:00Z'},'timeseries':[
            point('2026-11-14T12:00:00Z',11),point('2026-11-14T13:00:00Z',12),
            point('2026-11-14T14:00:00Z',None,float('inf'))]}}
        weather = service.parse_weather(payload, now=NOW)
        self.assertTrue(weather['forecast_only'])
        self.assertEqual([row['time'] for row in weather['rows']],['2026-11-14T13:00:00+00:00','2026-11-14T14:00:00+00:00'])
        self.assertEqual(weather['rows'][0]['rain_mm'],0)
        self.assertIsNone(weather['rows'][1]['temp_c'])
        self.assertIsNone(weather['rows'][1]['wind_m_s'])
        self.assertIn('CC BY 4.0',weather['attribution'])

    def test_weather_with_no_remaining_forecast_is_unavailable(self):
        service = self.service()
        with self.assertRaises(ValueError):
            service.parse_weather({'properties':{'timeseries':[]}},now=NOW)

    def test_empty_rss_is_successful_check_not_all_clear_and_preserves_feed_date(self):
        service = self.service()
        result = service.parse_warning_feed('<rss><channel><title>Warnings</title>'
            '<pubDate>Tue, 10 Nov 2026 10:00:51 GMT</pubDate></channel></rss>')
        self.assertEqual(result['status'],'available')
        self.assertEqual(result['items'],[])
        self.assertEqual(result['feed_updated_at'],'2026-11-10T10:00:51+00:00')
        self.assertNotIn('all clear',result['message'].lower())

    def test_rss_content_is_plain_text_and_does_not_infer_validity_from_publication(self):
        service = self.service()
        result = service.parse_warning_feed('<rss><channel><title>Warnings</title><item>'
            '<guid>w1</guid><title>Rain warning</title><link>javascript:alert(1)</link>'
            '<description>&lt;b&gt;Check local conditions&lt;/b&gt;</description>'
            '<pubDate>Sat, 14 Nov 2026 12:00:00 GMT</pubDate></item></channel></rss>')
        item = result['items'][0]
        self.assertEqual(item['description'],'Check local conditions')
        self.assertTrue(item['url'].startswith('https://'))
        self.assertIsNone(item['valid_from'])
        self.assertIsNone(item['valid_to'])
        self.assertNotEqual(item['status'].lower(),'active')

    def test_atom_feed_preserves_explicit_time_and_severity(self):
        service = self.service()
        result = service.parse_warning_feed('<feed xmlns="http://www.w3.org/2005/Atom" '
            'xmlns:cap="urn:oasis:names:tc:emergency:cap:1.2"><title>Warnings</title><updated>2026-11-14T12:00:00Z</updated>'
            '<entry><id>x</id><title>Wind</title><link href="https://www.metoffice.gov.uk/weather/warnings"/>'
            '<cap:onset>2026-11-14T14:00:00Z</cap:onset><cap:expires>2026-11-14T18:00:00Z</cap:expires>'
            '<cap:severity>Severe</cap:severity></entry></feed>')
        self.assertEqual(result['items'][0]['severity'],'Severe')
        self.assertEqual(result['items'][0]['valid_to'],'2026-11-14T18:00:00+00:00')

    def test_invalid_feed_is_not_interpreted_as_zero_warnings(self):
        service = self.service()
        with self.assertRaises(ValueError):
            service.parse_warning_feed('<html><title>Unavailable</title></html>')

    def test_flood_items_keep_official_severity_and_search_scope(self):
        service = self.service()
        result = service.parse_flood_warnings({'items':[{'floodAreaID':'A','description':'Estuary area',
            'severity':'Flood Alert','severityLevel':3,'timeRaised':'2026-11-14T10:00:00Z',
            'message':'Flooding possible','floodArea':{'@id':'http://environment.data.gov.uk/flood-monitoring/id/floodAreas/A'}}]})
        self.assertEqual(result['items'][0]['severity'],'Flood Alert')
        self.assertEqual(result['items'][0]['severity_level'],3)
        self.assertIn('30 km',result['message'])
        self.assertNotIn('asset',result['items'][0])
        with self.assertRaises(ValueError):
            service.parse_flood_warnings({'message':'service error'})

    def test_tide_keeps_references_separate_and_missing_values_missing(self):
        service = self.service()
        frame = pd.DataFrame([
            {'station_reference':'A','station_label':'Liverpool','unit':'m','datum':'Local','datum_uri':'local:A',
             'date_time':'2026-11-14T12:00:00Z','value':0,'lat':53.4,'lon':-3.0},
            {'station_reference':'A','station_label':'Liverpool','unit':'m','datum':'Local','datum_uri':'local:A',
             'date_time':'2026-11-14T12:15:00Z','value':None,'lat':53.4,'lon':-3.0},
            {'station_reference':'A','station_label':'Liverpool','unit':'mAOD','datum':'AOD','datum_uri':'datum:AOD',
             'date_time':'2026-11-14T12:00:00Z','value':4.2,'lat':53.4,'lon':-3.0},
            {'station_reference':'A','station_label':'Liverpool','unit':'m','datum':'Local','datum_uri':'local:A',
             'date_time':'bad','value':10,'lat':53.4,'lon':-3.0},
        ])
        series = service.normalise_tide(frame)
        self.assertEqual(len(series),2)
        local = next(row for row in series if row['unit']=='m')
        self.assertEqual(len(local['rows']),2)
        self.assertEqual(local['rows'][0]['value'],0)
        self.assertIsNone(local['rows'][1]['value'])
        self.assertEqual(local.get('station_reference'),'A')
        self.assertEqual(local['id'],'water:A|m|local:A')
        self.assertIsNone(local['period_seconds'])
        self.assertNotEqual(series[0]['id'],series[1]['id'])

    def test_tide_load_keeps_provider_measures_and_declared_periods_separate(self):
        service = self.service()
        first = 'http://environment.data.gov.uk/flood-monitoring/id/measures/E70139-anglian'
        second = 'http://environment.data.gov.uk/flood-monitoring/id/measures/E70139-north_west'
        reference = {'datumType':'http://environment.data.gov.uk/flood-monitoring/def/core/datumAOD',
                     'unitName':'mAOD'}
        station = {'stationReference':'E70139','lat':53.448,'long':-3.015,'measures':[
            {**reference,'@id':first,'period':900}, {**reference,'@id':second}]}
        reading = {'dateTime':'2026-11-14T12:00:00Z'}
        observations = [{**reading,'measure':first,'value':4.2}, {**reading,'measure':second,'value':5.2},
            {'dateTime':'2026-11-14T12:30:00Z','measure':second,'value':5.5}]
        context = Mock()
        session = Mock()
        context.__enter__ = Mock(return_value=session)
        context.__exit__ = Mock(return_value=False)
        session.get.side_effect = [Mock(**{'json.return_value':{'items':[station]}}),
                                   Mock(**{'json.return_value':{'items':observations}})]
        service.load_tide.clear()
        self.addCleanup(service.load_tide.clear)
        with patch('daily_service.request_session',return_value=context):
            tide = service.load_tide()
        self.assertEqual(tide['status'],'available')
        self.assertEqual(len(tide['series']),2)
        series = {row['measure_uri']:row for row in tide['series']}
        self.assertEqual(set(series),{first,second})
        self.assertNotEqual(series[first]['id'],series[second]['id'])
        self.assertEqual([row['value'] for row in series[first]['rows']],[4.2])
        self.assertEqual([row['value'] for row in series[second]['rows']],[5.2,5.5])
        self.assertEqual(series[first]['period_seconds'],900)
        self.assertIsNone(series[second]['period_seconds'])

    def test_tide_conflicting_or_invalid_periods_are_unverified(self):
        service = self.service()
        common = {'station_reference':'A','unit':'m','datum_uri':'datum:local',
                  'measure_uri':'http://example.org/measure/a','value':1}
        for periods in ((900,1800),(0,0),(2.5,2.5)):
            with self.subTest(periods=periods):
                frame = pd.DataFrame([{**common,'period_seconds':period,'date_time':instant}
                    for period,instant in zip(periods,('2026-11-14T12:00:00Z','2026-11-14T12:15:00Z'))])
                self.assertIsNone(service.normalise_tide(frame)[0]['period_seconds'])

    def test_http_failure_is_unavailable_not_empty_success(self):
        service = self.service()
        service.load_weather_warnings.clear()
        with patch('daily_service.requests.get',side_effect=requests.Timeout):
            result = service.load_weather_warnings()
        service.load_weather_warnings.clear()
        self.assertEqual(result['status'],'unavailable')
        self.assertIsNotNone(result['checked_at'])

    def test_tide_adapter_failure_is_independent(self):
        service = self.service()
        service.load_tide.clear()
        with patch('daily_service.fetch_liverpool_tide_water_levels',side_effect=requests.Timeout):
            result = service.load_tide()
        service.load_tide.clear()
        self.assertEqual(result['status'],'unavailable')
        self.assertEqual(result['series'],[])

    def test_tide_adapter_uses_shorter_timeouts_than_legacy_pages(self):
        service = self.service()
        service.load_tide.clear()
        context = Mock()
        session = context.__enter__ = Mock(return_value=Mock())
        context.__exit__ = Mock(return_value=False)
        raw = session.return_value
        def adapter(bounded):
            bounded.get('https://environment.data.gov.uk/test',timeout=45)
            return pd.DataFrame(),{}
        with patch('daily_service.request_session',return_value=context),\
             patch('daily_service.fetch_liverpool_tide_water_levels',side_effect=adapter):
            service.load_tide()
        service.load_tide.clear()
        timeout = raw.get.call_args.kwargs['timeout']
        self.assertIsInstance(timeout,tuple)
        self.assertLessEqual(timeout[1],8)

    def test_conflicting_same_time_tide_values_are_missing(self):
        service = self.service()
        common={'station_reference':'A','unit':'m','datum':'Local','datum_uri':'datum:local',
                'date_time':'2026-11-14T12:00:00Z','lat':53.4,'lon':-3.0}
        result=service.normalise_tide(pd.DataFrame([{**common,'value':1},{**common,'value':2}]))
        self.assertEqual(len(result[0]['rows']),1)
        self.assertIsNone(result[0]['rows'][0]['value'])

    def test_snapshot_retains_source_check_times_and_link_only_sections(self):
        service = self.service()
        result = {'status':'available','checked_at':'2026-11-14T12:00:00+00:00','items':[]}
        with patch('daily_service.load_weather',return_value=result),patch('daily_service.load_tide',return_value=result),\
             patch('daily_service.load_weather_warnings',return_value=result),patch('daily_service.load_flood_warnings',return_value=result),\
             patch('daily_service.load_port_news',return_value=result):
            snapshot = service.load_daily_snapshot()
        self.assertEqual(snapshot['checked_at'],result['checked_at'])
        self.assertEqual(snapshot['weather']['checked_at'],result['checked_at'])
        for name in ('port_notices','traffic'):
            self.assertEqual(snapshot[name]['status'],'link_only')
            self.assertIsNone(snapshot[name]['checked_at'])
            self.assertTrue(snapshot[name]['items'])
        self.assertEqual(snapshot['place']['name'],'Liverpool & Merseyside')

    def test_news_keeps_date_precision_group_scope_and_deduplicates_cards(self):
        service = self.service()
        card = '<a href="/news-articles/customer-update/"><span class="eyebrow">13 Nov 2026</span><h5>Customer update</h5></a>'
        other = '<a href="https://www.metoffice.gov.uk/news-articles/story/"><h5>Other publisher</h5></a>'
        result = service.parse_port_news('<a href="/news-articles/">News</a>'+card+card+other)
        self.assertEqual(len(result['items']),1)
        item = result['items'][0]
        self.assertEqual(item['published_at'],'2026-11-13')
        self.assertEqual(item['area'],'Peel Ports Group')
        self.assertEqual(item['status'],'Published news')
        self.assertIsNone(item['valid_to'])

    def test_snapshot_drops_forecast_points_that_expired_while_source_was_cached(self):
        service = self.service()
        now = datetime.now(timezone.utc)
        from datetime import timedelta
        base = {'status':'available','checked_at':'2026-11-14T12:00:00+00:00','items':[]}
        weather = {**base,'forecast_only':True,'rows':[
            {'time':(now-timedelta(hours=1)).isoformat(),'temp_c':10},
            {'time':(now+timedelta(hours=1)).isoformat(),'temp_c':11}]}
        with patch('daily_service.load_weather',return_value=weather),patch('daily_service.load_tide',return_value=base),\
             patch('daily_service.load_weather_warnings',return_value=base),patch('daily_service.load_flood_warnings',return_value=base),\
             patch('daily_service.load_port_news',return_value=base):
            snapshot = service.load_daily_snapshot()
        self.assertEqual(len(snapshot['weather']['rows']),1)
        self.assertEqual(snapshot['weather']['rows'][0]['temp_c'],11)
        self.assertEqual(snapshot['weather']['checked_at'],base['checked_at'])
        self.assertEqual(len(weather['rows']),2)


if __name__ == '__main__':
    unittest.main()
