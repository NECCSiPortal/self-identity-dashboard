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
#

import logging

from django.utils.translation import ugettext_lazy as _

from horizon import exceptions
from horizon import forms
from horizon import messages

from nec_portal.api import project_identity
from nec_portal.local import nec_portal_settings as nec_set

LOG = logging.getLogger(__name__)


class CreateGroupForm(forms.SelfHandlingForm):
    name = forms.CharField(label=_("Name"))
    description = forms.CharField(widget=forms.widgets.Textarea(
                                  attrs={'rows': 4}),
                                  label=_("Description"))

    def handle(self, request, data):
        try:
            LOG.info('Creating group with name "%s"' % data['name'])
            domain_context = request.session.get('domain_context', None)
            new_group = project_identity.group_create(
                request,
                domain_id=domain_context,
                name=data['name'],
                description=data['description'])
            messages.success(request,
                             _('Group "%s" was successfully created.')
                             % data['name'])
            add_roles = getattr(nec_set, 'DEFAULT_GROUP_ROLES', [])
            all_role = project_identity.role_list(self.request)
            add_role_id = []
            for role in all_role:
                if role.name in add_roles:
                    add_role_id.append(role.id)
            for add_role in add_role_id:
                try:
                    project_identity.add_group_role(
                        request,
                        role=add_role,
                        group=new_group.id,
                        project=self.request.user.project_id)
                except Exception:
                    exceptions.handle(request,
                                      _('Unable to add user '
                                        'to primary project.'))
        except Exception:
            exceptions.handle(request, _('Unable to create group.'))
            return False
        return True


class UpdateGroupForm(forms.SelfHandlingForm):
    group_id = forms.CharField(widget=forms.HiddenInput())
    name = forms.CharField(label=_("Name"),
                           widget=forms.TextInput(
                               attrs={'readonly': 'readonly'}))
    description = forms.CharField(widget=forms.widgets.Textarea(
                                  attrs={'rows': 4}),
                                  label=_("Description"))

    def handle(self, request, data):
        group_id = data.pop('group_id')

        try:
            project_identity.group_update(request,
                                          group_id=group_id,
                                          name=data['name'],
                                          description=data['description'])
            messages.success(request,
                             _('Group has been updated successfully.'))
        except Exception:
            exceptions.handle(request, _('Unable to update the group.'))
            return False
        return True


class ModifyRolesForm(forms.SelfHandlingForm):

    def __init__(self, request, *args, **kwargs):
        super(ModifyRolesForm, self).__init__(request, *args, **kwargs)

    def _add_roles_to_groups(self, request, data, project_id, group_id,
                             role_ids, available_roles):
        checked_role_list = data
        current_role_ids = list(role_ids)
        for role in available_roles:
            if role.name in checked_role_list:
                if role not in current_role_ids:
                    project_identity.add_group_role(
                        request,
                        role=role.id,
                        group=group_id,
                        project=project_id)
                else:
                    index = current_role_ids.index(role)
                    current_role_ids.pop(index)
        return current_role_ids

    def _remove_roles_from_groups(self, request, project_id, group_id,
                                  current_role_ids):
        for id_to_delete in current_role_ids:
            if str(id_to_delete.name).count('__') == 2 or\
               str(id_to_delete.name) == 'admin':
                project_identity.remove_group_role(
                    request,
                    role=id_to_delete.id,
                    group=group_id,
                    project=project_id)

    def handle(self, request, data):
        group_id = request.POST['group_id']
        role_data = request.POST.getlist('checked')
        set_auth_conf = getattr(nec_set, 'TBL_ROLE_ALL', None)
        try:
            old_role_list = project_identity.roles_for_group(
                self.request,
                group=group_id,
                project=request.user.project_id)
            all_role_list = project_identity.role_list(request)

            if role_data == []:
                default_roles = getattr(nec_set,
                                        'DEFAULT_GROUP_ROLES', [])
                for id_to_delete in old_role_list:
                    if id_to_delete.name in default_roles:
                        continue
                    project_identity.remove_group_role(
                        request,
                        role=id_to_delete.id,
                        group=group_id,
                        project=request.user.project_id)
            else:
                admin_role_list = []
                for set_auth in set_auth_conf:
                    if set_auth['policy'] == 'admin':
                        admin_role_list.append(set_auth['initial'])
                for role_name in role_data:
                    initial, region, rolename = str(role_name).split('__')
                    if initial in admin_role_list:
                        role_data.append('admin')
                        break

                modified_role_ids = self._add_roles_to_groups(
                    request, role_data, request.user.project_id,
                    group_id, old_role_list, all_role_list)

                self._remove_roles_from_groups(
                    request, request.user.project_id,
                    group_id, modified_role_ids)

            messages.success(request,
                             _('User has been updated successfully.'))
        except Exception:
            exceptions.handle(request, ignore=True)
            messages.error(request, _('Unable to update the user.'))

        return True
