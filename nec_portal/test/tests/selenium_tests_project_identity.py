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
#


"""Test 'Self Identity'.
Please operate setting.
  Step1. Create Projects
    - admin
  Step2. Create Users
    - admin
  Step3. Create Roles
    - C__Global__ProjectAdmin
  Step4. Setup Plilcy Files(for GlobalPortal DC1)
    - /etc/openstack-dashboard/keystone_policy.json
    - systemctl restart httpd
  Step5. Change Selenium Parameters
    - SET_BASE_URL
"""

import datetime
import os
import time
import traceback

from horizon.test import helpers as test

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait


# Command executor. Hub URL of Jenkins.
SET_COMMAND_EXECUTOR = 'http://127.0.0.1:4444/wd/hub'
# Base URL. Environment for testing.
SET_BASE_URL = 'http://127.0.0.1/dashboard'
# Login user.
SET_USER = {
    'admin': {
        'USERNM': 'admin',
        'PASSWORD': 'xxxx'
    },
    '!!!test_userA': {
        'USERNM': '!!!test_userA',
        'PASSWORD': 'xxxx'
    },
}
# Width of the window
SET_WIDTH = 1280
# Height of the window
SET_HEIGHT = 1024
# Implicitly wait
SET_IMPLICITLY_WAIT = 30
SET_TIMEOUT = 5
SET_LONG_WAIT = 30
# Capture of location
SET_CAPPATH = 'openstack_dashboard/test/tests/screenshots/'
# They are arranged sequentially by setting the execution target.
SET_METHOD_LIST = [
    # Pre-processing
    'sign_in_admin',
    'change_setting',
    'create_default_project',
    'create_default_user',
    'add_role',
    'sign_out',

    # Main
    'sign_in_projectA',
    'create_project',
    'update_project',
    'create_user',
    'update_user',
    'add_project_user',
    'sign_out',

    'sign_in_projectB',
    'create_group',
    'update_group',
    'add_group_user',
    'delete_group_user',
    'delete_group',
    'sign_out',

    'sign_in_projectA',
    'delete_project_user',
    'delete_user',
    'delete_project',
    'sign_out',

    # Post-processing
    'sign_in_admin',
    'delete_default_user',
    'delete_default_project',
    'sign_out',
]

# They are arranged sequentially by setting the browser target
SET_BROWSER_LIST = {
    'firefox': {
        'browserName': 'firefox',
        'version': '',
        'platform': 'ANY',
        'javascriptEnabled': True,
    },
    'chrome': {
        'browserName': 'chrome',
        'version': '',
        'platform': 'ANY',
        'javascriptEnabled': True,
    },
    'ie11': {
        'browserName': 'internet explorer',
        'version': '11',
        'platform': 'WINDOWS',
        'javascriptEnabled': True,
    }
}

# Take the capture
SET_CAPFLG = True
# Test language pattern.
SET_TEST_LANGUAGE = {
    'en': True,
    'ja': True,
}
# Test browser pattern.
SET_TEST_BROWSER = {
    'firefox': True,
    'chrome': True,
    'ie11': True,
}

CREATE_PROJECT_A = '!!!test_projectA'
CREATE_USER_A = '!!!test_userA'

CREATE_PROJECT_B = '!!!test_projectB'
CREATE_USER_B = '!!!test_userB'
CRAETE_GROUP_B = '!!!test_groupB'


