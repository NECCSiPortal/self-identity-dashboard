#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.
#
#

from mox3.mox import IsA

from django.conf import settings

from openstack_dashboard import api
from openstack_dashboard.api import keystone
from openstack_dashboard.test import helpers as test

from keystoneclient import client

from nec_portal import api as nec_api
from nec_portal.api import project_identity  # noqa


class ProjectIdentityApiTests(test.APITestCase):

    def setUp(self):
        super(ProjectIdentityApiTests, self).setUp()

        # Store the original clients
        self._original_keystoneclient = nec_api.project_identity.keystoneclient
        self._original_api_keystone = api.keystone

        # Replace the clients with our stubs.
        nec_api.project_identity.keystoneclient = \
            lambda request: self.stub_keystoneclient()
        api.keystone = lambda request: self.stub_api_keystone()

    def tearDown(self):
        super(ProjectIdentityApiTests, self).tearDown()

        nec_api.project_identity.keystoneclient = self._original_keystoneclient
        api.keystone = self._original_api_keystone

    def stub_keystoneclient(self):
        if not hasattr(self, "keystoneclient"):
            self.mox.StubOutWithMock(client, "Client")
            self.keystoneclient = self.mox.CreateMock(client.Client)
        return self.keystoneclient

    def stub_api_keystone(self):
        if not hasattr(self, "keystone"):
            self.mox.StubOutWithMock(keystone, 'keystone_can_edit_user')
            self.keystone = self.mox.CreateMock(keystone)
        return self.keystone

    def test_get_default_domain(self):

        keystoneclient = self.stub_keystoneclient()
        self.mox.StubOutWithMock(project_identity, 'get_keystone_client')
        project_identity.get_keystone_client().AndReturn(keystoneclient)

        domain = self.domains.get(id="1")

        keystoneclient.domains = self.mox.CreateMockAnything()
        keystoneclient.domains.get(IsA("str")).AndReturn(domain)

        self.mox.ReplayAll()

        setattr(self.request.user, 'user_domain_id', domain.id)

        res = project_identity.get_default_domain(self.request)
        self.assertItemsEqual(res["name"], "test_domain")

    def test_domain_get(self):

        keystoneclient = self.stub_keystoneclient()
        self.mox.StubOutWithMock(project_identity, 'get_keystone_client')
        project_identity.get_keystone_client().AndReturn(keystoneclient)

        domain_id = 'domain_id_0000-1111-2222'
        domain = self.domains.get(id="1")

        keystoneclient.domains = self.mox.CreateMockAnything()
        keystoneclient.domains.get(domain_id).AndReturn(domain)

        self.mox.ReplayAll()
        res = project_identity.domain_get(self.request, domain_id)
        self.assertItemsEqual(res.id, domain.id)

    def test_project_user_list(self):

        keystoneclient = self.stub_keystoneclient()
        self.mox.StubOutWithMock(project_identity, "get_keystone_client")
        project_identity.get_keystone_client().AndReturn(keystoneclient)

        project_id = "project_id_0000-1111-2222"
        users = self.users.list()

        return_obj = IdentityObj()
        return_obj.add('user', {"id": "2"})
        project_users = [return_obj]

        keystoneclient.role_assignments = self.mox.CreateMockAnything()
        keystoneclient.role_assignments.list(project=project_id). \
            AndReturn(project_users)

        keystoneclient.users = self.mox.CreateMockAnything()
        keystoneclient.users.list().AndReturn(users)

        self.mox.ReplayAll()
        res = project_identity.project_user_list(project_id)
        self.assertEqual(len(res), 1)
        self.assertItemsEqual(res[0].id, "2")

    def test_role_assignments_list(self):

        keystoneclient = self.stub_keystoneclient()
        self.mox.StubOutWithMock(project_identity, 'get_keystone_client')
        project_identity.get_keystone_client().AndReturn(keystoneclient)

        project_id = 'project_id_0000-1111-2222'
        users = self.users.list()

        keystoneclient.role_assignments = self.mox.CreateMockAnything()
        keystoneclient.role_assignments.list(
            project=project_id, domain=None, effective=False,
            group=None, role=None, user=None).AndReturn(users)

        self.mox.ReplayAll()
        res = project_identity.role_assignments_list(self.request, project_id)
        self.assertEqual(len(res), 5)
        self.assertItemsEqual(res[0].id, users[0].id)
        self.assertItemsEqual(res[1].id, users[1].id)

    def test_get_default_role(self):

        keystoneclient = self.stub_keystoneclient()
        self.mox.StubOutWithMock(project_identity, 'get_keystone_client')
        project_identity.get_keystone_client().AndReturn(keystoneclient)

        roles = self.roles.list()

        keystoneclient.roles = self.mox.CreateMockAnything()
        keystoneclient.roles.list().AndReturn(roles)

        self.mox.ReplayAll()
        res = project_identity.get_default_role(self.request)
        self.assertItemsEqual(res.name,
                              settings.OPENSTACK_KEYSTONE_DEFAULT_ROLE)

    def test_role_list(self):

        keystoneclient = self.stub_keystoneclient()
        self.mox.StubOutWithMock(project_identity, 'get_keystone_client')
        project_identity.get_keystone_client().AndReturn(keystoneclient)

        roles = self.roles.list()

        keystoneclient.roles = self.mox.CreateMockAnything()
        keystoneclient.roles.list().AndReturn(roles)

        self.mox.ReplayAll()
        res = project_identity.role_list(self.request)
        self.assertEqual(len(res), 2)
        self.assertItemsEqual(res[0].id, roles[0].id)

    def test_roles_for_user(self):

        keystoneclient = self.stub_keystoneclient()
        self.mox.StubOutWithMock(project_identity, 'get_keystone_client')
        project_identity.get_keystone_client().AndReturn(keystoneclient)

        user_id = 'user_id_0000-1111-2222'
        roles = self.roles.list()

        keystoneclient.roles = self.mox.CreateMockAnything()
        keystoneclient.roles.list(user=user_id,
                                  domain=None,
                                  project=None).AndReturn(roles)

        self.mox.ReplayAll()
        res = project_identity.roles_for_user(self.request, user_id)
        self.assertEqual(len(res), 2)
        self.assertItemsEqual(res[0].id, roles[0].id)

    def test_users_role_list(self):

        keystoneclient = self.stub_keystoneclient()
        self.mox.StubOutWithMock(project_identity, 'get_keystone_client')
        project_identity.get_keystone_client().AndReturn(keystoneclient)

        user_id = 'user_id_0000-1111-2222'
        roles = self.roles.list()

        keystoneclient.roles = self.mox.CreateMockAnything()
        keystoneclient.roles.list(user=user_id,
                                  project=IsA("str")).AndReturn(roles)

        self.mox.ReplayAll()
        res = project_identity.users_role_list(self.request, user_id)
        self.assertEqual(len(res), 2)
        self.assertItemsEqual(res[0].id, roles[0].id)

    def test_user_get(self):

        keystoneclient = self.stub_keystoneclient()
        self.mox.StubOutWithMock(project_identity, 'get_keystone_client')
        project_identity.get_keystone_client().AndReturn(keystoneclient)

        user = self.users.get(id="1")

        keystoneclient.users = self.mox.CreateMockAnything()
        keystoneclient.users.get(user=user.id).AndReturn(user)

        self.mox.ReplayAll()
        res = project_identity.user_get(self.request, user.id)
        self.assertItemsEqual(res.id, user.id)

    def test_user_create(self):

        keystoneclient = self.stub_keystoneclient()
        self.mox.StubOutWithMock(project_identity, 'get_keystone_client')
        project_identity.get_keystone_client().AndReturn(keystoneclient)

        user = self.users.get(id="1")

        keystoneclient.users = self.mox.CreateMockAnything()
        keystoneclient.users.create(user.name, password=user.password,
                                    email=user.email, project=user.project_id,
                                    enabled=user.enabled,
                                    domain=user.domain_id).AndReturn(user)

        self.mox.ReplayAll()
        res = project_identity.user_create(self.request, name=user.name,
                                           password=user.password,
                                           email=user.email,
                                           project=user.project_id,
                                           enabled=user.enabled,
                                           domain=user.domain_id)
        self.assertItemsEqual(res.id, user.id)

    def test_user_list(self):

        keystoneclient = self.stub_keystoneclient()
        self.mox.StubOutWithMock(project_identity, 'get_keystone_client')
        project_identity.get_keystone_client().AndReturn(keystoneclient)

        user = self.users.list()
        project_id = "project_id_0000-1111-2222"

        keystoneclient.users = self.mox.CreateMockAnything()
        keystoneclient.users.list(project=project_id, domain=None,
                                  group=None).AndReturn(user)

        self.mox.ReplayAll()
        res = project_identity.user_list(self.request, project=project_id)
        self.assertEqual(len(res), 5)
        self.assertItemsEqual(res[0].id, user[0].id)

    def test_user_update(self):

        keystoneclient = self.stub_keystoneclient()
        self.mox.StubOutWithMock(project_identity, 'get_keystone_client')
        project_identity.get_keystone_client().AndReturn(keystoneclient)

        user = self.users.get(id="1")

        keystoneclient.users = self.mox.CreateMockAnything()
        keystoneclient.users.update(user.id, email=user.email).AndReturn(user)

        api.keystone = self.stub_api_keystone()
        api.keystone.keystone_can_edit_user().AndReturn(True)

        self.mox.ReplayAll()
        project_identity.user_update(self.request, user=user.id,
                                     email=user.email)

    def test_user_delete(self):

        keystoneclient = self.stub_keystoneclient()
        self.mox.StubOutWithMock(project_identity, 'get_keystone_client')
        project_identity.get_keystone_client().AndReturn(keystoneclient)

        user = self.users.get(id="1")

        keystoneclient.users = self.mox.CreateMockAnything()
        keystoneclient.users.delete(user.id)

        self.mox.ReplayAll()
        project_identity.user_delete(self.request, user.id)

    def test_user_update_project(self):

        keystoneclient = self.stub_keystoneclient()
        self.mox.StubOutWithMock(project_identity, 'get_keystone_client')
        project_identity.get_keystone_client().AndReturn(keystoneclient)

        user = self.users.get(id="1")
        project_id = "project_id_0000-1111-2222"

        keystoneclient.users = self.mox.CreateMockAnything()
        keystoneclient.users.update(user.id,
                                    project=project_id).AndReturn(user)

        self.mox.ReplayAll()
        res = project_identity.user_update_project(self.request, user.id,
                                                   project_id)
        self.assertItemsEqual(res.id, user.id)

    def test_add_project_user_role(self):

        keystoneclient = self.stub_keystoneclient()
        self.mox.StubOutWithMock(project_identity, 'get_keystone_client')
        project_identity.get_keystone_client().AndReturn(keystoneclient)

        role = self.roles.get(id="1")
        project_id = "project_id_0000-1111-2222"
        user_id = "user_id_0000-1111-2222"

        keystoneclient.roles = self.mox.CreateMockAnything()
        keystoneclient.roles.grant(role.id, user=user_id, project=project_id,
                                   group=None).AndReturn(role)

        self.mox.ReplayAll()
        res = project_identity.add_project_user_role(self.request,
                                                     role=role.id,
                                                     user=user_id,
                                                     project=project_id)
        self.assertItemsEqual(res.id, role.id)

    def test_remove_project_user_role(self):

        keystoneclient = self.stub_keystoneclient()
        self.mox.StubOutWithMock(project_identity, 'get_keystone_client')
        project_identity.get_keystone_client().AndReturn(keystoneclient)

        role = self.roles.get(id="1")
        project_id = "project_id_0000-1111-2222"
        user_id = "user_id_0000-1111-2222"

        keystoneclient.roles = self.mox.CreateMockAnything()
        keystoneclient.roles.revoke(role.id, user=user_id,
                                    project=project_id,
                                    domain=None).AndReturn(role)

        self.mox.ReplayAll()
        res = project_identity.remove_project_user_role(self.request,
                                                        project_id,
                                                        user_id, role.id)
        self.assertItemsEqual(res.id, role.id)

    def test_remove_project_user(self):

        keystoneclient = self.stub_keystoneclient()
        self.mox.StubOutWithMock(project_identity, 'get_keystone_client')
        project_identity.get_keystone_client().AndReturn(keystoneclient)

        roles = self.roles.list()
        project_id = "project_id_0000-1111-2222"
        user_id = "user_id_0000-1111-2222"

        project_identity.get_keystone_client().AndReturn(keystoneclient)
        keystoneclient.roles = self.mox.CreateMockAnything()
        keystoneclient.roles.list(user=user_id, domain=None,
                                  project=project_id).AndReturn(roles)

        for role in roles:
            project_identity.get_keystone_client().AndReturn(keystoneclient)
            keystoneclient.roles.revoke(role.id, user=user_id,
                                        project=project_id,
                                        domain=None).AndReturn(role)

        self.mox.ReplayAll()
        project_identity.remove_project_user(self.request,
                                             project=project_id,
                                             user=user_id)

    def test_project_get(self):

        keystoneclient = self.stub_keystoneclient()
        self.mox.StubOutWithMock(project_identity, 'get_keystone_client')
        project_identity.get_keystone_client().AndReturn(keystoneclient)

        tenant = self.tenants.get(id="1")

        keystoneclient.projects = self.mox.CreateMockAnything()
        keystoneclient.projects.get(tenant.id,
                                    parents_as_list=True).AndReturn(tenant)

        self.mox.ReplayAll()
        res = project_identity.project_get(self.request, tenant.id,
                                           parents=True)
        self.assertItemsEqual(res.id, tenant.id)

    def test_project_create(self):

        keystoneclient = self.stub_keystoneclient()
        self.mox.StubOutWithMock(project_identity, 'get_keystone_client')
        project_identity.get_keystone_client().AndReturn(keystoneclient)

        tenant = self.tenants.get(id="1")

        keystoneclient.projects = self.mox.CreateMockAnything()
        keystoneclient.projects.create(tenant.name, tenant.domain_id,
                                       description=tenant.description,
                                       enabled=tenant.enabled). \
            AndReturn(tenant)

        self.mox.ReplayAll()
        res = project_identity.project_create(self.request, tenant.name,
                                              description=tenant.description,
                                              enabled=tenant.enabled,
                                              domain=tenant.domain_id)
        self.assertItemsEqual(res.id, tenant.id)

    def test_project_delete(self):

        keystoneclient = self.stub_keystoneclient()
        self.mox.StubOutWithMock(project_identity, 'get_keystone_client')
        project_identity.get_keystone_client().AndReturn(keystoneclient)

        tenant = self.tenants.get(id="1")

        keystoneclient.projects = self.mox.CreateMockAnything()
        keystoneclient.projects.delete(tenant.id)

        self.mox.ReplayAll()
        project_identity.project_delete(self.request, tenant.id)

    def test_project_list(self):

        keystoneclient = self.stub_keystoneclient()
        self.mox.StubOutWithMock(project_identity, 'get_keystone_client')
        project_identity.get_keystone_client().AndReturn(keystoneclient)

        tenants = self.tenants.list()
        user_id = "user_id_0000-1111-2222"
        domain_id = "domain_id_0000-1111-2222"

        keystoneclient.projects = self.mox.CreateMockAnything()
        keystoneclient.projects.list(domain=domain_id,
                                     user=user_id).AndReturn(tenants)

        self.mox.ReplayAll()
        res = project_identity.project_list(self.request, domain=domain_id,
                                            user=user_id)
        self.assertEqual(len(res[0]), 3)
        self.assertEqual(res[0][0].id, tenants[0].id)
        self.assertFalse(res[1])

    def test_project_update(self):

        keystoneclient = self.stub_keystoneclient()
        self.mox.StubOutWithMock(project_identity, 'get_keystone_client')
        project_identity.get_keystone_client().AndReturn(keystoneclient)

        tenant = self.tenants.get(id="1")

        keystoneclient.projects = self.mox.CreateMockAnything()
        keystoneclient.projects.update(tenant.id,
                                       name=tenant.name,
                                       description=tenant.description,
                                       enabled=tenant.enabled,
                                       domain=tenant.domain_id). \
            AndReturn(tenant)

        self.mox.ReplayAll()
        res = project_identity.project_update(self.request, tenant.id,
                                              name=tenant.name,
                                              description=tenant.description,
                                              enabled=tenant.enabled,
                                              domain=tenant.domain_id)
        self.assertItemsEqual(res.id, tenant.id)

    def test_group_get(self):

        keystoneclient = self.stub_keystoneclient()
        self.mox.StubOutWithMock(project_identity, 'get_keystone_client')
        project_identity.get_keystone_client().AndReturn(keystoneclient)

        group = self.groups.get(id="1")

        keystoneclient.groups = self.mox.CreateMockAnything()
        keystoneclient.groups.get(group.id).AndReturn(group)

        self.mox.ReplayAll()
        res = project_identity.group_get(self.request, group.id)
        self.assertItemsEqual(res.id, group.id)

    def test_group_user_list(self):

        keystoneclient = self.stub_keystoneclient()
        self.mox.StubOutWithMock(project_identity, 'get_keystone_client')
        project_identity.get_keystone_client().AndReturn(keystoneclient)

        users = self.users.list()[1:3]
        role_assignments = self.role_assignments.list()
        project_id = "project_id_0000-1111-2222"
        group_id = "group_id_0000-1111-2222"

        keystoneclient.users = self.mox.CreateMockAnything()
        keystoneclient.users.list(group=group_id).AndReturn(users)

        keystoneclient.role_assignments = self.mox.CreateMockAnything()
        keystoneclient.role_assignments.list(project=project_id). \
            AndReturn(role_assignments)

        self.mox.ReplayAll()
        res = project_identity.group_user_list(project=project_id,
                                               group=group_id)
        self.assertEqual(len(res), 2)
        self.assertItemsEqual(res[0].id, users[0].id)
        self.assertItemsEqual(res[1].id, users[1].id)

    def test_get_project_users_roles(self):

        keystoneclient = self.stub_keystoneclient()
        self.mox.StubOutWithMock(project_identity, 'get_keystone_client')
        project_identity.get_keystone_client().AndReturn(keystoneclient)

        project_id = 'project_id_0000-1111-2222'
        role_assignments = self.role_assignments.list()[0:4]

        keystoneclient.role_assignments = self.mox.CreateMockAnything()
        keystoneclient.role_assignments.list(project=project_id, domain=None,
                                             effective=False, group=None,
                                             role=None, user=None). \
            AndReturn(role_assignments)

        self.mox.ReplayAll()
        res = project_identity.get_project_users_roles(self.request,
                                                       project_id)
        self.assertEqual(len(res), 3)
        for role_assignment in role_assignments:
            if not hasattr(role_assignment, 'user'):
                continue
            user_id = role_assignment.user['id']
            role_id = role_assignment.role['id']
            self.assertItemsEqual(res[user_id], role_id)

    def test_roles_for_group(self):

        keystoneclient = self.stub_keystoneclient()
        self.mox.StubOutWithMock(project_identity, 'get_keystone_client')
        project_identity.get_keystone_client().AndReturn(keystoneclient)

        roles = self.roles.list()
        project_id = "project_id_0000-1111-2222"
        group_id = "group_id_0000-1111-2222"

        keystoneclient.roles = self.mox.CreateMockAnything()
        keystoneclient.roles.list(group=group_id,
                                  project=project_id).AndReturn(roles)

        self.mox.ReplayAll()
        res = project_identity.roles_for_group(self.request, group_id,
                                               project_id)
        self.assertEqual(len(res), 2)
        self.assertItemsEqual(res[0].id, roles[0].id)

    def test_add_group_role(self):

        keystoneclient = self.stub_keystoneclient()
        self.mox.StubOutWithMock(project_identity, 'get_keystone_client')
        project_identity.get_keystone_client().AndReturn(keystoneclient)

        role = self.roles.get(id="1")
        project_id = "project_id_0000-1111-2222"
        group_id = "group_id_0000-1111-2222"

        keystoneclient.roles = self.mox.CreateMockAnything()
        keystoneclient.roles.grant(role=role.id, group=group_id,
                                   project=project_id).AndReturn(role)

        self.mox.ReplayAll()
        res = project_identity.add_group_role(self.request, role.id,
                                              group_id, project_id)
        self.assertItemsEqual(res.id, role.id)

    def test_remove_group_role(self):

        keystoneclient = self.stub_keystoneclient()
        self.mox.StubOutWithMock(project_identity, 'get_keystone_client')
        project_identity.get_keystone_client().AndReturn(keystoneclient)

        role = self.roles.get(id="1")
        project_id = "project_id_0000-1111-2222"
        group_id = "group_id_0000-1111-2222"

        keystoneclient.roles = self.mox.CreateMockAnything()
        keystoneclient.roles.revoke(role=role.id, group=group_id,
                                    project=project_id).AndReturn(role)

        self.mox.ReplayAll()
        res = project_identity.remove_group_role(self.request, role.id,
                                                 group_id, project_id)
        self.assertItemsEqual(res.id, role.id)

    def test_project_group_list(self):

        keystoneclient = self.stub_keystoneclient()
        self.mox.StubOutWithMock(project_identity, 'get_keystone_client')
        project_identity.get_keystone_client().AndReturn(keystoneclient)

        role_assignments = self.role_assignments.list()[0:4]
        groups = self.groups.list()
        project_id = "project_id_0000-1111-2222"
        group_id = "group_id_0000-1111-2222"
        domain_id = "domain_id_0000-1111-2222"

        keystoneclient.role_assignments = self.mox.CreateMockAnything()
        keystoneclient.role_assignments.list(project=project_id) \
            .AndReturn(role_assignments)

        keystoneclient.groups = self.mox.CreateMockAnything()
        keystoneclient.groups.list(domain=domain_id).AndReturn(groups)

        self.mox.ReplayAll()
        res = project_identity.project_group_list(project=project_id,
                                                  domain=domain_id,
                                                  group=group_id)
        self.assertEqual(len(res), 1)
        self.assertItemsEqual(res[0].id, groups[0].id)

    def test_group_create(self):

        keystoneclient = self.stub_keystoneclient()
        self.mox.StubOutWithMock(project_identity, 'get_keystone_client')
        project_identity.get_keystone_client().AndReturn(keystoneclient)

        group = self.groups.get(id="1")

        keystoneclient.groups = self.mox.CreateMockAnything()
        keystoneclient.groups.create(domain=group.domain_id, name=group.name,
                                     description=group.description) \
            .AndReturn(group)

        self.mox.ReplayAll()
        res = project_identity.group_create(self.request, group.domain_id,
                                            group.name,
                                            description=group.description)
        self.assertItemsEqual(res.id, group.id)

    def test_group_update(self):

        keystoneclient = self.stub_keystoneclient()
        self.mox.StubOutWithMock(project_identity, 'get_keystone_client')
        project_identity.get_keystone_client().AndReturn(keystoneclient)

        group = self.groups.get(id="1")

        keystoneclient.groups = self.mox.CreateMockAnything()
        keystoneclient.groups.update(group=group.id, name=group.name,
                                     description=group.description) \
            .AndReturn(group)

        self.mox.ReplayAll()
        res = project_identity.group_update(self.request, group.id,
                                            name=group.name,
                                            description=group.description)
        self.assertItemsEqual(res.id, group.id)

    def test_add_group_user(self):

        keystoneclient = self.stub_keystoneclient()
        self.mox.StubOutWithMock(project_identity, 'get_keystone_client')
        project_identity.get_keystone_client().AndReturn(keystoneclient)

        user = self.users.get(id="1")
        group_id = "group_id_0000-1111-2222"

        keystoneclient.users = self.mox.CreateMockAnything()
        keystoneclient.users.add_to_group(group=group_id, user=user.id) \
            .AndReturn(user)

        self.mox.ReplayAll()
        res = project_identity.add_group_user(self.request, group_id, user.id)
        self.assertItemsEqual(res.id, user.id)

    def test_remove_group_user(self):

        keystoneclient = self.stub_keystoneclient()
        self.mox.StubOutWithMock(project_identity, 'get_keystone_client')
        project_identity.get_keystone_client().AndReturn(keystoneclient)

        user = self.users.get(id="1")
        group_id = "group_id_0000-1111-2222"

        keystoneclient.users = self.mox.CreateMockAnything()
        keystoneclient.users.remove_from_group(group=group_id, user=user.id) \
            .AndReturn(user)

        self.mox.ReplayAll()
        res = project_identity.remove_group_user(self.request, group_id,
                                                 user.id)
        self.assertItemsEqual(res.id, user.id)

    def test_group_delete(self):

        keystoneclient = self.stub_keystoneclient()
        self.mox.StubOutWithMock(project_identity, 'get_keystone_client')
        project_identity.get_keystone_client().AndReturn(keystoneclient)

        self.groups.get(id="1")
        group_id = "group_id_0000-1111-2222"

        keystoneclient.groups = self.mox.CreateMockAnything()
        keystoneclient.groups.delete(group_id)

        self.mox.ReplayAll()
        project_identity.group_delete(self.request, group_id)


class IdentityObj(object):

    def add(self, key, value):
        self.__dict__[key] = value
