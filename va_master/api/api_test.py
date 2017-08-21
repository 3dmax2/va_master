import unittest, simplejson
from url_handler import gather_paths

class TestAPIMethods():

    def __init__(self, token, base_url, paths = None):
        self.base_url = base_url
        self.paths = gather_paths()
        self.token = token

    def generate_api_endpoints(self):
        print self.paths
        serialized_paths = {m : {f : {'args' : self.paths[m][f]['args'] for x in  self.paths[m][f]} for f in self.paths[m]} for m in self.paths}
        with open('api_endpoints.json', 'w') as f: 
            f.write(simplejson.dumps(serialized_paths, indent = 4))

    def set_paths(self, paths): 
        print 'Setting paths to : ', paths
        self.paths = paths

    def test_api_endpoints(self):
        for method in ['get', 'post']: 
            functions = self.paths[method]
            for f in functions: 
                exec_f = raw_input('Execute ' + f + ' ? y/n\n')
                if exec_f != 'y': continue
                f_args = functions[f]['args']
                f_name = f 
                entered_args = []
                if f_args != []: 
                    entered_args = []
                    for arg in f_args: 
                        new_arg = raw_input('Enter value for : ' + arg + '.\n')
                        entered_args.append(new_arg)
                print 'Want to call : ', f_name, ' with args : ', entered_args
        self.assertTrue(True)


#class TestAPIMethods(unittest.TestCase):
#
#    def setUp(self, handler, token, base_url):
#        self.base_url = base_url
#        self.paths = gather_paths()
#        self.token = token
#        self.handler = handler
#
#    def test_non_args(self):
#        for method in ['get', 'post']: 
#            functions = self.handler.paths[method]
#            for f in functions: 
#                f_args = ['test_' + x for x in f['args']]
#                print 'Want to call : ', f['function'], ' with args : ', f_args
#        self.assertTrue(True)
#
#    def test_isupper(self):
#        self.assertTrue('FOO'.isupper())
#        self.assertFalse('Foo'.isupper())
#
#    def test_split(self):
#        s = 'hello world'
#        self.assertEqual(s.split(), ['hello', 'world'])
#        # check that s.split fails when the separator is not a string
#        with self.assertRaises(TypeError):
#            s.split(2)
#
#

