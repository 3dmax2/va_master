import time, sys
from va_api import APIManager
import warnings
from va_integration_base import VATestBase

class VAServicesTests(VATestBase):

    def __init__(self, *args, **kwargs):
        super(VAServicesTests, self).__init__(*args, **kwargs)

        self.test_functions = [
            (self.test_services, {}),
            (self.test_presets, {}),
        ]

    def test_services(self):
        services = self.api.api_call('/services', method='get', data={})
        self.assert_success(services)
    
    def test_presets(self):
        presets = self.api.api_call('/services/get_service_presets')
        self.assert_success(presets)
        new_service = {'presets' : ['ping_preset'], 'server' : 'va-master-ci', 'name' : 'test_service', 'address' : '127.0.0.1', 'port' : '443', 'tags' : 'web'}

        result = self.api.api_call('/services/add_service_with_presets', data = new_service, method = 'post')
        print ('Result is : ', result)
        self.assert_success(result)

        all_checks = self.api.api_call('/services/get_services_with_checks')
        self.assert_success(all_checks)

        services = all_checks['data'].keys()
        assert (new_service['name'] in services), 'Service %s not found in %s. ' % (new_service['name'], services)

        result = self.api.api_call('/services/delete', data = {'name' : new_service['name']}, method = 'delete')
        self.assert_success(result)

        all_checks = self.api.api_call('/services/get_services_with_checks')
        self.assert_success(all_checks)
#        self.assert_all_checks(all_checks)

        services = all_checks['data'].keys()
        assert (new_service['name'] not in services), 'Service %s was still in list %s even after being deleted. '


        result = self.api.api_call('/services/delete_service', method = 'delete', data = {"service_name" : new_service['name']})

