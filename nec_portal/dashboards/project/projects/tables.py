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

import logging

from django.core.urlresolvers import reverse
from django.template import defaultfilters as filters
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ungettext_lazy

from openstack_auth import utils as auth_utils

from horizon import tables
from keystoneclient.exceptions import Conflict

from nec_portal.api import project_identity
from nec_portal.local import nec_portal_settings as nec_set

from openstack_dashboard import api
from openstack_dashboard import policy

LOG = logging.getLogger(__name__)
STATUS_CHOICES = (
    ("true", True),
    ("false", False)
)


class UpdateMembersLink(tables.LinkAction):
    name = "users"
    verbose_name = _("Manage Members")
    url = "horizon:project:projects:manage_members"
    icon = "pencil"
    policy_rules = (("identity", "identity:get_project"),)

    def allowed(self, request, project):
        if request.user.project_id == project.id:
            return False
        return api.keystone.keystone_can_edit_project()


class CreateProject(tables.LinkAction):
    name = "create"
    verbose_name = _("Create Project")
    url = "horizon:project:projects:create"
    classes = ("ajax-modal",)
    icon = "plus"
    policy_rules = (('identity', 'identity:create_project'),)

    def allowed(self, request, project):
        return api.keystone.keystone_can_edit_project()


class UpdateProject(tables.LinkAction):
    name = "update"
    verbose_name = _("Edit Project")
    url = "horizon:project:projects:update"
    classes = ("ajax-modal",)
    icon = "pencil"
    policy_rules = (('identity', 'identity:update_project'),)

    def allowed(self, request, project):
        return api.keystone.keystone_can_edit_project()


class DeleteTenantsAction(tables.DeleteAction):
    @staticmethod
    def action_present(count):
        return ungettext_lazy(
            u"Delete Project",
            u"Delete Projects",
            count
        )

    @staticmethod
    def action_past(count):
        return ungettext_lazy(
            u"Deleted Project",
            u"Deleted Projects",
            count
        )

    policy_rules = (("identity", "identity:delete_project"),)

    def allowed(self, request, project):
        if not api.keystone.keystone_can_edit_project() or \
                (project and project.id == request.user.project_id):
            return False
        return True

    def delete(self, request, obj_id):
        # Selected project can not be deleted.
        if request.user.project_id == obj_id:
            raise Conflict
        project_identity.project_delete(request, obj_id)

    def handle(self, table, request, obj_ids):
        response = \
            super(DeleteTenantsAction, self).handle(table, request, obj_ids)
        auth_utils.remove_project_cache(request.user.token.id)
        return response


class TenantFilterAction(tables.FilterAction):
    def filter(self, table, tenants, filter_string):
        """Really naive case-insensitive search."""
        # FIXME(gabriel): This should be smarter. Written for demo purposes.
        q = filter_string.lower()

        def comp(tenant):
            if q in tenant.name.lower():
                return True
            return False

        return filter(comp, tenants)


class UpdateRow(tables.Row):
    ajax = True

    def get_data(self, request, project_id):
        project_info = project_identity.project_get(request, project_id,
                                                    admin=True)
        return project_info

    def load_cells(self, datum=None):
        super(UpdateRow, self).load_cells(datum=datum)
        if hasattr(self.datum, 'parent'):
            self.attrs['data-tt-id'] = self.datum.id
            if self.datum.parent:
                self.attrs['data-tt-parent-id'] = self.datum.parent.id


