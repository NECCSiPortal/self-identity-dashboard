#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.
#

import collections
import logging

from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from openstack_auth import utils as auth_utils
from openstack_dashboard import api
from openstack_dashboard.api import base

import keystoneclient
from keystoneclient import exceptions as keystone_exceptions

from horizon import exceptions
from horizon.utils import functions as utils

from nec_portal.local import nec_portal_settings as nec_set

LOG = logging.getLogger(__name__)
DEFAULT_ROLE = None
KEYSTONE_ADMIN_SETTING = getattr(nec_set, 'KEYSTONE_ADMIN_SETTING', None)


# Set up our data structure for managing Identity API versions, and
# add a couple utility methods to it.
class IdentityAPIVersionManager(base.APIVersionManager):
    def upgrade_v2_user(self, user):
        if getattr(user, "project_id", None) is None:
            user.project_id = getattr(user, "default_project_id",
                                      getattr(user, "tenantId", None))
        return user

    def get_project_manager(self, *args, **kwargs):
        if VERSIONS.active < 3:
            manager = keystoneclient(*args, **kwargs).tenants
        else:
            manager = keystoneclient(*args, **kwargs).projects
        return manager


VERSIONS = IdentityAPIVersionManager(
    "identity", preferred_version=auth_utils.get_keystone_version())


# Import from oldest to newest so that "preferred" takes correct precedence.
try:
    from keystoneclient.v2_0 import client as keystone_client_v2
    VERSIONS.load_supported_version(2.0, {"client": keystone_client_v2})
except ImportError:
    pass

try:
    from keystoneclient.v3 import client as keystone_client_v3
    VERSIONS.load_supported_version(3, {"client": keystone_client_v3})
except ImportError:
    pass


def get_keystone_client():

    api_version = VERSIONS.get_active_version()

    return api_version['client'].Client(
        username=KEYSTONE_ADMIN_SETTING['username'],
        password=KEYSTONE_ADMIN_SETTING['password'],
        tenant_name=KEYSTONE_ADMIN_SETTING['tenant_name'],
        auth_url=KEYSTONE_ADMIN_SETTING['auth_url'],
        region_name=KEYSTONE_ADMIN_SETTING.get('region_name', None))


def get_default_domain(request):
    domain_id = request.session.get("domain_context", None)
    domain_name = request.session.get("domain_context_name", None)
    # if running in Keystone V3 or later
    if VERSIONS.active >= 3 and not domain_id:
        # if no domain context set, default to users' domain
        domain_id = request.user.user_domain_id
        try:
            domain = domain_get(request, domain_id)
            domain_name = domain.name
        except Exception:
            LOG.warning("Unable to retrieve Domain: %s" % domain_id)
    domain = base.APIDictWrapper({"id": domain_id,
                                  "name": domain_name})
    return domain


def domain_get(request, domain_id):
    keystoneclient = get_keystone_client()
    return keystoneclient.domains.get(domain_id)


def project_user_list(project=None, domain=None, group=None, filters=None):

    users_roles = []
    keystoneclient = get_keystone_client()
    project_users = keystoneclient.role_assignments.list(project=project)

    for project_user in project_users:
        if not hasattr(project_user, 'user'):
            continue
        user_id = project_user.user['id']
        users_roles.append(user_id)

    ret_users = []
    all_users = keystoneclient.users.list()
    for user_data in all_users:
        if user_data.id in users_roles:
            ret_users.append(user_data)

    return ret_users


def role_assignments_list(request, project=None, user=None, role=None,
                          group=None, domain=None, effective=False):
    if VERSIONS.active < 3:
        raise exceptions.NotAvailable

    keystoneclient = get_keystone_client()
    return keystoneclient.role_assignments.list(project=project,
                                                user=user,
                                                role=role,
                                                group=group,
                                                domain=domain,
                                                effective=effective)


def get_default_role(request):
    global DEFAULT_ROLE
    default = getattr(settings, "OPENSTACK_KEYSTONE_DEFAULT_ROLE", None)
    if default and DEFAULT_ROLE is None:
        try:
            keystoneclient = get_keystone_client()
            roles = keystoneclient.roles.list()
        except Exception:
            roles = []
            exceptions.handle(request)
        for role in roles:
            if role.id == default or role.name == default:
                DEFAULT_ROLE = role
                break
    return DEFAULT_ROLE


def role_list(request):
    """Returns a global list of available roles."""
    keystoneclient = get_keystone_client()
    return keystoneclient.roles.list()


