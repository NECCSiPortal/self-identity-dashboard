# Copyright 2013 Hewlett-Packard Development Company, L.P.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from mox3.mox import IgnoreArg
from mox3.mox import IsA

from django.core.urlresolvers import reverse
from django import http

from openstack_dashboard.test import helpers as test

from nec_portal.api import project_identity
from nec_portal.dashboards.project.groups import constants

GROUPS_INDEX_URL = reverse(constants.GROUPS_INDEX_URL)
GROUP_CREATE_URL = reverse(constants.GROUPS_CREATE_URL)
GROUP_UPDATE_URL = reverse(constants.GROUPS_UPDATE_URL, args=[1])
GROUP_MANAGE_URL = reverse(constants.GROUPS_MANAGE_URL, args=[1])
GROUP_ADD_MEMBER_URL = reverse(constants.GROUPS_ADD_MEMBER_URL, args=[1])
GROUP_MODIFY_ROLES_URL = reverse(constants.GROUPS_MODIFY_ROLES_URL, args=[1])


class GroupsViewTests(test.BaseAdminViewTests):
    def _get_domain_id(self):
        return self.request.session.get('domain_context', None)

    def _get_groups(self, domain_id):
        if not domain_id:
            groups = self.groups.list()
        else:
            groups = [group for group in self.groups.list()
                      if group.domain_id == domain_id]
        return groups

    @test.create_stubs({project_identity: ('project_group_list',)})
    def test_index(self):
        domain_id = self._get_domain_id()
        groups = self._get_groups(domain_id)

        project_identity.project_group_list(project=IsA('str'),
                                            domain=domain_id) \
            .AndReturn(groups)

        self.mox.ReplayAll()

        res = self.client.get(GROUPS_INDEX_URL)

        self.assertTemplateUsed(res, constants.GROUPS_INDEX_VIEW_TEMPLATE)
        self.assertItemsEqual(res.context['table'].data, groups)
        if domain_id:
            for group in res.context['table'].data:
                self.assertItemsEqual(group.domain_id, domain_id)

        self.assertContains(res, 'Create Group')
        self.assertContains(res, 'Edit')
        self.assertContains(res, 'Delete Group')

    @test.create_stubs({project_identity: ('group_create',
                                           'role_list')})
    def test_create(self):
        domain_id = self._get_domain_id()
        group = self.groups.get(id="1")

        project_identity.group_create(IsA(http.HttpRequest),
                                      description=group.description,
                                      domain_id=domain_id,
                                      name=group.name).AndReturn(group)
        project_identity.role_list(IsA(http.HttpRequest)).\
            AndReturn(self.users.list())
        self.mox.ReplayAll()

        formData = {'method': 'CreateGroupForm',
                    'name': group.name,
                    'description': group.description}
        res = self.client.post(GROUP_CREATE_URL, formData)

        self.assertNoFormErrors(res)
        self.assertMessageCount(success=1)

    @test.create_stubs({project_identity: ('group_get',
                                           'group_update')})
    def test_update(self):
        group = self.groups.get(id="1")
        test_description = 'updated description'

        project_identity.group_get(IsA(http.HttpRequest), '1').AndReturn(group)
        project_identity.group_update(IsA(http.HttpRequest),
                                      description=test_description,
                                      group_id=group.id,
                                      name=group.name).AndReturn(None)

        self.mox.ReplayAll()

        formData = {'method': 'UpdateGroupForm',
                    'group_id': group.id,
                    'name': group.name,
                    'description': test_description}

        res = self.client.post(GROUP_UPDATE_URL, formData)

        self.assertNoFormErrors(res)

    @test.create_stubs({project_identity: ('group_get',
                                           'group_user_list',)})
    def test_manage(self):
        group = self.groups.get(id="1")
        group_members = self.users.list()

        project_identity.group_get(IsA(http.HttpRequest), group.id).\
            AndReturn(group)
        project_identity.group_user_list(project=IsA('str'),
                                         group=group.id).\
            AndReturn(group_members)
        self.mox.ReplayAll()

        res = self.client.get(GROUP_MANAGE_URL)

        self.assertTemplateUsed(res, constants.GROUPS_MANAGE_VIEW_TEMPLATE)
        self.assertItemsEqual(res.context['table'].data, group_members)

    @test.create_stubs({project_identity: ('group_get',
                                           'project_user_list',
                                           'group_user_list',
                                           'add_group_user')})
    def test_add_user(self):
        group = self.groups.get(id="1")
        user = self.users.get(id="2")

        project_identity.group_get(IsA(http.HttpRequest), group.id).\
            AndReturn(group)
        project_identity.project_user_list(project=IsA('str')).\
            AndReturn(self.users.list())
        project_identity.group_user_list(project=IsA('str'),
                                         group=group.id).\
            AndReturn(self.users.list()[2:])

        project_identity.add_group_user(IgnoreArg(),
                                        group_id=group.id,
                                        user_id=user.id)

        self.mox.ReplayAll()

        formData = {'action': 'group_non_members__addMember__%s' % user.id}
        res = self.client.post(GROUP_ADD_MEMBER_URL, formData)

        self.assertRedirectsNoFollow(res, GROUP_MANAGE_URL)
        self.assertMessageCount(success=1)

    @test.create_stubs({project_identity: ('group_user_list',)})
    def test_remove_user(self):
        group = self.groups.get(id="1")
        group_members = self.users.list()
        user = self.users.get(id="2")

        project_identity.group_user_list(project=IsA('str'),
                                         group=group.id).\
            AndReturn(group_members)

        self.mox.ReplayAll()

        formData = {'action': 'group_members__removeGroupMember__%s' % user.id}
        res = self.client.post(GROUP_MANAGE_URL, formData)

        self.assertRedirectsNoFollow(res, GROUP_MANAGE_URL)

    @test.create_stubs({project_identity: ('group_get',
                                           'roles_for_group',
                                           'role_list')})
    def test_modify_role_list(self):
        group = self.groups.get(id="1")
        role = self.roles.get(id="2")

        project_identity.group_get(IsA(http.HttpRequest), group.id).\
            AndReturn(group)
        project_identity.roles_for_group(IsA(http.HttpRequest),
                                         group=group.id, project=IsA('str')).\
            AndReturn([role])
        project_identity.role_list(IsA(http.HttpRequest)).\
            AndReturn(self.users.list())

        self.mox.ReplayAll()

        res = self.client.get(GROUP_MODIFY_ROLES_URL)

        self.assertTemplateUsed(res,
                                constants.GROUPS_MODIFY_ROLES_VIEW_TEMPLATE)

    @test.create_stubs({project_identity: ('roles_for_group',
                                           'role_list',
                                           'remove_group_role')})
    def test_modify_role_update(self):
        group = self.groups.get(id="1")
        role = self.roles.get(id="2")

        form_data = {'method': 'ModifyRolesForm',
                     'group_id': group.id,
                     'C__Global__ProjectAdmin': True}
        self._modify_role_update_no_select(form_data, group, role)

    @test.create_stubs({project_identity: ('roles_for_group',
                                           'role_list',
                                           'remove_group_role')})
    def test_modify_role_update_no_select(self):
        group = self.groups.get(id="1")
        role = self.roles.get(id="2")

        form_data = {'method': 'ModifyRolesForm',
                     'group_id': group.id}
        self._modify_role_update_no_select(form_data, group, role)

    def _modify_role_update_no_select(self, form_data, group, role):
        project_identity.roles_for_group(IsA(http.HttpRequest),
                                         group=group.id, project=IsA('str')).\
            AndReturn([role])
        project_identity.role_list(IsA(http.HttpRequest)).\
            AndReturn(self.users.list())

        self.mox.ReplayAll()

        res = self.client.post(GROUP_MODIFY_ROLES_URL, form_data)

        self.assertRedirectsNoFollow(res, GROUPS_INDEX_URL)
        self.assertMessageCount(success=1)

    @test.create_stubs({project_identity: ('project_group_list',)})
    def test_delete_group(self):
        domain_id = self._get_domain_id()
        group = self.groups.get(id="2")

        project_identity.project_group_list(IgnoreArg(), domain=domain_id) \
            .AndReturn(self.groups.list())

        self.mox.ReplayAll()

        formData = {'action': 'groups__delete__%s' % group.id}
        res = self.client.post(GROUPS_INDEX_URL, formData)

        self.assertRedirectsNoFollow(res, GROUPS_INDEX_URL)
