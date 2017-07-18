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
#
# 

from django.core import exceptions as django_exceptions
from django.template import defaultfilters
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ungettext_lazy

from horizon import exceptions as horizon_exceptions
from horizon import forms
from horizon import messages
from horizon import tables
from openstack_dashboard import api
from openstack_dashboard import policy

from nec_portal.api import project_identity

ENABLE = 0
DISABLE = 1


class CreateUserLink(tables.LinkAction):
    name = "create"
    verbose_name = _("Create User")
    url = "horizon:project:users:create"
    classes = ("ajax-modal",)
    icon = "plus"
    policy_rules = (('identity', 'identity:create_grant'),
                    ("identity", "identity:create_user"),)

    def allowed(self, request, user):
        return api.keystone.keystone_can_edit_user()


class EditUserLink(policy.PolicyTargetMixin, tables.LinkAction):
    name = "edit"
    verbose_name = _("Edit")
    url = "horizon:project:users:update"
    classes = ("ajax-modal",)
    icon = "pencil"
    policy_rules = (("identity", "identity:update_user"),)
    policy_target_attrs = (("user_id", "id"),)

    def allowed(self, request, user):
        return api.keystone.keystone_can_edit_user()


class DeleteUsersAction(tables.DeleteAction):
    @staticmethod
    def action_present(count):
        return ungettext_lazy(
            u"Delete User",
            u"Delete Users",
            count
        )

    @staticmethod
    def action_past(count):
        return ungettext_lazy(
            u"Deleted User",
            u"Deleted Users",
            count
        )
    policy_rules = (("identity", "identity:delete_user"),)

    def allowed(self, request, datum):
        if not api.keystone.keystone_can_edit_user() or \
                (datum and datum.id == request.user.id):
            return False
        return True

    def delete(self, request, obj_id):
        other_project = ''
        projects, _more = project_identity.project_list(request)
        for project in projects:
            if project.id != request.user.project_id:
                users = project_identity.project_user_list(project=project.id)
                if obj_id in [u.id for u in users]:
                    other_project = project.id
                    break

        if other_project:
            groups = project_identity.project_group_list(
                project=request.user.project_id)

            for group in groups:
                group_users = project_identity.group_user_list(
                    project=request.user.project_id,
                    group=group.id)
                if obj_id in group_users:
                    project_identity.remove_group_user(request,
                                                       group_id=group.id,
                                                       user_id=obj_id)

            project_identity.user_update_project(request, obj_id,
                                                 other_project)

            role_list = project_identity.users_role_list(request, obj_id)

            for role in role_list:
                project_identity.remove_project_user_role(
                    request,
                    project=request.user.project_id,
                    user=obj_id,
                    role=role)
        else:
            project_identity.user_delete(request,
                                         user_id=obj_id)


class UserFilterAction(tables.FilterAction):
    def filter(self, table, users, filter_string):
        """Naive case-insensitive search."""
        q = filter_string.lower()
        return [user for user in users
                if q in user.name.lower()
                or q in (getattr(user, 'email', None) or '').lower()]


class UpdateRow(tables.Row):
    ajax = True

    def get_data(self, request, user_id):
        user_info = api.keystone.user_get(request, user_id, admin=True)
        return user_info


class UpdateCell(tables.UpdateAction):
    def allowed(self, request, user, cell):
        return api.keystone.keystone_can_edit_user() and \
            policy.check((("identity", "identity:update_user"),),
                         request)

    def update_cell(self, request, datum, user_id,
                    cell_name, new_cell_value):
        try:
            user_obj = datum
            setattr(user_obj, cell_name, new_cell_value)
            project_identity.user_update(
                request,
                user_obj,
                name=user_obj.name,
                email=user_obj.email,
                enabled=user_obj.enabled,
                project=user_obj.project_id,
                password=None)

        except horizon_exceptions.Conflict:
            message = _("This name is already taken.")
            messages.warning(request, message)
            raise django_exceptions.ValidationError(message)
        except Exception:
            horizon_exceptions.handle(request, ignore=True)
            return False
        return True


class UsersTable(tables.DataTable):
    STATUS_CHOICES = (
        ("true", True),
        ("false", False)
    )
    name = tables.Column('name',
                         link="horizon:project:users:detail",
                         verbose_name=_('User Name'),
                         form_field=forms.CharField())
    email = tables.Column('email', verbose_name=_('Email'),
                          form_field=forms.CharField(),
                          update_action=UpdateCell,
                          filters=(lambda v: defaultfilters
                                   .default_if_none(v, ""),
                                   defaultfilters.escape,
                                   defaultfilters.urlize)
                          )
    # Default tenant is not returned from Keystone currently.
    # default_tenant = tables.Column('default_tenant',
    #                               verbose_name=_('Default Project'))
    id = tables.Column('id', verbose_name=_('User ID'),
                       attrs={'data-type': 'uuid'})
    enabled = tables.Column('enabled', verbose_name=_('Enabled'),
                            status=True,
                            status_choices=STATUS_CHOICES,
                            filters=(defaultfilters.yesno,
                                     defaultfilters.capfirst),
                            empty_value="False")

    class Meta(object):
        name = "users"
        verbose_name = _("Users")
        row_actions = (EditUserLink, DeleteUsersAction)
        table_actions = (UserFilterAction, CreateUserLink, DeleteUsersAction)
        row_class = UpdateRow
