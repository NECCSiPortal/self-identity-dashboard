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

from django.forms import ValidationError
from django import http
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.debug import sensitive_variables

from horizon import exceptions
from horizon import forms
from horizon import messages
from horizon.utils import validators

from nec_portal.api import project_identity
from nec_portal.local import nec_portal_settings as nec_set

from openstack_dashboard import api


LOG = logging.getLogger(__name__)
PROJECT_REQUIRED = api.keystone.VERSIONS.active < 3


class PasswordMixin(forms.SelfHandlingForm):
    password = forms.RegexField(
        label=_("Password"),
        widget=forms.PasswordInput(render_value=False),
        regex=validators.password_validator(),
        error_messages={'invalid': validators.password_validator_msg()})
    confirm_password = forms.CharField(
        label=_("Confirm Password"),
        widget=forms.PasswordInput(render_value=False))
    no_autocomplete = True

    def clean(self):
        '''Check to make sure password fields match.'''
        data = super(forms.Form, self).clean()
        if 'password' in data:
            if data['password'] != data.get('confirm_password', None):
                raise ValidationError(_('Passwords do not match.'))
        return data


class BaseUserForm(forms.SelfHandlingForm):
    def __init__(self, request, *args, **kwargs):
        super(BaseUserForm, self).__init__(request, *args, **kwargs)

        self.fields['project'].initial = self.request.user.project_name


class CreateUserForm(PasswordMixin, BaseUserForm):
    # Hide the domain_id and domain_name by default
    domain_id = forms.CharField(label=_("Domain ID"),
                                required=False,
                                widget=forms.HiddenInput())
    domain_name = forms.CharField(label=_("Domain Name"),
                                  required=False,
                                  widget=forms.HiddenInput())
    name = forms.CharField(max_length=255, label=_("User Name"))
    email = forms.EmailField(
        label=_("Email"))

    project = forms.CharField(label=_("Primary Project"),
                              widget=forms.TextInput(
                                  attrs={'readonly': 'readonly'}))

    def __init__(self, *args, **kwargs):
        kwargs.pop('roles')
        super(CreateUserForm, self).__init__(*args, **kwargs)
        # Reorder form fields from multiple inheritance
        self.fields.keyOrder = ["domain_id", "domain_name", "name",
                                "email", "password", "confirm_password",
                                "project"]

        # For keystone V3, display the two fields in read-only
        if api.keystone.VERSIONS.active >= 3:
            readonlyInput = forms.TextInput(attrs={'readonly': 'readonly'})
            self.fields["domain_id"].widget = readonlyInput
            self.fields["domain_name"].widget = readonlyInput

    # We have to protect the entire "data" dict because it contains the
    # password and confirm_password strings.
    @sensitive_variables('data')
    def handle(self, request, data):
        domain = project_identity.get_default_domain(self.request)
        try:
            LOG.info('Creating user with name "%s"' % data['name'])
            if "email" in data:
                data['email'] = data['email'] or None
            new_user = project_identity.user_create(
                request,
                name=data['name'],
                email=data['email'],
                password=data['password'],
                project=self.request.user.project_id,
                enabled=True,
                domain=domain.id)
            messages.success(request,
                             _('User "%s" was successfully created.')
                             % data['name'])

            if data['project']:
                add_roles = getattr(nec_set, 'DEFAULT_USER_ROLES', [])
                all_role = project_identity.role_list(self.request)
                add_role_id = []
                for role in all_role:
                    if role.name in add_roles:
                        add_role_id.append(role.id)
                roles = project_identity.roles_for_user(
                    request,
                    new_user.id,
                    self.request.user.project_id) or []
                for add_role in add_role_id:
                    assigned = [role for role in roles if role.id == add_role]
                    if not assigned:
                        try:
                            project_identity.add_project_user_role(
                                request,
                                role=add_role,
                                user=new_user.id,
                                project=self.request.user.project_id)
                        except Exception:
                            exceptions.handle(request,
                                              _('Unable to add user '
                                                'to primary project.'))
            return new_user
        except exceptions.Conflict:
            msg = _('User name "%s" is already used.') % data['name']
            messages.error(request, msg)
        except Exception:
            exceptions.handle(request, _('Unable to create user.'))


class UpdateUserForm(BaseUserForm):
    # Hide the domain_id and domain_name by default
    domain_id = forms.CharField(label=_("Domain ID"),
                                required=False,
                                widget=forms.HiddenInput())
    domain_name = forms.CharField(label=_("Domain Name"),
                                  required=False,
                                  widget=forms.HiddenInput())
    id = forms.CharField(label=_("ID"), widget=forms.HiddenInput)
    name = forms.CharField(label=_("User Name"),
                           widget=forms.TextInput(
                               attrs={'readonly': 'readonly'}))
    email = forms.EmailField(
        label=_("Email"))
    project = forms.CharField(label=_("Primary Project"),
                              widget=forms.TextInput(
                                  attrs={'readonly': 'readonly'}))

    def __init__(self, request, *args, **kwargs):
        super(UpdateUserForm, self).__init__(request, *args, **kwargs)

        if api.keystone.keystone_can_edit_user() is False:
            for field in ('name', 'email'):
                self.fields.pop(field)
        # For keystone V3, display the two fields in read-only
        if api.keystone.VERSIONS.active >= 3:
            readonlyInput = forms.TextInput(attrs={'readonly': 'readonly'})
            self.fields["domain_id"].widget = readonlyInput
            self.fields["domain_name"].widget = readonlyInput

    def handle(self, request, data):
        user = data.pop('id')

        data.pop('domain_id')
        data.pop('domain_name')
        data.pop('project')
        try:
            if "email" in data:
                data['email'] = data['email'] or None
            response = project_identity.user_update(request, user, **data)
            messages.success(request,
                             _('User has been updated successfully.'))
        except exceptions.Conflict:
            msg = _('User name "%s" is already used.') % data['name']
            messages.error(request, msg)
            return False
        except Exception:
            response = exceptions.handle(request, ignore=True)
            messages.error(request, _('Unable to update the user.'))

        if isinstance(response, http.HttpResponse):
            return response
        else:
            return True
