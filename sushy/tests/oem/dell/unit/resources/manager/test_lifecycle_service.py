# Copyright (c) 2020-2021 Dell Inc. or its subsidiaries.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import json
from unittest import mock

from oslotest.base import BaseTestCase

from sushy import exceptions
from sushy.oem.dell.resources.manager import constants
from sushy.oem.dell.resources.manager import lifecycle_service


class DellLCServiceTestCase(BaseTestCase):

    def setUp(self):
        super().setUp()
        self.conn = mock.Mock()
        with open('sushy/tests/oem/dell/unit/json_samples/'
                  'lifecycle_service.json') as f:
            mock_response = self.conn.get.return_value
            mock_response.json.return_value = json.load(f)
            mock_response.status_code = 200

        mock_response = self.conn.post.return_value
        mock_response.status_code = 202
        mock_response.headers.get.return_value = '1'
        self.lifecycle_service = lifecycle_service.DellLCService(
            self.conn,
            '/redfish/v1/Dell/Managers/iDRAC.Embedded.1/DellLCService')

    def test_is_idrac_ready_true(self):
        mock_response = self.conn.post.return_value
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "LCStatus": "Ready",
            "RTStatus": "Ready",
            "ServerStatus": "OutOfPOST",
            "Status": "Ready"
            }
        target_uri = ('/redfish/v1/Dell/Managers/iDRAC.Embedded.1'
                      '/DellLCService'
                      '/Actions/DellLCService.GetRemoteServicesAPIStatus')
        idrac_ready_response = self.lifecycle_service.is_idrac_ready()
        self.conn.post.assert_called_once_with(target_uri, data={})
        self.assertTrue(idrac_ready_response)

    def test_is_idrac_ready_false(self):
        mock_response = self.conn.post.return_value
        mock_response.status_code = 202
        mock_response.json.return_value = {
            "LCStatus": "NotReady",
            "RTStatus": "NotReady",
            "ServerStatus": "OutOfPOST",
            "Status": "NotReady"
            }
        target_uri = ('/redfish/v1/Dell/Managers/iDRAC.Embedded.1'
                      '/DellLCService'
                      '/Actions/DellLCService.GetRemoteServicesAPIStatus')
        idrac_ready_response = self.lifecycle_service.is_idrac_ready()
        self.conn.post.assert_called_once_with(target_uri, data={})
        self.assertFalse(idrac_ready_response)

    def test_is_realtime_ready_true(self):
        mock_response = self.conn.post.return_value
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "LCStatus": "Ready",
            "RTStatus": "Ready",
            "ServerStatus": "OutOfPOST",
            "Status": "Ready"
            }

        self.assertTrue(self.lifecycle_service.is_realtime_ready())
        target_uri = ('/redfish/v1/Dell/Managers/iDRAC.Embedded.1'
                      '/DellLCService'
                      '/Actions/DellLCService.GetRemoteServicesAPIStatus')
        self.conn.post.assert_called_once_with(target_uri, data={})

    def test_is_realtime_ready_false(self):
        mock_response = self.conn.post.return_value
        mock_response.status_code = 202
        mock_response.json.return_value = {
            "LCStatus": "Ready",
            "RTStatus": "NotReady",
            "ServerStatus": "OutOfPOST",
            "Status": "NotReady"
            }

        self.assertFalse(self.lifecycle_service.is_realtime_ready())
        target_uri = ('/redfish/v1/Dell/Managers/iDRAC.Embedded.1'
                      '/DellLCService'
                      '/Actions/DellLCService.GetRemoteServicesAPIStatus')
        self.conn.post.assert_called_once_with(target_uri, data={})

    def test_support_assist_eula_status(self):
        body = {'@Message.ExtendedInfo': [
            {'MessageId': 'IDRAC.2.19.SRV104'}]}
        self.conn.post.return_value.json.return_value = body
        self.assertEqual(
            body, self.lifecycle_service.support_assist_get_eula_status())
        self.conn.post.assert_called_once_with(
            self.lifecycle_service.path
            + '/Actions/DellLCService.SupportAssistGetEULAStatus', data={})

    def test_support_assist_accept_eula(self):
        body = {'@Message.ExtendedInfo': [
            {'MessageId': 'IDRAC.2.19.SRV074'}]}
        self.conn.post.return_value.json.return_value = body
        self.assertEqual(
            body, self.lifecycle_service.support_assist_accept_eula())
        self.conn.post.assert_called_once_with(
            self.lifecycle_service.path
            + '/Actions/DellLCService.SupportAssistAcceptEULA', data={})

    def test_support_assist_eula_empty_response(self):
        for method in (self.lifecycle_service.support_assist_get_eula_status,
                       self.lifecycle_service.support_assist_accept_eula):
            with self.subTest(method=method.__name__):
                response = self.conn.post.return_value
                response.content = b''
                response.json.side_effect = ValueError('Empty response')
                self.assertEqual({}, method())
                response.json.assert_not_called()

    def test_support_assist_eula_invalid_json(self):
        for method in (self.lifecycle_service.support_assist_get_eula_status,
                       self.lifecycle_service.support_assist_accept_eula):
            with self.subTest(method=method.__name__):
                response = self.conn.post.return_value
                response.content = b'not JSON'
                response.json.side_effect = ValueError('Invalid JSON')
                self.assertRaises(exceptions.SushyError, method)

    def test_support_assist_collection_missing(self):
        del self.lifecycle_service.json['Actions'][
            '#DellLCService.SupportAssistCollection']
        self.lifecycle_service._parse_attributes(self.lifecycle_service.json)
        self.assertRaises(exceptions.MissingActionError, self._collect)
        self.conn.post.assert_not_called()

    def _collect(self, **kwargs):
        return self.lifecycle_service.support_assist_collect(
            data_types=[constants.SupportAssistDataType.HARDWARE,
                        constants.SupportAssistDataType.DEBUG],
            filter_data=True,
            share_type=constants.SupportAssistShareType.HTTPS,
            ip_address='192.0.2.1', share_name='diagnostics', **kwargs)

    def test_support_assist_collect(self):
        # iDRAC 10 accepts a job without returning an Id in the body.
        response = self.conn.post.return_value
        response.status_code = 202
        response.headers = {
            'Location': '/redfish/v1/TaskService/TaskMonitors/JID_123'}
        response.json.return_value = {'@Message.ExtendedInfo': [
            {'MessageId': 'Base.1.18.Success'}]}
        self.conn.get.reset_mock()
        monitor = self._collect(username='user', password='secret', port=8443)
        self.assertEqual(response.headers['Location'],
                         monitor.task_monitor_uri)
        self.assertTrue(monitor.is_processing)
        self.conn.get.assert_not_called()
        self.conn.post.assert_called_once_with(
            self.lifecycle_service.path
            + '/Actions/DellLCService.SupportAssistCollection',
            data={'DataSelectorArrayIn': ['HWData', 'DebugLogs'],
                  'Filter': 'Yes', 'ShareType': 'HTTPS',
                  'IPAddress': '192.0.2.1', 'ShareName': 'diagnostics',
                  'Transmit': 'No', 'UserName': 'user', 'Password': 'secret',
                  'PortNumber': 8443})

    def test_support_assist_collect_missing_location(self):
        response = self.conn.post.return_value
        response.headers = {}
        response.json.return_value = {}
        exc = self.assertRaises(exceptions.MissingHeaderError, self._collect)
        self.assertIn('Location', str(exc))
        self.assertIn('may have been started', str(exc))

    def test_support_assist_collect_preserves_monitor_location(self):
        response = self.conn.post.return_value
        response.status_code = 202
        response.headers = {
            'Location': '/redfish/v1/TaskService/TaskMonitors/JID_123'}
        response.json.return_value = {
            '@odata.id': '/redfish/v1/TaskService/Tasks/JID_123',
            'Id': 'JID_123', 'Name': 'SupportAssist Collection',
            'TaskState': 'Running',
        }
        self.conn.get.reset_mock()
        monitor = self._collect()
        self.assertEqual(response.headers['Location'],
                         monitor.task_monitor_uri)
        self.conn.get.assert_not_called()

    def test_support_assist_collect_task_location(self):
        response = self.conn.post.return_value
        response.status_code = 202
        response.headers = {
            'Location': '/redfish/v1/TaskService/Tasks/JID_123'}
        response.json.return_value = {
            'Id': 'JID_123', 'Name': 'SupportAssist Collection',
            'TaskState': 'Running',
        }
        self.conn.get.reset_mock()
        monitor = self._collect()
        self.assertEqual(response.headers['Location'],
                         monitor.task_monitor_uri)
        self.assertTrue(monitor.is_processing)
        self.conn.get.assert_not_called()

    def test_support_assist_collect_rejected(self):
        self.conn.post.side_effect = exceptions.SushyError('EULA not accepted')
        self.assertRaises(exceptions.SushyError, self._collect)
        self.assertEqual(1, self.conn.post.call_count)

    def test_support_assist_collect_job_completes(self):
        # iDRAC reports a finished job as a plain 200 with a job body
        # rather than a Task, so polling must end without a Task.
        job_uri = ('/redfish/v1/Managers/iDRAC.Embedded.1/Oem/Dell/Jobs/'
                   'JID_123')
        response = self.conn.post.return_value
        response.status_code = 202
        response.headers = {'Location': job_uri}
        response.json.return_value = {}
        monitor = self._collect()
        self.assertTrue(monitor.is_processing)

        self.conn.get.reset_mock()
        done = self.conn.get.return_value
        done.status_code = 200
        done.json.return_value = {'JobState': 'Completed',
                                  'PercentComplete': 100}

        self.assertFalse(monitor.check_is_processing)
        self.conn.get.assert_called_once_with(path=job_uri)
        self.assertIsNone(monitor.task)
        self.assertIs(done, monitor.response)
