import importlib
import json
import unittest
from unittest.mock import patch

import test_daily_routing as routing
import test_monitor_workspace as monitor


class ConnectedWorkflowTests(unittest.TestCase):
    app=routing.DailyRoutingTests.app

    def test_data_navigation_has_explicit_label_and_default_integration(self):
        app=self.app()
        nav=next((x for x in app.button if x.label=='Data & Integration'),None)
        self.assertIsNotNone(nav)
        nav.click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['dashboard_page'],'Data')
        self.assertEqual(app.session_state['data_workspace_tab'],'Integration')
        self.feeds.assert_not_called()

    def test_common_mapping_editor_survives_navigation_and_lock_clears_it(self):
        app=self.app(dashboard_page='Data')
        next(x for x in app.button if x.label=='Load selected records').click().run()
        editor=next(x for x in app.dataframe if 'common_entity_id' in x.value)
        state=app._tree.get_widget_states()
        state.widgets.add(id=editor.proto.id,string_value=json.dumps({'edited_rows':{
            '0':{'common_entity_id':'port:shared','common_concept':'urn:level','confirmed':True}},
            'added_rows':[],'deleted_rows':[]}))
        app._run(state);self.assertFalse(app.exception)
        next(x for x in app.button if x.label=='Monitor').click().run()
        next(x for x in app.button if x.label=='Data & Integration').click().run()
        self.assertFalse(app.exception)
        editor=next(x for x in app.dataframe if 'common_entity_id' in x.value)
        self.assertEqual(editor.value.iloc[0]['common_entity_id'],'port:shared')
        next(x for x in app.button if x.label=='Lock dashboard').click().run()
        self.assertFalse(app.exception)
        self.assertFalse(any(x.startswith('integration_') for x in app.session_state.filtered_state))

    def test_monitor_integration_handoff_keeps_exact_selected_reference(self):
        case=monitor.MonitorWorkspaceTests();app=case.connected()
        button=next((x for x in app.button if x.label=='Integrate selected data'),None)
        self.assertIsNotNone(button)
        button.click().run();self.assertFalse(app.exception)
        self.assertEqual(app.session_state['dashboard_page'],'Data')
        self.assertEqual(app.session_state['data_workspace_tab'],'Integration')
        self.assertEqual(app.session_state['integration_input_kind'],'Connected sources')
        context=app.session_state['data_handoff']
        self.assertEqual(context['entity_id'],app.session_state['workbench_entity_id'])
        self.assertEqual(context['start'],app.session_state['monitor_start'])

    def test_monitor_raw_permission_is_required_for_integration_action(self):
        case=monitor.MonitorWorkspaceTests();app=case.connected(allowed_views={'weather','gis'})
        self.assertFalse(any(x.label=='Integrate selected data' for x in app.button))

    def test_overview_context_stays_current_with_retained_historical_selection(self):
        links=importlib.import_module('workspace_links')
        self.assertTrue(hasattr(links,'workspace_context_summary'))
        state={'dashboard_page':'Overview','monitor_handoff':{'source':'water_level','entity_id':'water:A',
               'station_reference':'A','unit':'m','datum_uri':'datum:aod','start':'2020-01-01','end':'2020-01-02'}}
        with patch.object(links.st,'session_state',state):summary=links.workspace_context_summary()
        self.assertEqual(summary['mode'],'Current overview')
        self.assertNotEqual(summary.get('start'),'2020-01-01')

    def test_data_context_does_not_fall_back_to_cleared_monitor_selection(self):
        links=importlib.import_module('workspace_links')
        self.assertTrue(hasattr(links,'workspace_context_summary'))
        with patch.object(links.st,'session_state',{'dashboard_page':'Data','data_workspace_tab':'Integration',
             'monitor_handoff':{'source':'webtris','entity_id':'traffic:old','start':'2020-01-01','end':'2020-01-02'}}):
            summary=links.workspace_context_summary()
        self.assertFalse(summary and summary.get('label')=='traffic:old')
