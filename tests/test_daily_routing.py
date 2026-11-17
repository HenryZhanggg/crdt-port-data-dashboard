import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

from test_daily_views import daily_fixture
from test_dashboard_views import observation_fixture


class DailyRoutingTests(unittest.TestCase):
    def app(self, authorised=True, snapshot=None, bundle=None, **state):
        st.cache_data.clear()
        daily = patch('daily_service.load_daily_snapshot', return_value=snapshot or daily_fixture())
        self.daily = daily.start()
        self.addCleanup(daily.stop)
        feeds = patch('api_connectors.fetch_raw_data_bundle', return_value=observation_fixture() if bundle is None else bundle)
        self.feeds = feeds.start()
        self.addCleanup(feeds.stop)
        app = AppTest.from_file('app.py', default_timeout=30)
        app.session_state['dashboard_authorised'] = authorised
        for key,value in state.items():
            app.session_state[key]=value
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

    def test_monitor_opens_network_and_overview_returns_to_daily(self):
        app = self.app()
        next(item for item in app.button if item.label == 'Monitor').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any(item.label == 'Object type' for item in app.selectbox))
        self.feeds.assert_not_called()
        next(item for item in app.button if item.label == 'Overview').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any('Around Liverpool' in item.value for item in app.subheader))

    def test_locked_dashboard_never_fetches_daily_sources(self):
        self.app(authorised=False)
        self.daily.assert_not_called()
        self.feeds.assert_not_called()

    def test_lock_clears_collected_integration_data_and_controls(self):
        app=self.app(dashboard_page='Data',data_workspace_tab='Integration',
            integration_loaded={'signature':'previous request','bundle':{'private':'session records'}},
            integration_freshness=45)
        next(item for item in app.button if item.label=='Lock dashboard').click().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.session_state['dashboard_authorised'])
        self.assertFalse(any(key.startswith('integration_') for key in app.session_state.filtered_state))
        self.feeds.assert_not_called()

    def test_integration_controls_and_collection_survive_workspace_navigation(self):
        app=self.app(dashboard_page='Data',data_workspace_tab='Integration')
        next(item for item in app.button if item.label=='Load selected records').click().run()
        self.assertFalse(app.exception)
        next(item for item in app.number_input if item.label=='Maximum observation age (minutes)').set_value(45).run()
        next(item for item in app.button if item.label=='Monitor').click().run()
        next(item for item in app.button if item.label=='Data').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['integration_freshness'],45)
        self.assertIn('integration_loaded',app.session_state)
        self.assertTrue(any(item.label=='Download integration report ZIP' for item in app.get('download_button')))

    def test_monitor_refresh_keeps_the_provider_weather_cache(self):
        from daily_service import load_weather
        app = self.app()
        next(item for item in app.button if item.label == 'Monitor').click().run()
        next(item for item in app.radio if item.label == 'Data view').set_value('Connected observations').run()
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

    def test_only_three_workspace_buttons_replace_the_old_navigation_trees(self):
        app=self.app()
        self.assertTrue({'Overview','Monitor','Data'} <= {item.label for item in app.button})
        self.assertFalse(any(item.label in {'Workspace','View'} for item in app.radio))
        self.assertFalse(any(item.label in {'More','Observations','WP modules'} for item in app.button))

    def test_data_catalogue_has_no_global_observation_dates_and_is_feed_free(self):
        app=self.app()
        next(item for item in app.button if item.label=='Data').click().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.date_input)
        self.feeds.assert_not_called()
        self.assertTrue(any(item.label=='Data source' for item in app.selectbox))

    def test_water_refresh_keeps_unrelated_port_statistics_cache(self):
        app=self.app()
        next(x for x in app.button if x.label=='Data').click().run()
        next(x for x in app.selectbox if x.label=='Data source').set_value('HS001').run()
        next(x for x in app.checkbox if x.label=='Browse connected records').check().run()
        next(x for x in app.button if x.label=='Monitor').click().run()
        next(x for x in app.radio if x.label=='Data view').set_value('Connected observations').run()
        next(x for x in app.multiselect if x.label=='Observation sources').set_value(['water_level']).run()
        next(x for x in app.button if x.label=='Refresh data').click().run()
        next(x for x in app.button if x.label=='Data').click().run()
        requested=[call.kwargs.get('sources') for call in self.feeds.call_args_list]
        self.assertEqual(requested.count(('dft',)),1)

    def test_selected_source_status_does_not_include_unrequested_deferred_connectors(self):
        import pandas as pd
        from api_connectors import status_row
        app=self.app()
        bundle=observation_fixture()
        bundle['status']=pd.concat([bundle['status'],pd.DataFrame([status_row(
            'private_sensor','Unrequested private feed','Partner','requires_partner_agreement',0,
            'https://example.org','Not requested')])],ignore_index=True)
        self.feeds.return_value=bundle
        next(x for x in app.button if x.label=='Data').click().run()
        next(x for x in app.selectbox if x.label=='Data source').set_value('HS004').run()
        next(x for x in app.checkbox if x.label=='Browse connected records').check().run()
        self.assertFalse(app.exception)
        statuses=[x.value for x in app.dataframe if 'status' in x.value]
        self.assertTrue(statuses)
        self.assertFalse(any(frame['status'].eq('requires_partner_agreement').any() for frame in statuses))

    def test_overview_handoff_keeps_measurement_reference_across_monitor_data_and_back(self):
        app=self.app()
        next(x for x in app.button if x.label=='Explore readings').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['dashboard_page'],'Monitor')
        self.assertEqual(app.session_state['workbench_entity_id'],'water:E70139')
        reference='E70139|mAOD|http://environment.data.gov.uk/flood-monitoring/def/core/datumAOD'
        self.assertEqual(app.session_state['workbench_reference'],reference)
        next(x for x in app.button if x.label=='Check data quality').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['dashboard_page'],'Data')
        self.assertEqual(app.session_state['data_quality_scope'],'Water levels')
        next(x for x in app.button if x.label=='Monitor').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['workbench_reference'],reference)
        self.assertEqual(next(x for x in app.radio if x.label=='Data view').value,'Connected observations')
        next(x for x in app.button if x.label=='Overview').click().run()
        self.assertEqual(app.session_state['daily_place_id'],'gauge:a')

    def test_overview_handoff_does_not_silently_substitute_a_missing_datum(self):
        snapshot=daily_fixture()
        snapshot['tide']['series'][0]['datum_uri']='datum:not-returned'
        app=self.app(snapshot=snapshot)
        next(x for x in app.button if x.label=='Explore readings').click().run()
        self.assertFalse(app.exception)
        self.assertFalse(any(x.label=='Download selected observations' for x in app.get('download_button')))
        text=' '.join(str(x.value) for x in list(app.warning)+list(app.info))
        self.assertTrue('reference' in text.lower() or 'requested' in text.lower(),text)

    def test_handoff_does_not_query_water_for_a_partner_without_water_navigation(self):
        app=self.app()
        next(x for x in app.selectbox if x.label=='Partner').set_value('Terminal operator').run()
        next(x for x in app.button if x.label=='Explore readings').click().run()
        self.assertFalse(app.exception)
        self.feeds.assert_not_called()


if __name__ == '__main__':
    unittest.main()
