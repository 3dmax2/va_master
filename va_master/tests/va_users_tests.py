import time, sys
from va_api import APIManager
import warnings
from va_integration_base import VATestBase

class VAUsersTests(VATestBase):

    def __init__(self, *args, **kwargs):
        super(VAUsersTests, self).__init__(*args, **kwargs)

        self.test_functions = [
            (self.get_users, {}) ,
            (self.test_users, {}), 
            (self.test_add_user, {}), 
        ]


    def get_users(self):
        users = self.api.api_call('/panels/users', method = 'get', data = {})
        self.assert_success(users)

        return users['data']

    def check_if_user_exists(self, user):
        users = self.get_users()
        user = user['user']
        users = [x['user'] for x in users]
        assert (user in users), "User %s not found in list of users: %s. " % (user, users)

    def test_users(self):
        users = self.get_users()
        required_keys = ['user', 'functions', 'groups']
        self.test_keys_in_set(users, required_keys, data_id_key = 'user')

    def add_group(self, group):
        new_group = self.api.api_call('/panels/create_user_group', method = 'post', data = {'group_name' : group['name'], 'functions' : group['functions']})
        self.assert_success(new_group)

    def add_user(self, user)       :
        new_user_api = self.api.api_call('/panels/create_user_with_group', method = 'post', data = user)
        self.assert_success(new_user_api)

    def _test_user_endpoint(self, function, token = '', method = 'get', data = {}, success = True):
        result = self.api.api_call(function, method = method, data = data, token = token)
        assert (result['success'] == success), "Success was wrong - expected %s but is %s. " % (str(success), str(result['success']))

    def test_add_user(self):
        user_functions = ['apps/action', 'panels', 'apps/get_panel']
        group = {'name' : 'providers', 'functions' : [{'func_path' : 'providers'}]}
        new_user = {'user' : 'auto_testing_user', 'password' : 'test_password', 'user_type' : 'user', 'functions' : user_functions, 'groups' : [group['name']]}

        self.add_group(group)
        self.add_user(new_user)
        self.check_if_user_exists(new_user)

        login = self.api.api_call('/login', method = 'post', data = {'username' : new_user['user'], 'password' : new_user['password']})
        self.assert_success(login)
        token = login['data']['token']

        panels = self._test_user_endpoint('/panels', method = 'get', token = token)
        providers = self._test_user_endpoint('/providers', method = 'post', token = token)
        #This should fail because the user does not have access to this function. 
        providers_info = self._test_user_endpoint('/providers/info', method = 'post', token = token, success = False)

        delete = self.api.api_call('/panels/delete_user', method = 'post', data = {'user' : new_user['user']})
        self.assert_success(delete)

        delete_group = self.api.api_call('/panels/delete_group', method = 'post', data = {'group_name' : group['name']})
        self.assert_success(delete_group)