class TenantsTable(tables.DataTable):
    name = tables.Column('name', verbose_name=_('Name'),
                         link=("horizon:project:projects:detail"))
    description = tables.Column(lambda obj: getattr(obj, 'description', None),
                                verbose_name=_('Description'))
    id = tables.Column('id', verbose_name=_('Project ID'))
    enabled = tables.Column('enabled', verbose_name=_('Enabled'), status=True,
                            filters=(filters.yesno, filters.capfirst))

    def set_immediate_parent(self, projects):
        """Set parent property to immediate parent

        This method treats the case in which the user has access to both a
        project and its immediate parent, setting the parent property of
        the project.

        """
        for project in projects:
            project.parent = None
            for parent in projects:
                if project.parent_id == parent.id:
                    project.parent = parent
                    break

    def get_hierarchical_name(self, project):
        """Return the hierarchical name of the given project

        Given a a project with parent property, return its hierarchical
        name, which is composed by its name added by its parents names,
        separated by slashes.

        """
        name = project.name
        while project.parent:
            name = project.parent.name + ' \ ' + name
            project = project.parent

        return name

    def set_closer_parent(self, projects, request):
        """Set parent property to closer parent

        This method treats the case in which the user has access to a
        project but not to its immediate parent. Then, the project's parent
        property will be set to the closer parent in the hierarchy that the
        user has access to.

        """
        authorized_ids = [p.id for p in projects]

        domain_context = request.session.get('domain_context', None)
        all_projects, more = project_identity.project_list(
            request,
            domain=domain_context)

        for project in projects:
            if project.parent:
                continue

            base_project = filter(lambda p:
                                  p.id == project.id,
                                  all_projects)
            if not base_project:
                continue

            parent_project_id = \
                [p for p in all_projects
                 if p.id == base_project[0].parent_id and
                 p.id in authorized_ids]
            if parent_project_id:
                project.parent = None
                for search_parent_project in projects:
                    if search_parent_project.id == parent_project_id[0].id:
                        project.parent = search_parent_project
                        break

    def get_rows(self):
        projects = self.filtered_data
        if (projects and hasattr(projects[0], 'parent_id')
                and project_identity.VERSIONS.active >= 3):

            self.set_immediate_parent(projects)
            if policy.check((("identity", "identity:get_project"),),
                            self.request):
                self.set_closer_parent(projects, self.request)

        if not projects or not hasattr(projects[0], 'parent'):
            return super(TenantsTable, self).get_rows()

        for project in projects:
            project.immediate_subprojects = []
            for child in projects:
                if child.parent and child.parent.id == project.id:
                    project.immediate_subprojects.append(child)

        for project in projects:
            if project.id == self.request.user.project_id:
                root_projects = [project]
        rows = []
        while root_projects:
            p = root_projects[0]
            row = self._meta.row_class(self, p)
            if self.get_object_id(p) == self.current_item_id:
                self.selected = True
                row.classes.append('current_selected')
            rows.append(row)

            root_projects.remove(p)
            root_projects[0:0] = sorted(p.immediate_subprojects,
                                        key=lambda project: project.name)
        return rows

    class Meta(object):
        name = "tenants"
        verbose_name = _("Projects")
        row_class = UpdateRow
        row_actions = (UpdateMembersLink,
                       UpdateProject,
                       DeleteTenantsAction,)
        table_actions = (TenantFilterAction, CreateProject,
                         DeleteTenantsAction,)
        pagination_param = "tenant_marker"


class UserFilterAction(tables.FilterAction):
    def filter(self, table, users, filter_string):
        """Naive case-insensitive search."""
        q = filter_string.lower()
        return [user for user in users
                if q in user.name.lower()
                or q in (getattr(user, 'email', None) or '').lower()]


