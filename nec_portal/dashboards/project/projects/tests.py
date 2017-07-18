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

from mox3.mox import IsA

from django.core.urlresolvers import reverse
from django import http

from openstack_dashboard import api
from openstack_dashboard.test import helpers as test

from horizon.workflows import views

from nec_portal.api import project_identity
from nec_portal.dashboards.project.projects import workflows
from nec_portal.local import nec_portal_settings as nec_set

INDEX_URL = reverse('horizon:project:projects:index')
PROJECT_DETAIL_URL = reverse('horizon:project:projects:detail', args=[1])
PROJECT_MANAGE_URL = reverse('horizon:project:projects:manage_members',
                             args=[1])
PROJECT_ADD_MEMBERS_URL = reverse('horizon:project:projects:add_members',
                                  args=[1])


class TenantsViewTests(test.BaseAdminViewTests):
    @test.create_stubs({project_identity: ('project_list',)})
    def test_index(self):
        project_identity.project_list(IsA(http.HttpRequest),
                                      domain=None,
                                      paginate=True,
                                      marker=None) \
            .AndReturn([self.tenants.list(), False])
        self.mox.ReplayAll()

        res = self.client.get(INDEX_URL)
        self.assertTemplateUsed(res, 'project/projects/index.html')
        self.assertItemsEqual(res.context['table'].data, self.tenants.list())

    @test.create_stubs({project_identity: ('project_list',)})
    def test_delete(self):
        project_identity.project_list(IsA(http.HttpRequest),
                                      domain=None,
                                      paginate=True,
                                      marker=None) \
            .AndReturn([self.tenants.list(), False])

        self.mox.ReplayAll()

        formData = {'action': 'tenants__delete__%s' % self.tenants.get(id="1")}
        res = self.client.post(INDEX_URL, formData)

        self.assertRedirectsNoFollow(res, INDEX_URL)


class DetailProjectViewTests(test.BaseAdminViewTests):
    @test.create_stubs({project_identity: ('project_get',)})
    def test_detail_view(self):
        project = self.tenants.first()
        project.parent_id = 'parent_1'
        parent_project = self.tenants.get(id="2")

        project_identity.project_get(IsA(http.HttpRequest), self.tenant.id) \
            .AndReturn(project)
        project_identity.project_get(IsA(http.HttpRequest),
                                     project.parent_id) \
            .AndReturn(parent_project)
        self.mox.ReplayAll()

        res = self.client.get(PROJECT_DETAIL_URL, args=[project.id])

        self.assertTemplateUsed(res, 'project/projects/detail.html')
        self.assertEqual(res.context['project'].name, project.name)
        self.assertEqual(res.context['project'].id, project.id)
        self.assertEqual(res.context['project'].parent_id, 'parent_1')
        self.assertEqual(res.context["parent_project_name"],
                         parent_project.name)
        self.assertContains(res, project.name, 3, 200)


