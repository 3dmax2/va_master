try: 
    from . import base
    from .base import Step, StepResult
except: 
    import base
    from base import Step, StepResult

from tornado.httpclient import AsyncHTTPClient, HTTPRequest
import tornado.gen
import json
import subprocess
import os

#  location: VAR_LOCATION 

PROVIDER_TEMPLATE = '''VAR_PROVIDER_NAME:
  # Set up the Project name and Service Account authorization
  project: "VAR_PROJECT_ID"
  service_account_email_address: "VAR_SERVICE_EMAIL"
  service_account_private_key: "VAR_PRIVATE_KEY"

  # Set up the location of the salt master
  minion:
    master: VAR_THIS_IP

  # Set up grains information, which will be common for all nodes
  # using this provider
  grains:
    node_type: broker
    release: 1.0.1

  metadata: '{"sshKeys": "gceuser:VAR_PUB_KEY"}'
  ssh_username: gceuser
  ssh_keyfile: VAR_SSH_FILE

  driver: gce
  ssh_interface: public_ips

  network: default
'''

PROFILE_TEMPLATE = '''VAR_PROFILE_NAME:
  use_persistent_disk: True
  delete_boot_pd: False
  deploy: True
  make_master: False
  provider: VAR_PROVIDER_NAME

  image: VAR_IMAGE
  size: VAR_SIZE
  minion:
      grains:
          role: VAR_ROLE
'''

class GCEDriver(base.DriverBase):
    def __init__(self, provider_name = 'gce-provider', profile_name = 'gce-profile', host_ip = '192.168.80.39', key_name = 'va_master_key', key_path = '/root/va_master_key', datastore_handler = None):
        """ The standard issue init method. Borrows most of the functionality from the BaseDriver init method, but adds a self.regions attribute, specific for OpenStack hosts. """

        kwargs = {
            'driver_name' : 'gce',
            'provider_template' : PROVIDER_TEMPLATE,
            'profile_template' : PROFILE_TEMPLATE,
            'provider_name' : provider_name,
            'profile_name' : profile_name,
            'host_ip' : host_ip,
            'key_name' : key_name,
            'key_path' : key_path,
            'datastore_handler' : datastore_handler
            }
        self.regions = ['RegionOne', ]
        super(GCEDriver, self).__init__(**kwargs)

    @tornado.gen.coroutine
    def driver_id(self):
        """ Pretty simple. """
        raise tornado.gen.Return('gce')

    @tornado.gen.coroutine
    def friendly_name(self):
        """ Pretty simple """
        raise tornado.gen.Return('Google Cloud Engine')



    @tornado.gen.coroutine
    def get_steps(self):
        """ Adds a provider_ip, tenant and region field to the first step. These are needed in order to get OpenStack values. """

        steps = yield super(GCEDriver, self).get_steps()
        steps[0].add_fields([
            ('project_id', 'Project id', 'str'),
            ('service_email', 'Service email', 'str'),
#            ('location', 'Location', 'str'),
            ('pub_key', 'Enter the public key contents', 'str'),
            ('private_key', 'Enter the private key contents', 'str'),
        ])
        self.steps = steps
        raise tornado.gen.Return(steps)


    @tornado.gen.coroutine
    def get_networks(self):
        networks = ['list', 'of', 'networks']
        raise tornado.gen.Return(networks)

    @tornado.gen.coroutine
    def get_sec_groups(self):
        sec_groups = ['list', 'of', 'groups']
        raise tornado.gen.Return(sec_groups)

