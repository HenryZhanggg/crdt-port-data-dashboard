import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

from test_daily_views import daily_fixture
from test_dashboard_views import observation_fixture


class DailyRoutingTests(unittest.TestCase):
    def app(self, authorised=True):
        st.cache_data.clear()
        daily = patch('daily_service.load_daily_snapshot', return_value=daily_fixture())
        self.daily = daily.start()
        self.addCleanup(daily.stop)
        feeds = patch('api_connectors.fetch_raw_data_bundle', return_value=observation_fixture())
        self.feeds = feeds.start()
        self.addCleanup(feeds.stop)
        app = AppTest.from_file('app.py', default_timeout=30)
        app.session_state['dashboard_authorised'] = authorised
        app.run()
        self.assertFalse(app.exception)
        return app

    def test_default_overview_is_everyday_content_without_technical_controls(self):
        app = self.app()
        self.assertTrue(any('Around Liverpool' in item.value for item in app.subheader))
        self.assertFalse(any(item.label in {'Object type', 'Relationship', 'Scenario', 'Demo period'}
                             for item in list(app.selectbox) + list(app.date_input)))
        self.daily.assert_called_once()
        self.feeds.assert_not_called()

    def test_example_is_available_in_more_views_and_home_returns_to_daily(self):
        app = self.app()
        next(item for item in app.button if item.label == 'Port connections example').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any(item.label == 'Object type' for item in app.selectbox))
        next(item for item in app.button if item.label == 'Home').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any('Around Liverpool' in item.value for item in app.subheader))

    def test_locked_dashboard_never_fetches_daily_sources(self):
        self.app(authorised=False)
        self.daily.assert_not_called()
        self.feeds.assert_not_called()

    def test_monitor_refresh_keeps_the_provider_weather_cache(self):
        from daily_service import load_weather
        app = self.app()
        next(item for item in app.button if item.label == 'Monitor').click().run()
        moment = datetime.now(timezone.utc)
        payload = {'properties':{'meta':{'updated_at':moment.isoformat()},'timeseries':[
            {'time':(moment+timedelta(hours=1)).isoformat(), 'data':{'instant':{'details':
                {'air_temperature':12,'wind_speed':4}}}}]}}
        load_weather.clear()
        with patch('daily_service._download', return_value=SimpleNamespace(json=lambda:payload)) as download:
            load_weather()
            next(item for item in app.button if item.label == 'Refresh data').click().run()
            self.assertFalse(app.exception)
            load_weather()
        self.assertEqual(download.call_count, 1)
        load_weather.clear()


if __name__ == '__main__':
    unittest.main()
