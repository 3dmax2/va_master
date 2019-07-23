try: 
    from . import base
    from .base import Step, StepResult
except: 
    import base
    from base import Step, StepResult

from va_master.api import apps
from tornado.httpclient import AsyncHTTPClient, HTTPRequest
import tornado.gen
import json
import subprocess
import os
from paramiko import SSHClient, AutoAddPolicy

from va_master.handlers.ssh_handler import handle_ssh_action
from va_master.utils.paramiko_utils import ssh_call


PROVIDER_TEMPLATE = ""
PROFILE_TEMPLATE = ""

def check_ping(address):
    response = os.system("ping -c 1 " + address + " > /dev/null")
    if response == 0:
        pingstatus = "ACTIVE"
    else:
        pingstatus = "SHUTOFF"
    return pingstatus

class GenericDriver(base.DriverBase):
    def __init__(self, provider_name = 'generic_provider', profile_name = 'generic_profile', host_ip = '192.168.80.39', key_name = 'va_master_key', key_path = '/root/va_master_key', datastore_handler = None, driver_name = 'generic_driver', flavours = []):
        kwargs = {
            'driver_name' : driver_name, 
            'provider_template' : PROVIDER_TEMPLATE, 
            'profile_template' : PROFILE_TEMPLATE, 
            'provider_name' : provider_name, 
            'profile_name' : profile_name, 
            'host_ip' : host_ip,
            'key_name' : key_name, 
            'key_path' : key_path, 
            'datastore_handler' : datastore_handler
            }
        self.sizes = flavours
        super(GenericDriver, self).__init__(**kwargs) 


    def get_cl(self, data):
        cl = SSHClient()
        cl.load_system_host_keys()
        cl.set_missing_host_key_policy(AutoAddPolicy())
        connect_kwargs = {
            'username' : data.get('username', ''), 
        }
        if data.get('port'): 
            connect_kwargs['port'] = int(data.get('port'))

        if data.get('password'): 
            connect_kwargs['password'] = data['password']
        else: 
            connect_kwargs['key_filename'] = self.key_path + '.pem'


        try:
            print ('Kwargs : ', connect_kwargs)
            cl.connect(data.get('ip'), **connect_kwargs)
        except Exception as e: 
            print ('Failed to connect with ssh to ', data.get('ip'))
            import traceback
            traceback.print_exc()
            raise Exception('Failed to connect with ssh: ' + e.message)

        self.cl = cl
        return cl

    @tornado.gen.coroutine
    def driver_id(self):
        """ Pretty simple. """
        raise tornado.gen.Return('generic_driver')

    @tornado.gen.coroutine
    def friendly_name(self):
        raise tornado.gen.Return('Generic provider')

      
    @tornado.gen.coroutine
    def get_provider_status(self, provider = ''): 
        raise tornado.gen.Return({'success' : True, 'message': ''})

    @tornado.gen.coroutine
    def get_steps(self):
        steps = yield super(GenericDriver, self).get_steps()
        steps[0].add_fields([('ip_address', 'IP address', 'str')])
        steps = [steps[0]]
        self.steps = steps
        raise tornado.gen.Return(steps)


    @tornado.gen.coroutine
    def get_networks(self):
        networks = [] 
        raise tornado.gen.Return(networks)

    @tornado.gen.coroutine
    def get_sec_groups(self):
        
       	sec_groups =[] 
    	raise tornado.gen.Return(sec_groups)

    @tornado.gen.coroutine
    def get_images(self):
        
        images = []
        raise tornado.gen.Return(images)

    @tornado.gen.coroutine
    def get_sizes(self):
        
        sizes = []
        raise tornado.gen.Return(sizes)

    @tornado.gen.coroutine
    def remove_server(self, provider, server_name):
        provider_datastore = yield self.datastore_handler.get_provider(provider['provider_name'])
        servers = provider_datastore.get('servers')

        servers = [x for x in servers if x['hostname'] != server_name]
        provider_datastore['servers'] = servers
        yield self.datastore_handler.edit_provider(provider_datastore)

    @tornado.gen.coroutine
    def reboot_server(self, provider, server):
        cl = self.get_cl(server)
        ssh_call(cl, 'reboot')
        raise tornado.gen.Return(True)

    @tornado.gen.coroutine
    def stop_server(self, provider, server):
        cl = self.get_cl(server)
        ssh_call(cl, 'poweroff')
        raise tornado.gen.Return(True)
 
    @tornado.gen.coroutine
    def server_action(self, provider, server_name, action):

        server = yield self.datastore_handler.get_object(object_type = 'server', server_name = server_name)
        ssh_kwargs = {'server_name' : server_name, 'datastore_handler' :  self.datastore_handler}


        result = yield handle_ssh_action(datastore_handler = self.datastore_handler, action = action, ip_addr = server['ip_address'], port = server.get('port'), username = server.get('username'), password = server.get('password'), kwargs = ssh_kwargs)
        raise tornado.gen.Return(result)


    @tornado.gen.coroutine
    def get_servers(self, provider):
        servers = yield self.datastore_handler.get_provider(provider['provider_name'])
        servers = servers['servers']
        result = []
        if provider['provider_name'] == 'va_standalone_servers' : 
            provider['provider_name'] = ''

        for server in servers: 
            db_server = yield self.datastore_handler.get_object(object_type = 'server', server_name = server['hostname'])
            server_template = {
                'hostname' : server['hostname'], 
                'ip' : server['ip_address'],
                'size' : '',
                'used_disk' : 0, 
                'used_ram' : 0, 
                'used_cpu' : 0,
                'status' : check_ping(server['ip_address']), 
                'cost' : 0,  #TODO find way to calculate costs
                'estimated_cost' : 0,
                'managed_by' : [],
                'provider' : provider['provider_name'], 
            }
            server_template.update(server)
            server_template.update(db_server)
            result.append(server_template)

        raise tornado.gen.Return(result)
        

    @tornado.gen.coroutine
    def get_provider_billing(self, provider):
        raise tornado.gen.Return(None)


    @tornado.gen.coroutine
    def get_provider_data(self, provider, get_servers = True, get_billing = True):
        
        try: 
            data = {
                'servers' : [], 
                'limits' : {
                    'absolute' : [
                    ]
                }
            }
            #Functions that connect to provider here. 
        except Exception as e: 
            provider_data = {
                'servers' : [], 
                'limits' : {},
                'provider_usage' : {},
                'status' : {'success' : False, 'message' : 'Could not connect to the libvirt provider. ' + e}
            }
            raise tornado.gen.Return(provider_data)
           
        provider_usage = {
            'total_disk_usage_gb' : None, 
            'current_disk_usage_mb' : None, 
            'cpus_usage' :None, 
        }

        servers = yield self.get_servers(provider)

        provider_usage = {
            'max_cpus' : 0,
            'used_cpus' : 0, # TODO calculate cpus from servers
            'free_cpus' : 0,
            'max_ram' : 0,
            'used_ram' : 0, # TODO calculate ram from servers
            'free_ram' : 0,
            'max_disk' : 0,
            'used_disk' : 0, # TODO calculate disk from servers
            'free_disk' : 0,
            'max_servers' : 0,
            'used_servers' : len(servers),
            'free_servers' : 0
        }

        provider_data = {
            'servers' : servers,
            'provider_usage' : provider_usage,
            'status' : {'success' : True, 'message': ''}
        }

        raise tornado.gen.Return(provider_data)



    @tornado.gen.coroutine
    def validate_field_values(self, step_index, field_values):
        step_result = yield super(GenericDriver, self).validate_field_values(step_index, field_values)

        if step_index == 0: 
            self.field_values.update({
                'provider_name' : field_values['provider_name'], 
                'username' : field_values['username'], 
                'password' : field_values['password'],
                'ip_address' : field_values['ip_address'],
                'images' : [], 
                'sizes' : self.sizes, 
            })
            raise tornado.gen.Return(StepResult(
                errors = [], new_step_index = -1, option_choices = {}
            ))
        raise tornado.gen.Return(step_result)
       
     
    @tornado.gen.coroutine
    def validate_app_fields(self, step, **fields):
        steps_fields = [['role', 'server_name'], [], ['username', 'ip', 'port', 'location']]
        result = yield super(GenericDriver, self).validate_app_fields(step, steps_fields = steps_fields, **fields)
        raise tornado.gen.Return(result)

    @tornado.gen.coroutine
    def create_server(self, provider, data):
        cl = self.get_cl(data)
        try:

            server = {"username" : data['username'], "server_name" : data["server_name"], "hostname" : data["server_name"], "ip_address" : data["ip"], "local_gb" : 0, "memory_mb" : 0, "managed_by" : ['ssh'], "location" : data.get('location', '')}
            print ('Server is : ', server)
            yield apps.add_server_to_datastore(self.datastore_handler, server_name = server['server_name'], ip_address = data['ip'], hostname = server['hostname'], manage_type = 'ssh', username = data['username'], kwargs = {'password' : data.get('password', ''), 'location' : data.get('location', '')})
            print ('Added server to datastore')
            db_server = yield self.datastore_handler.get_object('server', server_name = server['server_name'])
            print ('Db server is : ', db_server)

            if provider['provider_name'] != 'va_standalone_servers' : 
                print ('Provider name is : ', provider['provider_name'])
                yield apps.manage_server_type(self.datastore_handler, server_name = server['server_name'], new_type = 'provider', driver_name = 'generic_driver')
                server['managed_by'].append('provider')

            yield self.datastore_handler.add_generic_server(provider, server)
            print ('Added generic server ', server)
        except: 
            import traceback
            traceback.print_exc()

        raise tornado.gen.Return(True)  