#    @tornado.gen.coroutine
#    def get_images(self):
#        images = yield super(GCEDriver, self).get_images()
#        images = [x['name'] for x in images]
#        raise tornado.gen.Return(images)
#
#    @tornado.gen.coroutine
#    def get_sizes(self):
#        sizes =  yield super(GCEDriver, self).get_sized()
#        sizes = [x['name'] for x in sizes['flavors']]
#        raise tornado.gen.Return(sizes)


    @tornado.gen.coroutine
    def get_servers(self, provider):
        """ Gets various information about the servers so it can be returned to provider_data. The format of the data for each server follows the same format as in the base driver description """
        try:
            servers = []
            servers = [
                {
                    'hostname' : x['name'], 
                    'ip' : x['ip_address'],  
                    'size' : x['size'],
                    'used_disk' : x['used_disk'], 
                    'used_ram' : x['used_ram'], 
                    'used_cpu' : x['used_cpu'],
                    'status' : x['status'], 
                    'host' : provider['hostname']
                } for x in servers
            ]
        except Exception as e: 
            print ('Cannot get servers. ')
            import traceback
            print traceback.print_exc()
            raise tornado.gen.Return([])
        raise tornado.gen.Return(servers)



    @tornado.gen.coroutine
    def get_provider_status(self, provider):
        """ Tries to get the token for the provider. If not successful, returns an error message. """
        raise tornado.gen.Return(True)

    @tornado.gen.coroutine
    def get_provider_data(self, provider, get_servers = True, get_billing = True):
        """ Gets various data about the provider and all the servers using the get_openstack_value() method. Returns the data in the same format as defined in the base driver. """
        import time
        print ('Starting timer for OpenStack. ')
        try:
            servers = yield self.get_servers(provider)
            provider_data = {
                'max_cores' : 0, 
                'used_cores' : 0, 
                'max_ram' : 0, 
                'used_ram' : 0, 
                'max_disk' : 0, 
                'used_disk' : 0, 
                'max_servers' : 0, 
                'used_servers' : 0
            }
        except Exception as e: 
            import traceback
            print traceback.print_exc()
            provider_data = {
                'servers' : [],
                'limits' : {},
                'provider_usage' : {},
                'status' : {'success' : False, 'message' : 'Could not connect to the libvirt provider. ' + e.message}
            }
            raise tornado.gen.Return(provider_data)


        servers = yield self.get_servers(provider)

        provider_usage = {
            'max_cpus' : provider_data['maxTotalCores'],
            'used_cpus' : provider_data['totalCoresUsed'], 
            'free_cpus' : provider_data['maxTotalCores'] - provider_data['totalCoresUsed'], 
            'max_ram' : provider_data['maxTotalRAMSize'], 
            'used_ram' : provider_data['totalRAMUsed'],
            'free_ram' : provider_data['maxTotalRAMSize'] - provider_data['totalRAMUsed'], 
            'max_disk' : provider_data['maxTotalVolumeGigabytes'], 
            'used_disk' : provider_data['totalGigabytesUsed'], 
            'free_disk' : provider_data['maxTotalVolumeGigabytes'] - provider_data['maxTotalVolumeGigabytes'],
            'max_servers' : provider_data['maxTotalInstances'], 
            'used_servers' : provider_data['totalInstancesUsed'], 
            'free_servers' : provider_data['maxTotalInstances'] - provider_data['totalInstancesUsed']
        }

        provider_data = {
            'servers' : servers, 
            'provider_usage' : provider_usage,
            'status' : True,
        }
        raise tornado.gen.Return(provider_data)


    @tornado.gen.coroutine
    def server_action(self, provider, server_name, action):
        """ Performs server actions using a nova client. """
        try:
            nova = client.Client('2.0', provider['username'], provider['password'], provider['tenant'], 'http://' + provider['provider_ip'] + '/v2.0')
            server = [x for x in nova.servers.list() if x.name == server_name][0]
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise tornado.gen.Return({'success' : False, 'message' : 'Could not get server. ' + e.message})
        try:
            success = getattr(server, action)()
            print ('Made action : ', success)
        except Exception as e:
            raise tornado.gen.Return({'success' : False, 'message' : 'Action was not performed. ' + e.message, 'data' : {}})

        raise tornado.gen.Return({'success' : True, 'message' : ''})


    @tornado.gen.coroutine
    def validate_field_values(self, step_index, field_values):
        """ Uses the base driver method, but adds the region tenant and identity_url variables, used in the configurations. """
        if step_index == 0:
            for key in ['project_id', 'service_email', 'pub_key']: 
                provider_key = 'VAR_' + key.upper()
                print 'Setting provider vars : ', provider_key, field_values[key]

                self.provider_vars[provider_key] = field_values[key]

            private_key_contents = field_values['private_key']
            private_key_path = '/root/' + field_values['project_id'] + '.json' 

            with open(private_key_path, 'w') as f: 
                f.write(private_key_contents)

            self.provider_vars['VAR_PRIVATE_KEY'] = private_key_path
#        elif step_index == 1:

        try:
            step_kwargs = yield super(GCEDriver, self).validate_field_values(step_index, field_values)
        except:
            import traceback
            traceback.print_exc()
        raise tornado.gen.Return(step_kwargs)


    @tornado.gen.coroutine
    def create_server(self, provider, data):
        """ Works properly with the base driver method, but overwritten for bug tracking. """
        try:
#            nova = client.Client('2', provider['username'], provider['password'], provider['tenant'], 'http://' + provider['provider_ip'] + '/v2.0')
#            full_key_path = provider['salt_key_path'] + ('/' * provider['salt_key_path'][-1] != '/') + provider['salt_key_name'] + '.pub'
#            f = ''
#            with open(self.key_path + '.pub') as f: 
#                key = f.read()
#            keypair = nova.keypairs.create(name = self.key_name, public_key = key)
#            print ('Creating server!')
            yield super(GCEDriver, self).create_minion(provider, data)
        except:
            import traceback
            traceback.print_exc()
