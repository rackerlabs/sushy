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

import logging

from sushy import exceptions
from sushy.resources import base
from sushy.resources import common
from sushy.taskmonitor import TaskMonitor

LOG = logging.getLogger(__name__)


class ActionsField(base.CompositeField):
    remote_service_api_status = common.ActionField(
        "#DellLCService.GetRemoteServicesAPIStatus")
    support_assist_get_eula_status = common.ActionField(
        '#DellLCService.SupportAssistGetEULAStatus')
    support_assist_accept_eula = common.ActionField(
        '#DellLCService.SupportAssistAcceptEULA')
    support_assist_register = common.ActionField(
        '#DellLCService.SupportAssistRegister')
    support_assist_collection = common.ActionField(
        '#DellLCService.SupportAssistCollection')


class DellLCService(base.ResourceBase):

    _actions = ActionsField('Actions')
    _OK_STATUS_CODE = 200
    _READY_STATUS = 'Ready'
    identity = base.Field('Id', required=True)

    def __init__(self, connector, identity, redfish_version=None,
                 registries=None):
        """A class representing a DellLCService.

        :param connector: A Connector instance
        :param identity: The identity of the DellLCService resource
        :param redfish_version: The version of Redfish. Used to construct
            the object according to schema of the given version.
        :param registries: Dict of Redfish Message Registry objects to be
            used in any resource that needs registries to parse messages.
        """
        super().__init__(
            connector, identity, redfish_version, registries)

    def _is_remote_service_api_status_ready(self, status_field):
        """Checks remote service status field

        :param status_field: Status field to check, e.g., LCStatus, RTStatus
        :returns: True if response returned and status field is Ready,
            otherwise False.
        """
        target_uri = self._actions.remote_service_api_status.target_uri
        response = self._conn.post(target_uri, data={})
        if response.status_code != self._OK_STATUS_CODE:
            return False
        data = response.json()
        return data[status_field] == self._READY_STATUS

    def is_idrac_ready(self):
        """Indicates if the iDRAC is ready to accept commands.

        :returns: A boolean value True/False based on remote service api status
            response.
        """
        LOG.debug('Checking to see if the iDRAC is ready...')
        return self._is_remote_service_api_status_ready('LCStatus')

    def is_realtime_ready(self):
        """Indicates if real-time operations are ready to be accepted.

        :returns: True if ready to accept real-time operations, otherwise
            false.
        """
        LOG.debug('Checking to see if the real-time operations are ready...')
        return self._is_remote_service_api_status_ready('RTStatus')

    def _support_assist_action(self, field, name):
        action = getattr(self._actions, field)
        if not action or not action.target_uri:
            raise exceptions.MissingActionError(
                action=name, resource=self.path)
        return action.target_uri

    def support_assist_get_eula_status(self):
        """Return Dell's EULA status, including ExtendedInfo messages.

        Dell identifies accepted/not accepted EULAs with message codes
        SRV074/SRV104 respectively, rather than a boolean property.
        """
        target = self._support_assist_action(
            'support_assist_get_eula_status', 'SupportAssistGetEULAStatus')
        return self._conn.post(target, data={}).json()

    def support_assist_accept_eula(self):
        """Explicitly accept the EULA and return Dell's confirmation."""
        target = self._support_assist_action(
            'support_assist_accept_eula', 'SupportAssistAcceptEULA')
        return self._conn.post(target, data={}).json()

    def support_assist_register(self, registration):
        """Register SupportAssist using Dell contact/address fields.

        :param registration: Dictionary of SupportAssistRegister parameters.
            Registration requires iSM and is absent on newer firmware.
            This method does not enable OS-to-BMC passthrough or accept EULA.
        :returns: Dell's registration response.
        :raises: MissingActionError if registration is not advertised.
        """
        target = self._support_assist_action(
            'support_assist_register', 'SupportAssistRegister')
        return self._conn.post(target, data=registration).json()

    def support_assist_collect(self, *, data_types, filter_data, share_type,
                               ip_address, share_name, username=None,
                               password=None, port=None):
        """Start an offline SupportAssist collection to a network share.

        :param data_types: Iterable of SupportAssistDataType enum values.
        :param filter_data: Boolean selecting Dell's PII filtering.
        :param share_type: SupportAssistShareType enum value.
        :param ip_address: Destination server address.
        :param share_name: Destination share/directory path.
        :param username: Optional share username.
        :param password: Optional share password.
        :param port: Optional destination port (HTTP/HTTPS).
        :returns: Standard TaskMonitor, reusable with get_task_monitor(),
            without waiting for completion.
        :raises: MissingActionError if collection is not advertised.
        """
        target = self._support_assist_action(
            'support_assist_collection', 'SupportAssistCollection')
        payload = {
            'DataSelectorArrayIn': [item.value for item in data_types],
            'Filter': 'Yes' if filter_data else 'No',
            'ShareType': share_type.value,
            'IPAddress': ip_address,
            'ShareName': share_name,
            'Transmit': 'No',
        }
        for key, value in (('UserName', username), ('Password', password),
                           ('PortNumber', port)):
            if value is not None:
                payload[key] = value
        response = self._conn.post(target, data=payload)
        monitor_uri = response.headers.get('Location')
        if not monitor_uri:
            raise exceptions.MissingHeaderError(
                target_uri=target, header='Location')
        return TaskMonitor(
            self._conn, monitor_uri, response=response,
            redfish_version=self.redfish_version,
            registries=self.registries)
