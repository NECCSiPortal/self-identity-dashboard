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
#

import logging

from django.core.urlresolvers import reverse
from django.core.urlresolvers import reverse_lazy
from django.utils.translation import ugettext_lazy as _

from horizon import exceptions
from horizon import forms
from horizon import tables
from horizon.utils import memoized

from openstack_auth import utils as auth_utils

from nec_portal.api import project_identity
from nec_portal.dashboards.project.groups import constants
from nec_portal.dashboards.project.groups \
    import forms as project_forms
from nec_portal.dashboards.project.groups \
    import tables as project_tables
from nec_portal.local import nec_portal_settings as nec_set

LOG = logging.getLogger(__name__)


class IndexView(tables.DataTableView):
    table_class = project_tables.GroupsTable
    template_name = constants.GROUPS_INDEX_VIEW_TEMPLATE
    page_title = _("Groups")

    def get_data(self):
        groups = []
        domain_context = self.request.session.get('domain_context', None)
        try:
            groups = project_identity.project_group_list(
                project=self.request.user.project_id,
                domain=domain_context)
        except Exception:
            exceptions.handle(self.request,
                              _('Unable to retrieve group list.'))
        return groups


class CreateView(forms.ModalFormView):
    template_name = constants.GROUPS_CREATE_VIEW_TEMPLATE
    modal_header = _("Create Group")
    form_id = "create_group_form"
    form_class = project_forms.CreateGroupForm
    submit_label = _("Create Group")
    submit_url = reverse_lazy(constants.GROUPS_CREATE_URL)
    success_url = reverse_lazy(constants.GROUPS_INDEX_URL)
    page_title = _("Create Group")


class UpdateView(forms.ModalFormView):
    template_name = constants.GROUPS_UPDATE_VIEW_TEMPLATE
    modal_header = _("Update Group")
    form_id = "update_group_form"
    form_class = project_forms.UpdateGroupForm
    submit_url = constants.GROUPS_UPDATE_URL
    submit_label = _("Update Group")
    success_url = reverse_lazy(constants.GROUPS_INDEX_URL)
    page_title = _("Update Group")

    @memoized.memoized_method
    def get_object(self):
        try:
            return project_identity.group_get(
                self.request, self.kwargs['group_id'])
        except Exception:
            redirect = reverse(constants.GROUPS_INDEX_URL)
            exceptions.handle(self.request,
                              _('Unable to update group.'),
                              redirect=redirect)

    def get_context_data(self, **kwargs):
        context = super(UpdateView, self).get_context_data(**kwargs)
        args = (self.get_object().id,)
        context['submit_url'] = reverse(self.submit_url, args=args)
        return context

    def get_initial(self):
        group = self.get_object()
        return {'group_id': group.id,
                'name': group.name,
                'description': group.description}


class GroupManageMixin(object):
    @memoized.memoized_method
    def _get_group(self):
        group_id = self.kwargs['group_id']
        return project_identity.group_get(self.request, group_id)

    @memoized.memoized_method
    def _get_group_members(self):
        group_id = self.kwargs['group_id']
        return project_identity.group_user_list(
            project=self.request.user.project_id, group=group_id)

    @memoized.memoized_method
    def _get_group_non_members(self):
        self._get_group().domain_id
        all_project_users = project_identity.project_user_list(
            project=self.request.user.project_id)
        group_members = self._get_group_members()
        group_member_ids = [user.id for user in group_members]
        return filter(lambda u: u.id not in group_member_ids,
                      all_project_users)


class ManageMembersView(GroupManageMixin, tables.DataTableView):
    table_class = project_tables.GroupMembersTable
    template_name = constants.GROUPS_MANAGE_VIEW_TEMPLATE
    page_title = _("Group Management: {{ group.name }}")

    def get_context_data(self, **kwargs):
        context = super(ManageMembersView, self).get_context_data(**kwargs)
        context['group'] = self._get_group()
        return context

    def get_data(self):
        group_members = []
        try:
            group_members = self._get_group_members()
        except Exception:
            exceptions.handle(self.request,
                              _('Unable to retrieve group users.'))
        return group_members