class RemoveMembers(tables.DeleteAction):
    @staticmethod
    def action_present(count):
        return ungettext_lazy(
            u"Remove User",
            u"Remove Users",
            count
        )

    @staticmethod
    def action_past(count):
        return ungettext_lazy(
            u"Removed User",
            u"Removed Users",
            count
        )

    name = "remove_project_member"
    policy_rules = (("identity", "identity:update_project"),)

    def allowed(self, request, user=None):
        return api.keystone.keystone_can_edit_project()

    def action(self, request, obj_id):
        user_obj = self.table.get_object_by_id(obj_id)
        project_id = self.table.kwargs['project_id']
        LOG.info('Removing user %s from project %s.' % (user_obj.id,
                                                        project_id))

        groups = project_identity.project_group_list(
            project=project_id)

        for group in groups:
            group_users = project_identity.group_user_list(
                project=project_id,
                group=group.id)
            if user_obj.id in group_users:
                project_identity.remove_group_user(request,
                                                   group_id=group.id,
                                                   user_id=user_obj.id)

        other_project = ''
        projects, _more = project_identity.project_list(request)
        for project in projects:
            if project.id != project_id:
                users = project_identity.project_user_list(project=project.id)
                if user_obj.id in [u.id for u in users]:
                    other_project = project.id
                    break

        if other_project:
            project_identity.user_update_project(request,
                                                 user_obj.id,
                                                 other_project)

            project_identity.remove_project_user(request,
                                                 project=project_id,
                                                 user=user_obj.id)
        else:
            project_identity.user_delete(request,
                                         user_id=user_obj.id)

        # TODO(lin-hua-cheng): Fix the bug when removing current user
        # Keystone revokes the token of the user removed from the group.
        # If the logon user was removed, redirect the user to logout.


class AddMembersLink(tables.LinkAction):
    name = "add_user_link"
    verbose_name = _("Add Users")
    classes = ("ajax-modal",)
    icon = "plus"
    url = 'horizon:project:projects:add_members'
    policy_rules = (("identity", "identity:update_project"),)

    def allowed(self, request, user=None):
        return api.keystone.keystone_can_edit_project()

    def get_link_url(self, datum=None):
        return reverse(self.url, kwargs=self.table.kwargs)


class UsersTable(tables.DataTable):
    name = tables.Column('name', verbose_name=_('User Name'))
    email = tables.Column('email', verbose_name=_('Email'),
                          filters=[filters.escape,
                                   filters.urlize])
    id = tables.Column('id', verbose_name=_('User ID'))
    enabled = tables.Column('enabled', verbose_name=_('Enabled'),
                            status=True,
                            status_choices=STATUS_CHOICES,
                            filters=(filters.yesno,
                                     filters.capfirst),
                            empty_value=_('False'))


class ProjectMembersTable(UsersTable):
    class Meta(object):
        name = "project_members"
        verbose_name = _("Project Members")
        table_actions = (UserFilterAction, AddMembersLink, RemoveMembers)


class AddMembers(tables.BatchAction):
    @staticmethod
    def action_present(count):
        return ungettext_lazy(
            u"Add User",
            u"Add Users",
            count
        )

    @staticmethod
    def action_past(count):
        return ungettext_lazy(
            u"Added User",
            u"Added Users",
            count
        )

    name = "addMember"
    icon = "plus"
    requires_input = True
    success_url = 'horizon:project:projects:manage_members'
    policy_rules = (("identity", "identity:update_project"),)

    def allowed(self, request, user=None):
        return api.keystone.keystone_can_edit_project()

    def action(self, request, obj_id):
        user_obj = self.table.get_object_by_id(obj_id)
        project_id = self.table.kwargs['project_id']
        LOG.info('Adding user %s to project %s.' % (user_obj.id,
                                                    project_id))
        add_roles = getattr(nec_set, 'DEFAULT_USER_ROLES', [])
        all_role = project_identity.role_list(request)
        for role in all_role:
            if role.name in add_roles:
                project_identity.add_project_user_role(request,
                                                       project=project_id,
                                                       user=user_obj.id,
                                                       role=role.id)
        # TODO(lin-hua-cheng): Fix the bug when adding current user
        # Keystone revokes the token of the user added to the group.
        # If the logon user was added, redirect the user to logout.

    def get_success_url(self, request=None):
        project_id = self.table.kwargs.get('project_id', None)
        return reverse(self.success_url, args=[project_id])


class ProjectNonMembersTable(UsersTable):
    class Meta(object):
        name = "project_non_members"
        verbose_name = _("Non-Members")
        table_actions = (UserFilterAction, AddMembers)
