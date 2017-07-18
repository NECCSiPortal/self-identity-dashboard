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
#

from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
from django.views import generic

from horizon import exceptions
from horizon import forms
from horizon import messages
from horizon import tables
from horizon.utils import memoized
from horizon import workflows

from openstack_dashboard.api import keystone
from openstack_dashboard import policy

from nec_portal.api import project_identity
from nec_portal.dashboards.project.projects \
    import tables as project_tables
from nec_portal.dashboards.project.projects \
    import workflows as project_workflows

PROJECT_INFO_FIELDS = ("domain_id",
                       "domain_name",
                       "name",
                       "description",
                       "enabled")

INDEX_URL = "horizon:project:projects:index"


class TenantContextMixin(object):
    @memoized.memoized_method
    def get_object(self):
        project_id = self.kwargs['project_id']
        try:
            return project_identity.project_get(self.request,
                                                project_id,
                                                admin=True)
        except Exception:
            exceptions.handle(self.request,
                              _('Unable to retrieve project information.'),
                              redirect=reverse(INDEX_URL))

    def get_context_data(self, **kwargs):
        context = super(TenantContextMixin, self).get_context_data(**kwargs)
        context['tenant'] = self.get_object()
        return context


class IndexView(tables.DataTableView):
    table_class = project_tables.TenantsTable
    template_name = 'project/projects/index.html'
    page_title = _("Projects")

    def has_more_data(self, table):
        return self._more

    def get_data(self):
        projects = []
        marker = self.request.GET.get(
            project_tables.TenantsTable._meta.pagination_param, None)
        domain_context = self.request.session.get('domain_context', None)
        self._more = False
        if policy.check((("identity", "identity:list_projects"),),
                        self.request):
            try:
                projects, self._more = project_identity.project_list(
                    self.request,
                    domain=domain_context,
                    paginate=True,
                    marker=marker)
            except Exception:
                exceptions.handle(self.request,
                                  _("Unable to retrieve project list."))
        elif policy.check((("identity", "identity:list_user_projects"),),
                          self.request):
            try:
                projects, self._more = project_identity.project_list(
                    self.request,
                    user=self.request.user.id,
                    paginate=True,
                    marker=marker,
                    admin=False)
            except Exception:
                exceptions.handle(self.request,
                                  _("Unable to retrieve project information."))
        else:
            msg = \
                _("Insufficient privilege level to view project information.")
            messages.info(self.request, msg)
        return projects


class CreateProjectView(workflows.WorkflowView):
    workflow_class = project_workflows.CreateProject

    def get_initial(self):
        initial = super(CreateProjectView, self).get_initial()

        # Set the domain of the project
        domain = project_identity.get_default_domain(self.request)
        initial["domain_id"] = domain.id
        initial["domain_name"] = domain.name

        return initial


class UpdateProjectView(workflows.WorkflowView):
    workflow_class = project_workflows.UpdateProject

    def get_initial(self):
        initial = super(UpdateProjectView, self).get_initial()

        project_id = self.kwargs['project_id']
        initial['project_id'] = project_id

        try:
            # get initial project info
            project_info = project_identity.project_get(self.request,
                                                        project_id,
                                                        admin=True)
            for field in PROJECT_INFO_FIELDS:
                initial[field] = getattr(project_info, field, None)

            # Retrieve the domain name where the project belong
            if keystone.VERSIONS.active >= 3:
                try:
                    domain = project_identity.domain_get(self.request,
                                                         initial["domain_id"])
                    initial["domain_name"] = domain.name
                except Exception:
                    exceptions.handle(self.request,
                                      _('Unable to retrieve project domain.'),
                                      redirect=reverse(INDEX_URL))
                # Show parent project info, if available
                if hasattr(project_info, "parent_id"):
                    initial["parent_id"] = project_info.parent_id
        except Exception:
            exceptions.handle(self.request,
                              _('Unable to retrieve project details.'),
                              redirect=reverse(INDEX_URL))
        return initial


class DetailProjectView(generic.TemplateView):
    template_name = 'project/projects/detail.html'

    def get_context_data(self, **kwargs):
        context = super(DetailProjectView, self).get_context_data(**kwargs)
        project = self.get_data()
        parent_project_name = self._get_parent_project_name(project)
        table = project_tables.TenantsTable(self.request)
        context["project"] = project
        context["parent_project_name"] = parent_project_name
        context["page_title"] = project.name
        context["url"] = reverse(INDEX_URL)
        context["actions"] = table.render_row_actions(project)
        return context

    @memoized.memoized_method
    def get_data(self):
        try:
            project_id = self.kwargs['project_id']
            project = project_identity.project_get(self.request, project_id)
        except Exception:
            exceptions.handle(self.request,
                              _('Unable to retrieve project details.'),
                              redirect=reverse(INDEX_URL))
        return project

    def _get_parent_project_name(self, project):
        if not getattr(project, 'parent_id', None):
            return None
        if not project.parent_id:
            return None
        try:
            project = project_identity.project_get(
                self.request, project.parent_id)
        except Exception:
            exceptions.handle(self.request,
                              _('Unable to retrieve parent project details.'),
                              redirect=reverse(INDEX_URL))
        return project.name


class ProjectManageMixin(object):
    @memoized.memoized_method
    def _get_project(self):
        project_id = self.kwargs['project_id']
        return project_identity.project_get(self.request, project_id)

    @memoized.memoized_method
    def _get_project_members(self):
        project_id = self.kwargs['project_id']
        return project_identity.project_user_list(project=project_id)

    @memoized.memoized_method
    def _get_project_non_members(self):
        self._get_project().domain_id
        all_users = project_identity.project_user_list(
            project=self.request.user.project_id)
        project_members = self._get_project_members()
        project_member_ids = [user.id for user in project_members]
        return filter(lambda u: u.id not in project_member_ids, all_users)


class ManageMembersView(ProjectManageMixin, tables.DataTableView):
    table_class = project_tables.ProjectMembersTable
    template_name = 'project/projects/manage.html'
    page_title = _("Project Management: {{ project.name }}")

    def get_context_data(self, **kwargs):
        context = super(ManageMembersView, self).get_context_data(**kwargs)
        try:
            context['project'] = self._get_project()
        except Exception:
            exceptions.handle(self.request,
                              _('Unable to retrieve project users.'))
        return context

    def get_data(self):
        project_members = []
        try:
            project_members = self._get_project_members()
        except Exception:
            exceptions.handle(self.request,
                              _('Unable to retrieve project users.'))
        return project_members


class NonMembersView(ProjectManageMixin, forms.ModalFormMixin,
                     tables.DataTableView):
    template_name = 'project/projects/add_non_member.html'
    ajax_template_name = 'project/projects/_add_non_member.html'
    table_class = project_tables.ProjectNonMembersTable

    def get_context_data(self, **kwargs):
        context = super(NonMembersView, self).get_context_data(**kwargs)
        try:
            context['project'] = self._get_project()
        except Exception:
            exceptions.handle(self.request,
                              _('Unable to retrieve project users.'))
        return context

    def get_data(self):
        project_non_members = []
        try:
            project_non_members = self._get_project_non_members()
        except Exception:
            exceptions.handle(self.request,
                              _('Unable to retrieve users.'))
        return project_non_members