def roles_for_user(request, user, project=None, domain=None):
    """Returns a list of user roles scoped to a project or domain."""
    keystoneclient = get_keystone_client()
    if VERSIONS.active < 3:
        return keystoneclient.roles.roles_for_user(user, project)
    else:
        return keystoneclient.roles.list(user=user,
                                         domain=domain,
                                         project=project)


def users_role_list(request, user_id):
    keystoneclient = get_keystone_client()
    return keystoneclient.roles.list(user=user_id,
                                     project=request.user.project_id)


def user_get(request, user_id):
    user = get_keystone_client().users.get(user=user_id)
    return VERSIONS.upgrade_v2_user(user)


def user_create(request, name=None, email=None, password=None, project=None,
                enabled=None, domain=None):
    keystoneclient = get_keystone_client()
    try:
        if VERSIONS.active < 3:
            user = keystoneclient.users.create(name, password, email,
                                               project, enabled)
            return VERSIONS.upgrade_v2_user(user)
        else:
            return keystoneclient.users.create(name, password=password,
                                               email=email, project=project,
                                               enabled=enabled, domain=domain)
    except keystone_exceptions.Conflict:
        raise exceptions.Conflict()


def user_list(request, project=None, domain=None, group=None, filters=None):
    if VERSIONS.active < 3:
        kwargs = {"tenant_id": project}
    else:
        kwargs = {
            "project": project,
            "domain": domain,
            "group": group
        }
        if filters is not None:
            kwargs.update(filters)
    keystoneclient = get_keystone_client()
    users = keystoneclient.users.list(**kwargs)
    return [VERSIONS.upgrade_v2_user(user) for user in users]


def user_update(request, user, **data):
    keystoneclient = get_keystone_client()
    error = None

    if not api.keystone.keystone_can_edit_user():
        raise keystone_exceptions.ClientException(
            405, _("Identity service does not allow editing user data."))

    # The v2 API updates user model and default project separately
    if VERSIONS.active < 3:
        project = data.pop('project')

        # Update user details
        try:
            user = keystoneclient.users.update(user, **data)
        except keystone_exceptions.Conflict:
            raise exceptions.Conflict()
        except Exception:
            error = exceptions.handle(request, ignore=True)

        # Update default tenant
        try:
            user_update_project(request, user, project)
            user.tenantId = project
        except Exception:
            error = exceptions.handle(request, ignore=True)

        # Check for existing roles
        # Show a warning if no role exists for the project
        roles_for_user(request, user, project)

        if error is not None:
            raise error

    # v3 API is so much simpler...
    else:
        try:
            user = keystoneclient.users.update(user, **data)
        except keystone_exceptions.Conflict:
            raise exceptions.Conflict()


def user_delete(request, user_id):
    keystoneclient = get_keystone_client()
    return keystoneclient.users.delete(user_id)


def user_update_project(request, user, project, admin=True):
    keystoneclient = get_keystone_client()
    if VERSIONS.active < 3:
        return keystoneclient.users.update_tenant(user, project)
    else:
        return keystoneclient.users.update(user, project=project)


def add_project_user_role(
        request, project=None, user=None, role=None, group=None):
    """Adds a role for a user on a tenant."""
    keystoneclient = get_keystone_client()
    if VERSIONS.active < 3:
        return keystoneclient.roles.add_user_role(user, role, project)
    else:
        return keystoneclient.roles.grant(
            role, user=user, project=project, group=group)


def remove_project_user_role(request, project, user, role, domain=None):
    keystoneclient = get_keystone_client()
    return keystoneclient.roles.revoke(role, user=user,
                                       project=project, domain=domain)


def remove_project_user(request, project=None, user=None, domain=None):
    """Removes all roles from a user on a tenant, removing them from it."""
    get_keystone_client()
    roles = roles_for_user(request, user, project)
    for role in roles:
        remove_project_user_role(request, user=user, role=role.id,
                                 project=project, domain=domain)


def project_get(request, project, admin=True, parents=False):
    keystoneclient = get_keystone_client()
    kwargs = {'parents_as_list': True} if parents else {}
    return keystoneclient.projects.get(project, **kwargs)


def project_create(request, name, description=None, enabled=None,
                   domain=None, **kwargs):
    keystoneclient = get_keystone_client()
    if VERSIONS.active < 3:
        return keystoneclient.projects.create(name,
                                              description,
                                              enabled,
                                              **kwargs)
    else:
        return keystoneclient.projects.create(name,
                                              domain,
                                              description=description,
                                              enabled=enabled,
                                              **kwargs)


