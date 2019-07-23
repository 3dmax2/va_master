import time, logging, sys
from va_api import APIManager

import warnings

#We use coloredlogs for limited prettier output. It may not be available for all terminals. 
try:
    import coloredlogs
except ImportError:
    coloredlogs = None


class VATestBase(object):

    def __init__(self, va_url = 'https://127.0.0.1:443', va_user = 'admin', va_pass = 'admin', token = '', verbosity = 'DEBUG'):
        if token: 
            self.api = APIManager(va_url = va_url, token = token, verify = False)
        else: 
            self.api = APIManager(va_url = va_url, va_user=va_user, va_pass=va_pass, verify=False)

        # self.test_functions is a list of tuples, where each tuple is a function-kwargs pair. 
        self.test_functions = []

        # This is where the results of the functions is stored. 
        self.function_results = []

        self.assert_errors = []

        self.logger = logging.getLogger('va_master.integration_tests')
        logger_level = getattr(logging, verbosity)
        self.logger.setLevel(logger_level)

        if not self.logger.handlers: 
            ch = logging.StreamHandler()
            ch.setFormatter(logging.Formatter('[%(asctime)-15s] %(message)s'))
            ch.setLevel(logger_level)
            self.logger.addHandler(ch)

            if coloredlogs:
                coloredlogs.install(logger = self.logger)

    def assert_success(self, result):
        assert type(result) == dict, "Result returned was not a dictionary: %s" % (str(result))
        assert(result['success']), "Result was unsuccessful - %s" % (str(result))


    def do_tests(self):
        self.logger.info('Doing tests for %s. ' % (type(self).__name__))
        for func in self.test_functions:
            self.logger.debug('Testing %s. ' % func[0].func_name)
            try:
                output = func[0](**func[1])
                if output:
                    self.logger.warning('Function %s has output: %s. ' % (func[0].func_name, output))
                success = True
                self.logger.debug('Function %s is successful. ' % func[0].func_name)
            except AssertionError as e:
                output = 'Assertion error at %s: %s' % (func[0].func_name, e.message)
                success = False
                self.assert_errors.append((func[0].func_name, output))
                self.logger.error('Function %s has an assertion error: %s. ' % (func[0].func_name, output))

            self.function_results.append((func[0].func_name, success))

        self.output_results()

    def output_results(self):
        if self.assert_errors: 
            self.logger.error('Some functions reported errors. ')
            for error in self.assert_errors: 
                pass
                self.logger.error('Function %s failed with: %s' % (error[0], error[1]))
        for result in self.function_results: 
            self.logger.debug('Function %s had output %s. ' % (result[0], result[1]))
#        print self.function_results #TODO print prettier

    def test_keys_in_set(self, data, required_keys, warning_keys = {}, data_id_key = ''):
        for d in data: 
            assert set(d.keys()).issuperset(required_keys), "Failed key test for " + d.get(data_id_key, str(d)) + " : " + str(d.keys()) + " don't contain " + str(required_keys)
#            if not set(d.keys()).issuperset(warning_keys):
#                warning_str = "Expected to see " + str(warning_keys) + " in " + d.get(data_id_key, str(d)) + " but didn't. "
#                self.warnings.append(warning_str)