class CreateProjectWorkflowTests(test.BaseAdminViewTests):
    def _get_project_info(self, project):
        domain = self._get_default_domain()
        project_info = {"name": project.name,
                        "description": project.description,
                        "enabled": project.enabled,
                        "domain": domain.id}
        return project_info

    def _get_workflow_fields(self, project):
        domain = self._get_default_domain()
        project_info = {"domain_id": domain.id,
                        "domain_name": domain.name,
                        "name": project.name,
                        "description": project.description,
                        "enabled": project.enabled}
        return project_info

    def _get_workflow_data(self, project, quota):
        project_info = self._get_workflow_fields(project)
        quota_data = self._get_quota_info(quota)
        project_info.update(quota_data)
        return project_info

    def _get_default_domain(self):
        default_domain = self.domain
        domain = {"id": self.request.session.get('domain_context',
                                                 default_domain.id),
                  "name": self.request.session.get('domain_context_name',
                                                   default_domain.name)}
        return api.base.APIDictWrapper(domain)

    def _get_all_users(self, domain_id):
        if not domain_id:
            users = self.users.list()
        else:
            users = [user for user in self.users.list()
                     if user.domain_id == domain_id]
        return users

    def _get_all_groups(self, domain_id):
        if not domain_id:
            groups = self.groups.list()
        else:
            groups = [group for group in self.groups.list()
                      if group.domain_id == domain_id]
        return groups

    @test.create_stubs({project_identity: ('get_default_domain',)})
    def test_add_project_get(self):
        self.roles.first()
        default_domain = self._get_default_domain()
        self.roles.list()

        # init
        project_identity.get_default_domain(
            IsA(http.HttpRequest)).AndReturn(default_domain)

        self.mox.ReplayAll()

        url = reverse('horizon:project:projects:create')
        res = self.client.get(url)

        self.assertTemplateUsed(res, views.WorkflowView.template_name)

        workflow = res.context['workflow']
        self.assertEqual(res.context['workflow'].name,
                         workflows.CreateProject.name)

        workflow.get_step("createprojectinfoaction")
        self.assertQuerysetEqual(
            workflow.steps,
            ['<CreateProjectInfo: createprojectinfoaction>'])

    @test.create_stubs({project_identity: ('project_get',
                                           'domain_get')})
    def test_update_project_get(self):
        api.keystone.VERSIONS.active
        project = self.tenants.first()
        self.roles.first()
        domain_id = project.domain_id
        self._get_all_users(domain_id)

        project_identity.project_get(
            IsA(http.HttpRequest),
            self.tenant.id, admin=True).AndReturn(project)
        project_identity.domain_get(
            IsA(http.HttpRequest),
            domain_id).AndReturn(self.domain)
        project_identity.project_get(
            IsA(http.HttpRequest),
            None, admin=True).AndReturn(project)

        self.mox.ReplayAll()

        url = reverse('horizon:project:projects:update',
                      args=[self.tenant.id])
        res = self.client.get(url)

        self.assertTemplateUsed(res, views.WorkflowView.template_name)

        workflow = res.context['workflow']
        self.assertEqual(res.context['workflow'].name,
                         workflows.UpdateProject.name)

        self.assertQuerysetEqual(
            workflow.steps,
            ['<UpdateProjectInfo: update_info>'])

    @test.create_stubs({project_identity: ('project_get',
                                           'project_user_list',)})
    def test_manage(self):
        project = self.groups.get(id="1")
        project_members = self.users.list()

        project_identity.project_get(IsA(http.HttpRequest), project.id).\
            AndReturn(project)
        project_identity.project_user_list(project=project.id).\
            AndReturn(project_members)

        self.mox.ReplayAll()

        res = self.client.get(PROJECT_MANAGE_URL)

        self.assertTemplateUsed(res, 'project/projects/manage.html')
        self.assertItemsEqual(res.context['table'].data, project_members)

    @test.create_stubs({project_identity: ('project_get',
                                           'project_user_list',)})
    def test_add_member(self):
        project = self.groups.get(id="1")
        project_all_members = self.users.list()
        project_members = self.users.list()[2:]

        project_identity.project_get(IsA(http.HttpRequest), project.id).\
            AndReturn(project)
        project_identity.project_user_list(project=IsA('str')).\
            AndReturn(project_all_members)
        project_identity.project_user_list(project=project.id).\
            AndReturn(project_members)

        self.mox.ReplayAll()

        res = self.client.get(PROJECT_ADD_MEMBERS_URL)

        self.assertTemplateUsed(res, 'project/projects/add_non_member.html')
        self.assertItemsEqual(res.context['table'].data,
                              project_all_members[0:2])

    @test.create_stubs({project_identity: ('project_get',
                                           'project_user_list',
                                           'role_list',
                                           'add_project_user_role')})
    def test_add_member_post(self):
        user = self.users.get(id="2")
        project = self.groups.get(id="1")
        project_members = self.users.list()
        roles = self.roles.list()

        project_identity.project_get(IsA(http.HttpRequest), project.id).\
            AndReturn(project)
        project_identity.project_user_list(project=IsA('str')).\
            AndReturn(project_members)
        project_identity.project_user_list(project=project.id).\
            AndReturn(project_members[2:])
        project_identity.role_list(IsA(http.HttpRequest)).\
            AndReturn(roles)

        project_identity.add_project_user_role(IsA(http.HttpRequest),
                                               project=IsA('str'),
                                               user=IsA('str'),
                                               role=IsA('str'))

        self.mox.ReplayAll()

        formData = {'action': 'project_non_members__addMember__%s' % user.id}
        res = self.client.post(PROJECT_ADD_MEMBERS_URL, formData)

        self.assertRedirectsNoFollow(res, PROJECT_MANAGE_URL)

    def test_add_member_post_no_set_disinherit_roles(self):
        setattr(nec_set, 'DISINHERITED_ROLES', [])
        self.test_add_member_post()

    @test.create_stubs({project_identity: ('project_user_list',)})
    def test_remove_user(self):
        user = self.users.get(id="2")
        project = self.groups.get(id="1")
        project_members = self.users.list()

        project_identity.project_user_list(project=project.id).\
            AndReturn(project_members)

        self.mox.ReplayAll()

        formData = {'action': 'project_members__remove_project_member__%s'
                    % user.id}
        res = self.client.post(PROJECT_MANAGE_URL, formData)

        self.assertRedirectsNoFollow(res, PROJECT_MANAGE_URL)