def project_delete(request, project):
    keystoneclient = get_keystone_client()
    return keystoneclient.projects.delete(project)


def project_list(request, paginate=False, marker=None, domain=None, user=None,
                 admin=True, filters=None):
    keystoneclient = get_keystone_client()
    page_size = utils.get_page_size(request)

    limit = None
    if paginate:
        limit = page_size + 1

    has_more_data = False

    # if requesting the projects for the current user,
    # return the list from the cache
    if user == request.user.id:
        projects = request.user.authorized_tenants

    elif VERSIONS.active < 3:
        projects = keystoneclient.projects.list(limit, marker)
        if paginate and len(projects) > page_size:
            projects.pop(-1)
            has_more_data = True
    else:
        kwargs = {
            "domain": domain,
            "user": user
        }
        if filters is not None:
            kwargs.update(filters)
        projects = keystoneclient.projects.list(**kwargs)
    return (projects, has_more_data)


def project_update(request, project, name=None, description=None,
                   enabled=None, domain=None, **kwargs):
    keystoneclient = get_keystone_client()
    if VERSIONS.active < 3:
        return keystoneclient.projects.update(project,
                                              name,
                                              description,
                                              enabled,
                                              **kwargs)
    else:
        return keystoneclient.projects.update(project,
                                              name=name,
                                              description=description,
                                              enabled=enabled,
                                              domain=domain,
                                              **kwargs)


def group_get(request, group):
    keystoneclient = get_keystone_client()
    return keystoneclient.groups.get(group)


def group_user_list(project=None, domain=None, group=None, filters=None):
    keystoneclient = get_keystone_client()
    group_users = keystoneclient.users.list(group=group)
    project_users = keystoneclient.role_assignments.list(project=project)

    project_user_ids = []
    for project_user in project_users:
        if not hasattr(project_user, 'user'):
            continue
        user_id = project_user.user['id']
        project_user_ids.append(user_id)

    ret_users = []
    for group_data in group_users:
        if group_data.id in project_user_ids:
            ret_users.append(group_data)

    return ret_users


def get_project_users_roles(request, project):
    users_roles = collections.defaultdict(list)
    if VERSIONS.active < 3:
        project_users = user_list(request, project=project)

        for user in project_users:
            roles = roles_for_user(request, user.id, project)
            roles_ids = [role.id for role in roles]
            users_roles[user.id].extend(roles_ids)
    else:
        project_role_assignments = role_assignments_list(request,
                                                         project=project)
        for role_assignment in project_role_assignments:
            if not hasattr(role_assignment, 'user'):
                continue
            user_id = role_assignment.user['id']
            role_id = role_assignment.role['id']
            users_roles[user_id].append(role_id)
    return users_roles


def roles_for_group(request, group, project):
    keystoneclient = get_keystone_client()
    return keystoneclient.roles.list(group=group, project=project)


def add_group_role(request, role, group, project):
    keystoneclient = get_keystone_client()
    return keystoneclient.roles.grant(role=role, group=group, project=project)


def remove_group_role(request, role, group, project):
    keystoneclient = get_keystone_client()
    return keystoneclient.roles.revoke(role=role, group=group,
                                       project=project)


def project_group_list(project=None, domain=None, group=None, filters=None):
    project_group_ids = []
    keystoneclient = get_keystone_client()
    project_groups = keystoneclient.role_assignments.list(project=project)

    for project_group in project_groups:
        if not hasattr(project_group, 'group'):
            continue
        group_id = project_group.group['id']
        project_group_ids.append(group_id)

    ret_groups = []
    all_groups = keystoneclient.groups.list(domain=domain)
    for user_data in all_groups:
        if user_data.id in project_group_ids:
            ret_groups.append(user_data)

    return ret_groups


def group_create(request, domain_id, name, description=None):
    keystoneclient = get_keystone_client()
    return keystoneclient.groups.create(domain=domain_id,
                                        name=name,
                                        description=description)


def group_update(request, group_id, name=None, description=None):
    keystoneclient = get_keystone_client()
    return keystoneclient.groups.update(group=group_id,
                                        name=name,
                                        description=description)


def add_group_user(request, group_id, user_id):
    keystoneclient = get_keystone_client()
    return keystoneclient.users.add_to_group(group=group_id, user=user_id)


def remove_group_user(request, group_id, user_id):
    keystoneclient = get_keystone_client()
    return keystoneclient.users.remove_from_group(group=group_id, user=user_id)


def group_delete(request, group_id):
    keystoneclient = get_keystone_client()
    return keystoneclient.groups.delete(group_id)
