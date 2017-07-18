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

KEYSTONE_ADMIN_SETTING = {
    'username': 'admin',
    'password': 'xxxx',
    'tenant_name': 'admin',
    'auth_url': 'http://127.0.0.1:5000/v3',
    'region_name': ''
}

DEFAULT_ROLES = ['_member_', ]
DEFAULT_USER_ROLES = DEFAULT_ROLES
DEFAULT_GROUP_ROLES = DEFAULT_ROLES

# Roles which are defined in this setting
# are not inherited when creating a child project.
DISINHERITED_ROLES = [
    "T__DC1__ObjectStore",
    "T__DC2__ObjectStore",
    "T__DC3__ObjectStore",
]

TBL_ROLE_COMMON = {
    'initial': 'C',
    'policy': '',
    'name': _('Common Roles'),
}

TBL_ROLE_OPERATOR = {
    'initial': 'O',
    'policy': 'admin',
    'name': _('Operator Roles'),
}

TBL_ROLE_TENANT_USER = {
    'initial': 'T',
    'policy': '',
    'name': _('Tenant User Roles'),
}

TBL_ROLE_ALL = [
    TBL_ROLE_COMMON,
    TBL_ROLE_OPERATOR,
    TBL_ROLE_TENANT_USER,
]
