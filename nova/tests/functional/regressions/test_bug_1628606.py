# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import mock
from nova import test
from nova.tests import fixtures as nova_fixtures
from nova.tests.functional.api import client
from nova.tests.functional import fixtures as func_fixtures
from nova.tests.functional import integrated_helpers
from nova.tests.unit.image import fake


class PostLiveMigrationFail(
    test.TestCase, integrated_helpers.InstanceHelperMixin):
    """Regression test for bug 1628606
    """

    def setUp(self):
        super(PostLiveMigrationFail, self).setUp()
        self.useFixture(nova_fixtures.NeutronFixture(self))
        fake.stub_out_image_service(self)
        self.useFixture(func_fixtures.PlacementFixture())
        self.useFixture(nova_fixtures.HostNameWeigherFixture())

        self.start_service('conductor')
        self.start_service('scheduler')

        api_fixture = self.useFixture(nova_fixtures.OSAPIFixture(
            api_version='v2.1'))

        self.admin_api = api_fixture.admin_api
        self.api = api_fixture.api

        # retrieve image already so we can set api.microversion as latest
        self.image_id = self.api.get_images()[0]['id']

        self.admin_api.microversion = 'latest'
        self.api.microversion = 'latest'

        self.src = self._start_compute(host='host1')
        self.dest = self._start_compute(host='host2')

    @mock.patch(
        'nova.compute.manager.ComputeManager'
        '._post_live_migration_remove_source_vol_connections')
    def test_post_live_migration(self, mock_migration):
        server = self.admin_api.post_server(
            dict(server=self._build_minimal_create_server_request(
                self.api, 'test_post_live_migration', self.image_id,
                networks='none')))
        server = self._wait_for_state_change(self.admin_api, server, 'ACTIVE')
        self.assertEqual(self.src.host, server['OS-EXT-SRV-ATTR:host'])

        error = client.OpenStackApiException(
            "Failed to remove source vol connection post live migration")
        mock_migration.side_effect = error

        server = self._live_migrate(
            server, migration_expected_state='error',
            server_expected_state='ERROR')

        self.assertEqual(self.dest.host, server['OS-EXT-SRV-ATTR:host'])
