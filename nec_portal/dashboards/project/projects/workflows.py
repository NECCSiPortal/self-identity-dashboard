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

import logging

from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _

from openstack_auth import utils as auth_utils

from horizon import exceptions
from horizon import forms
from horizon import workflows

from openstack_dashboard.api import keystone

from nec_portal.api import project_identity
from nec_portal.local import nec_portal_settings as nec_set

LOG = logging.getLogger(__name__)
INDEX_URL = "horizon:project:projects:index"
ADD_USER_URL = "horizon:project:projects:create_user"
COMMON_HORIZONTAL_TEMPLATE = "project/projects/_common_horizontal_form.html"


class CreateProjectInfoAction(workflows.Action):
    # Hide the domain_id and domain_name by default
    domain_id = forms.CharField(label=_("Domain ID"),
                                required=False,
                                widget=forms.HiddenInput())
    domain_name = forms.CharField(label=_("Domain Name"),
                                  required=False,
                                  widget=forms.HiddenInput())
    name = forms.CharField(label=_("Name"),
                           max_length=64)
    parent_id = forms.DynamicChoiceField(
        label=_("Parent Project"),
        required=False,
        widget=forms.widgets.Select(attrs={'disabled': 'true'}))
    description = forms.CharField(widget=forms.widgets.Textarea(
                                  attrs={'rows': 4}),
                                  label=_("Description"),
                                  required=False)
    enabled = forms.BooleanField(label=_("Enabled"),
                                 required=False,
                                 initial=True)

    def __init__(self, request, *args, **kwargs):
        super(CreateProjectInfoAction, self).__init__(request,
                                                      *args,
                                                      **kwargs)
        self.fields['enabled'].widget.attrs['disabled'] = True

        # For keystone V3, display the two fields in read-only
        if keystone.VERSIONS.active >= 3:
            readonlyInput = forms.TextInput(attrs={'readonly': 'readonly'})
            self.fields["domain_id"].widget = readonlyInput
            self.fields["domain_name"].widget = readonlyInput
            parent_id_choices = [(request.user.project_id,
                                  request.user.project_name)]
            self.fields["parent_id"].choices = parent_id_choices
        else:
            self.fields["parent_id"].widget = forms.HiddenInput()

    def clean(self):
        cleaned_data = super(CreateProjectInfoAction, self).clean()
        # NOTE(tsufiev): in case the current project is being edited, its
        # 'enabled' field is disabled to prevent changing the field value
        # which is always `True` for the current project (because the user
        # logged in it). Since Django treats disabled checkbox as providing
        # `False` value even if its initial value is `True`, we need to
        # restore the original `True` value of 'enabled' field here.
        if self.fields['enabled'].widget.attrs.get('disabled', False):
            cleaned_data['enabled'] = True
        return cleaned_data

    class Meta(object):
        name = _("Project Information")
        help_text = _("Create a project to organize users.")


class CreateProjectInfo(workflows.Step):
    action_class = CreateProjectInfoAction
    template_name = COMMON_HORIZONTAL_TEMPLATE
    contributes = ("domain_id",
                   "domain_name",
                   "project_id",
                   "name",
                   "description",
                   "parent_id",
                   "enabled")


class CreateProject(workflows.Workflow):
    slug = "create_project"
    name = _("Create Project")
    finalize_button_name = _("Create Project")
    success_message = _('Created new project "%s".')
    failure_message = _('Unable to create project "%s".')
    success_url = "horizon:project:projects:index"
    default_steps = (CreateProjectInfo,)

    def __init__(self, request=None, context_seed=None, entry_point=None,
                 *args, **kwargs):
        super(CreateProject, self).__init__(request=request,
                                            context_seed=context_seed,
                                            entry_point=entry_point,
                                            *args,
                                            **kwargs)

    def format_status_message(self, message):
        return message % self.context.get('name', 'unknown project')

    def _create_project(self, request, data):
        # create the project
        domain_id = data['domain_id']
        parent_id = request.user.project_id
        try:
            desc = data['description']
            kwargs = {'parent': parent_id} if parent_id else {}

            self.object = project_identity.project_create(
                request,
                name=data['name'],
                description=desc,
                enabled=data['enabled'],
                domain=domain_id,
                **kwargs)
            return self.object
        except Exception:
            exceptions.handle(request, ignore=True)
            return

    def _add_project_user_role(self, request, project_id):
        try:
            role_list = {role.name: role.id
                         for role in project_identity.role_list(request)}

            user = auth_utils.get_user(request)
            role_name_list = [role['name'] for role in user.roles]

            for role_name in role_name_list:
                if role_name in getattr(nec_set,
                                        'DISINHERITED_ROLES', []):
                    continue

                project_identity.add_project_user_role(
                    request,
                    project=project_id,
                    user=user,
                    role=role_list.get(role_name))
            return True
        except Exception:
            exceptions.handle(request, ignore=True)
            return False
        finally:
            auth_utils.remove_project_cache(request.user.token.id)

    def handle(self, request, data):
        project = self._create_project(request, data)
        if not project:
            return False

        return self._add_project_user_role(request, project.id)