class BrowserTests(test.SeleniumTestCase):
    """This test will output the capture of announcens."""

    def setUp(self):
        """Set the Remote instance of WebDriver."""

        super(BrowserTests, self).setUp()

        # One setting of the browser is necessary
        # to carry out a test of selenium.
        key = SET_BROWSER_LIST.keys()[0]
        value = SET_BROWSER_LIST[key]

        print (value)
        self.caps = key
        self.selenium = webdriver.Remote(
            command_executor=SET_COMMAND_EXECUTOR,
            desired_capabilities=value)

        self.selenium.implicitly_wait(SET_IMPLICITLY_WAIT)

    def initialize(self):
        """Initializing process."""

        # Capture count.
        self.cap_count = 1

        # Method name
        self.method = ''

    def test_main(self):
        """Main execution method"""
        try:
            # Datetime.
            self.datetime = datetime.datetime.today().strftime('%Y%m%d%H%M%S')

            # Browser order definition.
            for key, value in SET_BROWSER_LIST.items():
                if key not in SET_TEST_BROWSER or \
                        not SET_TEST_BROWSER[key]:
                    continue

                if not self.caps == key:
                    self.caps = key
                    self.selenium = webdriver.Remote(
                        command_executor=SET_COMMAND_EXECUTOR,
                        desired_capabilities=value)

                    self.selenium.implicitly_wait(SET_IMPLICITLY_WAIT)

                # Browser display waiting time.
                self.selenium.implicitly_wait(SET_IMPLICITLY_WAIT)
                # Set the size of the window.
                self.selenium.set_window_size(SET_WIDTH, SET_HEIGHT)

                for language, flg in SET_TEST_LANGUAGE.items():
                    if not flg:
                        continue

                    print ('Test language = [' + language + ']')

                    # Initializing process
                    self.initialize()
                    # Object language
                    self.multiple_languages = language
                    # Call execution method
                    self.execution()

            print ('Test has been completed')

        except Exception as e:
            print (' Test Failure:' + e.message)
            print (traceback.print_exc())

    def execution(self):
        """Execution method"""
        # Method execution order definition.
        for self.method in SET_METHOD_LIST:
            try:
                method = getattr(self, self.method)
                method()

                print (' Success:' + self.caps + ':' + self.method)
            except Exception as e:
                print (' Failure:' + self.caps + ':' + self.method +
                       ':' + e.message)
                print (traceback.print_exc())

    def save_screenshot(self):
        """Save a screenshot"""
        if SET_CAPFLG:
            filepath = SET_CAPPATH + self.datetime + '/' + \
                self.multiple_languages + '/' + self.caps + '/'
            filename = str(self.cap_count).zfill(4) + \
                '_' + self.method + '.png'
            # Make directory.
            if not os.path.isdir(filepath):
                os.makedirs(filepath)

            time.sleep(SET_TIMEOUT)
            self.selenium.get_screenshot_as_file(filepath + filename)
            self.cap_count = self.cap_count + 1

    def trans(self, urlpath, timeout=SET_TIMEOUT):
        """Transition to function. No wait."""

        time.sleep(timeout)
        self.selenium.get(SET_BASE_URL + urlpath)

    def trans_and_wait(self, nextId, urlpath, timeout=SET_TIMEOUT):
        """Transition to function."""

        time.sleep(timeout)
        self.selenium.get(SET_BASE_URL + urlpath)

        if nextId:
            self.wait_id(nextId, SET_TIMEOUT)

        time.sleep(timeout)

    def fill_field(self, field_id, value):
        """Enter a value to the field."""

        self.fill_field_clear(field_id)
        if type(value) in (int, long):
            value = str(value)
        while 0 < len(value):
            split_value = value[0:10]
            self.selenium.find_element_by_id(field_id).send_keys(split_value)
            value = value[10:]

    def fill_field_clear(self, field_id):
        """Clear to the field."""

        time.sleep(SET_TIMEOUT)
        self.selenium.find_element_by_id(field_id).clear()

    def click_and_wait(self, id, nextId, timeout=SET_TIMEOUT):
        """Click on the button."""

        time.sleep(timeout)
        element = self.selenium.find_element_by_id(id)
        element.click()
        self.wait_id(nextId, timeout)

    def click_and_sleep(self, field_id, timeout=SET_TIMEOUT):
        """Click on the button"""
        element = self.selenium.find_element_by_id(field_id)
        element.click()
        time.sleep(timeout)

    def click_xpath(self, xpath, timeout=SET_TIMEOUT):
        """Click on the button xpath"""
        time.sleep(timeout)
        element = self.selenium.find_element_by_xpath(xpath)
        element.click()

    def click_id(self, id, timeout=SET_TIMEOUT):
        """Click on the button."""

        time.sleep(timeout)
        element = self.selenium.find_element_by_id(id)
        element.click()

    def click_css(self, css, timeout=SET_TIMEOUT):
        """Click on the button css. (no wait)"""
        time.sleep(timeout)
        element = self.selenium.find_element_by_css_selector(css)
        element.click()

    def click_xpath_and_ajax_wait(self, xpath, timeout=SET_TIMEOUT):
        """Click on the button xpath ajax wait"""
        time.sleep(timeout)
        element = self.selenium.find_element_by_xpath(xpath)
        self.selenium.execute_script(
            'arguments[0].scrollIntoView(true);', element)
        element.click()
        self.wait_ajax(timeout)

    def set_select_value(self, id, value):
        """Set of pull-down menu by value."""
        time.sleep(SET_TIMEOUT)
        Select(self.selenium.find_element_by_id(id)).select_by_value(value)

    def set_select_visible_text(self, id, value):
        """Set of pull-down menu by value"""
        Select(self.selenium.find_element_by_id(id)). \
            select_by_visible_text(value)

    def wait_id(self, nextId, timeout=SET_TIMEOUT):
        """Wait until the ID that you want to schedule is displayed"""
        WebDriverWait(self.selenium, timeout).until(
            EC.visibility_of_element_located((By.ID, nextId)))

    def wait_css(self, nextCss, timeout=SET_TIMEOUT):
        """Wait until the ID that you want to schedule is displayed"""
        WebDriverWait(self.selenium, timeout).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, nextCss)))

    def wait_ajax(self, timeout=SET_TIMEOUT):
        """Wait until ajax request is completed"""
        WebDriverWait(self.selenium, timeout).until(
            lambda s: s.execute_script('return jQuery.active == 0'))

    def change_setting(self):
        """Change Language"""
        self.trans('/settings/')
        self.set_select_value('id_language', self.multiple_languages)
        self.click_css('input[type=submit]')

    def sign_out(self):
        """Sign Out."""

        # Run to sign out
        self.trans_and_wait('loginBtn', '/auth/logout/')

    def sign_in_admin(self):
        """Sign in admin user"""
        self._sign_in()

    def sign_in_projectA(self):
        """Sign in project user"""
        self._sign_in(username=CREATE_USER_A, project=CREATE_PROJECT_A)

    def sign_in_projectB(self):
        """Sign in project user"""
        self._sign_in(username=CREATE_USER_A, project=CREATE_PROJECT_B)

    def _sign_in(self, username='admin', project='admin'):
        """Sign In."""
        # Run a sign-in
        self.trans('')

        self.fill_field('id_username', SET_USER.get(username).get('USERNM'))
        self.fill_field('id_password', SET_USER.get(username).get('PASSWORD'))

        self.click_id('loginBtn')

        # Set project.
        self._select_project(project)

        self.save_screenshot()

    def _select_project(self, project_name='demo'):
        """Select project name"""
        time.sleep(SET_TIMEOUT)
        self.click_css('span.fa-caret-down')

        time.sleep(SET_LONG_WAIT)
        self.click_xpath(
            '//span[@class="dropdown-title"][contains(text(),"%s")]'
            % project_name)

    # ==================================================

    def create_default_project(self):
        self.trans('/identity/')
        time.sleep(SET_LONG_WAIT)

        self.click_and_sleep('tenants__action_create', SET_LONG_WAIT)

        self.fill_field('id_name', CREATE_PROJECT_A)
        self.save_screenshot()

        self.click_css('input[type=submit]')
        self.save_screenshot()

    def delete_default_project(self):

        self.trans('/identity/')
        time.sleep(SET_LONG_WAIT)

        self.click_xpath(
            '//tr[td[div[div[a[contains(./text(),"%s")]]]]]//label'
            % CREATE_PROJECT_A)
        self.click_and_sleep('tenants__action_delete', SET_LONG_WAIT)
        self.save_screenshot()

        self.click_css('a.btn-primary')
        self.save_screenshot()

    # ==================================================

    def create_default_user(self):

        self.trans('/identity/users/')
        time.sleep(SET_LONG_WAIT)

        self.click_and_sleep('users__action_create', SET_LONG_WAIT)

        self.fill_field_clear('id_name')
        self.fill_field('id_name', CREATE_USER_A)
        self.fill_field_clear('id_password')
        self.fill_field('id_password', 'xxxx')
        self.fill_field_clear('id_confirm_password')
        self.fill_field('id_confirm_password', 'xxxx')
        self.set_select_visible_text('id_project', CREATE_PROJECT_A)
        self.save_screenshot()

        self.click_css('input[type=submit]')
        self.save_screenshot()

    def delete_default_user(self):

        self.trans('/identity/users/')
        time.sleep(SET_LONG_WAIT)

        self.click_xpath_and_ajax_wait(
            '//tr[td[div[div[a[contains(./text(),"%s")]]]]]//label'
            % CREATE_USER_A)
        self.click_and_sleep('users__action_delete', SET_LONG_WAIT)
        self.save_screenshot()

        self.click_css('a.btn-primary')
        self.save_screenshot()

    # ==================================================

    def add_role(self):

        self.trans('/identity/')
        time.sleep(SET_LONG_WAIT)

        # Open role form
        self.click_xpath(
            '//tr[td[div[div[a[contains(./text(),"%s")]]]]]'
            '//a[contains(@href, "update_members")]' % CREATE_PROJECT_A)

        drop_down_xpath = '//div[@id="update_members_members"]'
        '//ul[li[span[contains(./text(),"%s")]]]' % CREATE_USER_A

        # Open role dorp down
        time.sleep(SET_TIMEOUT)
        self.click_xpath(drop_down_xpath + '//a[@href="#"]')
        time.sleep(SET_TIMEOUT)
        # Add admin role
        self.click_xpath(
            drop_down_xpath +
            '//ul//li[a[contains(./text(),"C__Global__ProjectAdmin")]]')

        # Save
        self.click_css('input[type=submit]')

        self.save_screenshot()

    # ==================================================

    def create_project(self):

        self.trans('/project/projects/')
        time.sleep(SET_LONG_WAIT)

        self.click_and_sleep('tenants__action_create', SET_LONG_WAIT)
        self.fill_field_clear('id_name')
        self.fill_field('id_name', CREATE_PROJECT_B)
        self.save_screenshot()

        self.click_css('input[type=submit]')
        self.save_screenshot()

    def update_project(self):

        self.trans('/project/projects/')
        time.sleep(SET_LONG_WAIT)

        self.click_css("a[title=\"Expand\"]")

        update_xpath = '//tr[td[a[contains(./text(),"%s")]]]' \
            % CREATE_PROJECT_B

        self.click_xpath(update_xpath + '//a[@href="#"]')
        self.click_xpath(update_xpath + '//a[contains(@href,"/update/")]')
        self.fill_field_clear('id_description')
        self.fill_field('id_description', 'test_projectB')
        self.save_screenshot()

        self.click_css('input[type=submit]')
        self.save_screenshot()

    def delete_project(self):

        self.trans('/project/projects/')
        time.sleep(SET_LONG_WAIT)

        self.click_css("a[title=\"Expand\"]")

        delete_xpath = '//tr[td[a[contains(./text(),"%s")]]]' \
            % CREATE_PROJECT_B

        self.click_xpath(delete_xpath + '//label')
        time.sleep(SET_TIMEOUT)
        self.click_and_sleep('tenants__action_delete', SET_LONG_WAIT)
        self.save_screenshot()

        self.click_css('a.btn-primary')
        self.save_screenshot()

    # ==================================================

    def add_project_user(self):

        self.trans('/project/projects/')
        time.sleep(SET_LONG_WAIT)

        self.click_css("a[title=\"Expand\"]")

        update_xpath = '//tr[td[a[contains(./text(),"%s")]]]' \
            % CREATE_PROJECT_B

        self.click_xpath(
            update_xpath + '//a[contains(@href,"/manage_members/")]')

        self.click_and_sleep('project_members__action_add_user_link',
                             SET_LONG_WAIT)

        self.click_xpath(
            '//tr[td[contains(./text(),"%s")]]//label' % CREATE_USER_B)
        self.click_and_sleep('project_non_members__action_addMember',
                             SET_LONG_WAIT)
        self.save_screenshot()

        self.selenium.find_element_by_link_text(CREATE_USER_A).click()
        self.save_screenshot()

    def delete_project_user(self):

        self.trans('/project/projects/')
        time.sleep(SET_LONG_WAIT)

        self.click_css("a[title=\"Expand\"]")

        update_xpath = '//tr[td[a[contains(./text(),"%s")]]]' \
            % CREATE_PROJECT_B

        self.click_xpath(
            update_xpath + '//a[contains(@href,"/manage_members/")]')

        self.click_xpath(
            '//tr[td[contains(./text(),"%s")]]//label' % CREATE_USER_B)
        time.sleep(SET_TIMEOUT)
        self.click_and_sleep('project_members__action_remove_project_member',
                             SET_LONG_WAIT)
        self.save_screenshot()

        self.click_css('a.btn-primary')
        self.save_screenshot()

    # ==================================================

    def create_user(self):

        self.trans('/project/users/')
        time.sleep(SET_LONG_WAIT)

        self.click_and_sleep('users__action_create', SET_LONG_WAIT)
        self.fill_field_clear('id_password')
        self.fill_field('id_password', 'xxxx')
        self.fill_field_clear('id_confirm_password')
        self.fill_field('id_confirm_password', 'xxxx')
        self.fill_field_clear('id_name')
        self.fill_field('id_name', CREATE_USER_B)
        self.fill_field_clear('id_email')
        self.fill_field('id_email', 'test_userB@example.com')
        self.click_css('input.btn.btn-primary')
        self.save_screenshot()

        self.selenium.find_element_by_link_text(CREATE_USER_B).click()
        self.save_screenshot()

    def update_user(self):

        self.trans('/project/users/')
        time.sleep(SET_LONG_WAIT)

        update_xpath = '//tr[td[a[contains(./text(),"%s")]]]' \
            % CREATE_USER_B

        self.click_xpath(
            update_xpath + '//a[contains(@href,"/update/")]')

        self.fill_field_clear('id_email')
        self.fill_field('id_email', 'test_userBB@example.com')
        self.save_screenshot()

        self.click_css('input[type=submit]')
        self.save_screenshot()

    def delete_user(self):

        self.trans('/project/users/')
        time.sleep(SET_LONG_WAIT)

        delete_xpath = '//tr[td[a[contains(./text(),"%s")]]]' \
            % CREATE_USER_B

        self.click_xpath(delete_xpath + '//label')

        self.click_and_sleep('users__action_delete', SET_LONG_WAIT)
        self.save_screenshot()

        self.click_css('a.btn-primary')
        self.save_screenshot()

    # ==================================================

    def create_group(self):

        self.trans('/project/groups/')
        time.sleep(SET_LONG_WAIT)

        self.click_and_sleep('groups__action_create', SET_LONG_WAIT)
        self.fill_field_clear('id_name')
        self.fill_field('id_name', CRAETE_GROUP_B)
        self.fill_field_clear('id_description')
        self.fill_field('id_description', 'test_groupB')
        self.save_screenshot()

        self.click_css('input[type=submit]')
        self.save_screenshot()

    def update_group(self):

        self.trans('/project/groups/')
        time.sleep(SET_LONG_WAIT)

        update_xpath = '//tr[td[contains(./text(),"%s")]]' \
            % CRAETE_GROUP_B

        self.click_xpath(update_xpath + '//a[@href="#"]')
        self.click_xpath(update_xpath + '//a[contains(@href,"/update/")]')

        self.fill_field_clear('id_description')
        self.fill_field('id_description', 'test_groupBB')
        self.save_screenshot()

        self.click_css('input[type=submit]')
        self.save_screenshot()

    def delete_group(self):

        self.trans('/project/groups/')
        time.sleep(SET_LONG_WAIT)

        delete_xpath = '//tr[td[contains(./text(),"%s")]]' \
            % CRAETE_GROUP_B

        self.click_xpath(delete_xpath + '//label')

        self.click_and_sleep('groups__action_delete', SET_LONG_WAIT)
        self.save_screenshot()

        self.click_css('a.btn-primary')
        self.save_screenshot()

    # ==================================================

    def add_group_user(self):

        self.trans('/project/groups/')
        time.sleep(SET_LONG_WAIT)

        update_xpath = '//tr[td[contains(./text(),"%s")]]' \
            % CRAETE_GROUP_B

        self.click_xpath(
            update_xpath + '//a[contains(@href,"/manage_members/")]')
        self.save_screenshot()

        self.click_and_sleep('group_members__action_add_user_link',
                             SET_LONG_WAIT)
        self.save_screenshot()

        self.click_xpath(
            '//tr[td[contains(./text(), "%s")]]//label' % CREATE_USER_B)
        self.save_screenshot()

        self.click_and_sleep('group_non_members__action_addMember',
                             SET_LONG_WAIT)
        self.save_screenshot()

    def delete_group_user(self):

        self.trans('/project/groups/')
        time.sleep(SET_LONG_WAIT)

        update_xpath = '//tr[td[contains(./text(),"%s")]]' \
            % CRAETE_GROUP_B

        self.click_xpath(
            update_xpath + '//a[contains(@href,"/manage_members/")]')
        self.save_screenshot()

        self.click_xpath(
            '//tr[td[contains(./text(),"%s")]]//label' % CREATE_USER_B)
        self.click_and_sleep('group_members__action_removeGroupMember',
                             SET_LONG_WAIT)
        self.save_screenshot()

        self.click_css('a.btn-primary')
        self.save_screenshot()
