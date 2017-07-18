# Copyright 2012 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
#
# Copyright 2012 Nebula, Inc.
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

from nec_portal.api import project_identity
from openstack_dashboard import api
from openstack_dashboard.test import helpers as test


USERS_INDEX_URL = reverse('horizon:project:users:index')
USER_CREATE_URL = reverse('horizon:project:users:create')
USER_UPDATE_URL = reverse('horizon:project:users:update', args=[1])
USER_DETAIL_URL = reverse('horizon:project:users:detail', args=[1])


class UsersViewTests(test.BaseAdminViewTests):
    def _get_default_domain(self):
        domain = {"id": self.request.session.get('domain_context',
                                                 None),
                  "name": self.request.session.get('domain_context_name',
                                                   None)}
        return api.base.APIDictWrapper(domain)

    def _get_users(self, domain_id):
        if not domain_id:
            users = self.users.list()
        else:
            users = [user for user in self.users.list()
                     if user.domain_id == domain_id]
        return users

    @test.create_stubs({project_identity: ('project_user_list',)})
    def test_index(self):
        domain = self._get_default_domain()
        domain_id = domain.id
        users = self._get_users(domain_id)
        project_identity.project_user_list(project=IsA('str')). \
            AndReturn(users)

        self.mox.ReplayAll()
        res = self.client.get(USERS_INDEX_URL)
        self.assertTemplateUsed(res, 'project/users/index.html')
        self.assertItemsEqual(res.context['table'].data, users)

        if domain_id:
            for user in res.context['table'].data:
                self.assertItemsEqual(user.domain_id, domain_id)

    @test.create_stubs({project_identity: ('user_create',
                                           'get_default_domain',
                                           'project_list',
                                           'add_project_user_role',
                                           'get_default_role',
                                           'roles_for_user',
                                           'role_list')})
    def test_create(self):
        user = self.users.get(id="1")
        domain = self._get_default_domain()
        domain_id = domain.id

        role = self.roles.first()

        project_identity.get_default_domain(IgnoreArg()) \
            .MultipleTimes().AndReturn(domain)
        project_identity.user_create(IgnoreArg(),
                                     name=user.name,
                                     email=user.email,
                                     password=user.password,
                                     project=self.tenant.id,
                                     enabled=True,
                                     domain=domain_id).AndReturn(user)
        project_identity.role_list(IgnoreArg()).AndReturn(self.roles.list())
        project_identity.get_default_role(IgnoreArg()).AndReturn(role)

        self.mox.ReplayAll()

        formData = {'method': 'CreateUserForm',
                    'domain_id': domain_id,
                    'name': user.name,
                    'description': user.description,
                    'email': user.email,
                    'password': user.password,
                    'project': self.tenant.id,
                    'role_id': self.roles.first().id,
                    'enabled': True,
                    'confirm_password': user.password}
        res = self.client.post(USER_CREATE_URL, formData)

        self.assertNoFormErrors(res)

    @test.create_stubs({project_identity: ('user_get',
                                           'domain_get',
                                           'user_update',)})
    def test_update(self):
        user = self.users.get(id="1")
        domain_id = user.domain_id
        domain = self.domains.get(id=domain_id)

        project_identity.user_get(IsA(http.HttpRequest), '1').AndReturn(user)
        project_identity.domain_get(IsA(http.HttpRequest),
                                    domain_id).AndReturn(domain)
        project_identity.user_update(IsA(http.HttpRequest),
                                     user.id,
                                     email=user.email,
                                     name=user.name).AndReturn(None)

        self.mox.ReplayAll()

        formData = {'method': 'UpdateUserForm',
                    'id': user.id,
                    'name': user.name,
                    'description': user.description,
                    'email': user.email,
                    'project': self.tenant.id}

        res = self.client.post(USER_UPDATE_URL, formData)

        self.assertNoFormErrors(res)
        self.assertMessageCount(success=1)

    @test.create_stubs({project_identity: ('user_get',)})
    def test_detail_view(self):
        user = self.users.get(id="1")
        self.tenants.get(id=user.project_id)

        project_identity.user_get(IsA(http.HttpRequest), '1').AndReturn(user)
        self.mox.ReplayAll()

        res = self.client.get(USER_DETAIL_URL, args=[user.id])

        self.assertTemplateUsed(res, 'project/users/detail.html')
        self.assertEqual(res.context['user'].name, user.name)
        self.assertEqual(res.context['user'].id, user.id)
        self.assertContains(res, user.name, 3, 200)

    @test.create_stubs({project_identity: ('project_user_list',)})
    def test_delete_user(self):
        domain = self._get_default_domain()
        domain_id = domain.id
        users = self._get_users(domain_id)

        project_identity.project_user_list(project=IsA('str')). \
            AndReturn(users)

        self.mox.ReplayAll()

        formData = {'action': 'users__delete__%s' % users[0].id}
        res = self.client.post(USERS_INDEX_URL, formData)

        self.assertRedirectsNoFollow(res, USERS_INDEX_URL)