class NonMembersView(GroupManageMixin, forms.ModalFormMixin,
                     tables.DataTableView):
    template_name = constants.GROUPS_ADD_MEMBER_VIEW_TEMPLATE
    ajax_template_name = constants.GROUPS_ADD_MEMBER_AJAX_VIEW_TEMPLATE
    table_class = project_tables.GroupNonMembersTable

    def get_context_data(self, **kwargs):
        context = super(NonMembersView, self).get_context_data(**kwargs)
        context['group'] = self._get_group()
        return context

    def get_data(self):
        group_non_members = []
        try:
            group_non_members = self._get_group_non_members()
        except Exception:
            exceptions.handle(self.request,
                              _('Unable to retrieve users.'))
        return group_non_members


class ModifyRolesView(forms.ModalFormView):
    template_name = constants.GROUPS_MODIFY_ROLES_VIEW_TEMPLATE
    modal_header = _("Modify Roles")
    form_id = "modify_group_roles_form"
    form_class = project_forms.ModifyRolesForm
    submit_url = constants.GROUPS_MODIFY_ROLES_URL
    submit_label = _("Save")
    success_url = reverse_lazy(constants.GROUPS_INDEX_URL)
    page_title = _("Modify Roles")

    def dispatch(self, *args, **kwargs):
        return super(ModifyRolesView, self).dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ModifyRolesView, self).get_context_data(**kwargs)
        args = (self.kwargs['group_id'],)
        context['submit_url'] = reverse(self.submit_url, args=args)
        context['group_id'] = self.kwargs['group_id']
        context['group_name'] = self.get_group_object().name
        context['roles_list'] = []

        role_operator = self.get_user_role(self.request.user.id)
        role_target = self.get_group_role(self.kwargs['group_id'])
        role_all = self.get_data()
        roles_list = {}
        dsp_role = {}

        for role in role_all:
            if str(role.name).count('__') == 2:

                initial, region, rolename = str(role.name).split('__')
                if initial not in roles_list:
                    roles_list[initial] = {}
                    dsp_role[initial] = []
                if region not in roles_list[initial]:
                    roles_list[initial][region] = {}
                if rolename not in roles_list[initial][region]:
                    roles_list[initial][region][rolename] = []
                if rolename not in dsp_role[initial]:
                    dsp_role[initial].append(rolename)

                flg_operator = 0
                flg_target = 0
                if role.name in role_operator:
                    flg_operator = 1
                if role.name in role_target:
                    flg_target = 1
                roles_list[initial][region][rolename] = [flg_operator,
                                                         flg_target,
                                                         role.id,
                                                         role.name]

        set_role_conf = getattr(nec_set, 'TBL_ROLE_ALL', None)
        for set_role in set_role_conf:

            if set_role['policy'] == 'admin':
                if 'admin' not in role_operator:
                    continue
            initial = set_role['initial']
            if initial not in roles_list:
                continue

            set_role['dsp_col'] = []
            set_role['dsp_row'] = {}
            for region, role in sorted(roles_list[initial].iteritems()):
                for key in dsp_role[initial]:
                    if key not in set_role['dsp_row']:
                        set_role['dsp_row'][key] = []
                    value = [3, 0, '', '']
                    if key in role:
                        value = role[key]
                    set_role['dsp_row'][key].append(value)
                set_role['dsp_col'].append(region)
            context['roles_list'].append(set_role)

        return context

    @memoized.memoized_method
    def get_data(self):
        try:
            roles = project_identity.role_list(self.request)
        except Exception:
            redirect = self.get_redirect_url()
            exceptions.handle(self.request,
                              _('Unable to retrieve role list.'),
                              redirect=redirect)
        return roles

    @memoized.memoized_method
    def get_user_role(self, user_id):
        try:
            user = auth_utils.get_user(self.request)
        except Exception:
            redirect = self.get_redirect_url()
            exceptions.handle(self.request,
                              _('Unable to retrieve role list.'),
                              redirect=redirect)
        role_names = [role['name'] for role in user.roles]
        return role_names

    @memoized.memoized_method
    def get_group_role(self, group_id):
        role_name_list = []
        try:
            roles = project_identity.roles_for_group(
                self.request, group=group_id,
                project=self.request.user.project_id)
        except Exception:
            redirect = self.get_redirect_url()
            exceptions.handle(self.request,
                              _('Unable to retrieve role list.'),
                              redirect=redirect)
        for role in roles:
            role_name_list.append(role.name)
        return role_name_list

    @memoized.memoized_method
    def get_group_object(self):
        try:
            return project_identity.group_get(
                self.request, self.kwargs['group_id'])
        except Exception:
            redirect = reverse("horizon:project:users:index")
            exceptions.handle(self.request,
                              _('Unable to retrieve user information.'),
                              redirect=redirect)