class UpdateProjectInfoAction(CreateProjectInfoAction):
    parent_id = forms.DynamicChoiceField(
        label=_("Parent Project"), required=False,
        widget=forms.widgets.Select(attrs={'disabled': 'true'}))
    enabled = forms.BooleanField(required=False, label=_("Enabled"))

    def __init__(self, request, initial, *args, **kwargs):
        super(UpdateProjectInfoAction, self).__init__(
            request, initial, *args, **kwargs)
        if initial['project_id'] == request.user.token.project['id']:
            self.fields['enabled'].widget.attrs['disabled'] = True
            self.fields['enabled'].help_text = _(
                'You cannot disable your current project')
        else:
            self.fields['enabled'].widget.attrs['disabled'] = False

        if keystone.VERSIONS.active >= 3:
            parent_id_choices = self._get_parent_id_choices(
                initial['project_id'])
            self.fields["parent_id"].choices = parent_id_choices
        else:
            self.fields["parent_id"].widget = forms.HiddenInput()

    def _get_parent_id_choices(self, project_id):
        parent_id_choices = [('', '')]
        try:
            project = project_identity.project_get(self.request,
                                                   project_id,
                                                   admin=True)
            if not getattr(project, 'parent_id', None):
                return parent_id_choices
            if not project.parent_id:
                return parent_id_choices

            parent_project = project_identity.project_get(
                self.request, project.parent_id)

            parent_id_choices = [(parent_project.id, parent_project.name)]

        except Exception:
            exceptions.handle(self.request,
                              _('Unable to retrieve parent project details.'),
                              redirect=reverse(INDEX_URL))

        return parent_id_choices

    def clean(self):
        cleaned_data = super(UpdateProjectInfoAction, self).clean()
        # NOTE(tsufiev): in case the current project is being edited, its
        # 'enabled' field is disabled to prevent changing the field value
        # which is always `True` for the current project (because the user
        # logged in it). Since Django treats disabled checkbox as providing
        # `False` value even if its initial value is `True`, we need to
        # restore the original `True` value of 'enabled' field here.
        if self.fields['enabled'].widget.attrs.get('disabled', False):
            cleaned_data['enabled'] = True
        return cleaned_data

    class Meta(object):
        name = _("Project Information")
        slug = 'update_info'
        help_text = _("Edit the project details.")


class UpdateProjectInfo(workflows.Step):
    action_class = UpdateProjectInfoAction
    template_name = COMMON_HORIZONTAL_TEMPLATE
    depends_on = ("project_id",)
    contributes = ("domain_id",
                   "domain_name",
                   "name",
                   "description",
                   "enabled")


class UpdateProject(workflows.Workflow):
    slug = "update_project"
    name = _("Edit Project")
    finalize_button_name = _("Save")
    success_message = _('Modified project "%s".')
    failure_message = _('Unable to modify project "%s".')
    success_url = "horizon:project:projects:index"
    default_steps = (UpdateProjectInfo,)

    def __init__(self, request=None, context_seed=None, entry_point=None,
                 *args, **kwargs):
        super(UpdateProject, self).__init__(request=request,
                                            context_seed=context_seed,
                                            entry_point=entry_point,
                                            *args,
                                            **kwargs)

    def format_status_message(self, message):
        return message % self.context.get('name', 'unknown project')

    def _update_project(self, request, data):
        # update project info
        try:
            project_id = data['project_id']
            return project_identity.project_update(
                request,
                project_id,
                name=data['name'],
                description=data['description'],
                enabled=data['enabled'])
        except Exception:
            exceptions.handle(request, ignore=True)
            return

    def handle(self, request, data):
        # FIXME(gabriel): This should be refactored to use Python's built-in
        # sets and do this all in a single "roles to add" and "roles to remove"
        # pass instead of the multi-pass thing happening now.

        project = self._update_project(request, data)
        if not project:
            return False

        return True
