try: 
    from . import base
    from .base import Step, StepResult
except: 
    import base
    from base import Step, StepResult
import operator

import sys
from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from tornado.concurrent import run_on_executor
from concurrent.futures import ThreadPoolExecutor   # `pip install futures` for python2

import tornado.gen
import tornado.ioloop
import json
import subprocess

import salt.client
import clc

PROVIDER_TEMPLATE = "" 
PROFILE_TEMPLATE = "" 

class CenturyLinkDriver(base.DriverBase):
    executor = ThreadPoolExecutor(max_workers=4)
    def __init__(self, flavours, provider_name = 'century_link_provider', profile_name = 'century_link__profile', host_ip = '192.168.80.39', key_name = 'va_master_key', key_path = '/root/va_master/va_master_key/', datastore_handler = None):
        """
            Works ok atm but needs more stuff in the future. Namely, we need the following: 
                - A way to get usage statistics. No option for this yet in the python API, so I may need to check out the REST API. 
                - Creating hosts. Driver is in the beginning stage atm, so this is for a later stage. 

            The arguments are fairly generic. Some of the more important ones are: 
            Arguments:  
                flavours -- Information about storage, CPU and other hardware for the provider. We're using these to stay close to the OpenStack model. 
                salt_master_fqdn -- May be used for the config_drive if we need to generate it. Keeping it in just in case, but not used atm. 

            The locations parameter is hardcoded atm, may need to get locations in a different manner. 
        """

        self.flavours = flavours
        self.locations = [u'PrimaryDatacenter', u'au1', u'ca1', u'ca2', u'ca3', u'de1', u'gb1', u'gb3', u'il1', u'ny1', u'sg1', u'uc1', u'ut1', u'va1', u'va2', u'wa1']        

        kwargs = {
            'driver_name' : 'century_link_driver', 
            'provider_template' : PROVIDER_TEMPLATE, 
            'profile_template' : PROFILE_TEMPLATE, 
            'provider_name' : provider_name, 
            'profile_name' : profile_name, 
            'host_ip' : host_ip, 
            'key_name' : key_name, 
            'key_path' : key_path, 
            'datastore_handler' : datastore_handler
            }
        super(CenturyLinkDriver, self).__init__(**kwargs) 

    def set_credentials(self, provider):
        clc.v2.SetCredentials(provider['username'], provider['password'])
        self.account = clc.v2.Account()


    def get_datacenter(self, provider): 
        self.set_credentials(provider)
        self.datacenter = [x for x in clc.v2.Datacenter.Datacenters() if provider['location'] in x.location][0]
        return self.datacenter

    def get_servers_api(self, provider):
        servers = self.datacenter.Groups().Get(provider['defaults']['sec_group']).Servers()
        return servers

    def get_servers_list(self, provider):
        servers_list = self.get_servers_api(provider).Servers()
        return servers_list      

    @tornado.gen.coroutine
    def driver_id(self):
        """ Pretty simple. """
        raise tornado.gen.Return('century_link_driver')

    @tornado.gen.coroutine
    def friendly_name(self):
        """ Pretty simple. """
        raise tornado.gen.Return('Century Link')


    @tornado.gen.coroutine
    def wait_for_clc_action(self, success):
        print ('Initial success is : ', success)
        status_url = [x for x in success['links'] if x.get('rel') == 'status'][0]['href']
        status = 'unknown'
        while status not in ['failed', 'underConstruction']:
            print ('Status is : ', status)
            result = clc.v2.API.Call('get', status_url)
            status = result['status']
            if status == 'succeeded': raise tornado.gen.Return(result)
            yield tornado.gen.sleep(5)

        raise tornado.gen.Return(False)
    

    @tornado.gen.coroutine
    def server_action(self, provider, server_name, action):
        server_name = server_name.upper()
        clc.v2.SetCredentials(provider['username'], provider['password'])
        self.account = clc.v2.Account()
        self.get_datacenter(provider)

        servers_list = self.get_servers_list_api(provider)
        server = [x for x in servers_list if server_name in x.id] or [None]
        server = server[0]
        if not server: 
            print ('Did not find server with name: ', server_name)
            raise tornado.gen.Return({'success' : False, 'message' : 'Did not find server with name: ' + server_name})

        #post_arg is simply to cut down on code; it creates a tuple of arguments ready to be sent to the API. 
        #It basically creates tuples that look like this: ('post', 'ctl/api/url', '["server_id"]')
        post_arg = lambda action: ('post', 'operations/%s/servers/%s' % (self.account.alias, action), '["%s"]'% server.id)

        action_map = {
            'delete'  : ('delete', 'servers/%s/%s' % (self.account.alias, server.id), {}),
            'reboot'  : post_arg('reboot'),
            'start'   : post_arg('powerOn'),
            'stop'    : post_arg('powerOff'),
            'suspend' : post_arg('pause'),
#            'resume'  : None,
        }

        if action not in action_map: 
            raise tornado.gen.Return({'success' : False, 'message' : 'Action not supported : ' + action})
        success = clc.v2.API.Call(*action_map[action], debug = True)[0]
        yield self.wait_for_clc_action(success)

        raise tornado.gen.Return({'success' : True, 'message' : ''})

    @tornado.gen.coroutine
    def get_provider_billing_data(self, provider):
        self.get_datacenter(provider)
        group = self.datacenter.Groups().Get(provider['defaults']['sec_group'])
        group_links = group.data['links']

        billing_link = [x for x in group_links if 'billing' in x['rel']][0]['href']
        billing_info = clc.v2.API.Call('get', billing_link)
        billing_info = billing_info['groups'][group.id]['servers']

        billing_info = [{'hostname' : x.upper(), 'estimated_cost' : billing_info[x]['monthlyEstimate'], 'cost' : billing_info[x]['monthToDate'], 'current_hour' : billing_info[x]['currentHour']} for x in billing_info]

        raise tornado.gen.Return(billing_info)

    @tornado.gen.coroutine
    def get_provider_billing(self, provider): 
        servers = yield self.get_servers(provider)
        print ('Servers are : ', servers)
        raise tornado.gen.Return(None)


    @tornado.gen.coroutine
    def get_servers(self, provider, get_billing = True):
        """ Gets servers from the group selected when adding the provider. """
        try: 
            datacenter = self.datacenter
        except:
            self.account = clc.v2.Account()
            datacenter = self.get_datacenter(provider)

        servers = self.get_servers_list(provider)
        servers = [x.data for x in servers if 'details' in x.data.keys()]
        print ('Servers are : ', servers)
        servers =  [{
                'hostname' : x['name'],
                'ip' : None if not x['details']['ipAddresses'] else x['details']['ipAddresses'][0]['internal'],
                'size' : 'va-small',
                'status' : x['status'],
                'provider' : provider['provider_name'],
                'used_ram' : x['details']['memoryGB'],
                'used_cpu': x['details']['cpu'],
                'used_disk' : x['details']['storageGB'],

        } for x in servers]

        raise tornado.gen.Return(servers)


    @tornado.gen.coroutine
    def get_provider_data(self, provider, get_servers = True, get_billing = True):
        """ Gets servers properly, but doesn't yet get provider_usage. """
        import time
        print ('Century link timer started. ')
        t0 = time.time()
        try:
            clc.v2.SetCredentials(provider['username'], provider['password'])
            self.get_datacenter(provider)
            group = self.datacenter.Groups().Get(provider['defaults']['sec_group'])

            group_stats_link = [x for x in group.data['links'] if x['rel'] == 'statistics'][0]
            group_stats = clc.v2.API.Call('get', group_stats_link['href'] + '?type=latest')
            #TODO do stuff with group_stats

            self.account = clc.v2.Account()
            if get_servers: 
                servers = yield self.get_servers(provider, get_billing)
                if get_billing: 
                    servers_billing = yield self.get_provider_billing_data(provider)
                    for x in servers: 
                        server_billing = [i for i in servers_billing if x['hostname'] == i['hostname']] or [{}]
                        server_billing = server_billing[0]

                        x.update(server_billing)
            else: 
                servers = []

            provider_data = {
                'servers' : servers, 
                'provider_usage' : {
                    'max_cpus' : 'n/a',
                    'used_cpus' : sum([x['used_cpu'] for x in servers]),
                    'free_cpus' : 'n/a',
                    'max_ram' : 'n/a',
                    'used_ram' : sum([x['used_ram'] for x in servers]),
                    'free_ram' : 'n/a',
                    'max_disk' : 'n/a',
                    'used_disk' : sum([x['used_disk'] for x in servers]),
                    'free_disk' : 'n/a',
                    'max_servers' : 'n/a',
                    'used_servers' :  group.data['serversCount'],
                    'free_servers' :'n/a' 
                },
            }
            #Functions that connect to provider here. 
        except Exception as e: 
            import traceback
            traceback.print_exc()
            provider_data = {
                'servers' : [], 
                'provider_usage' : {},
                'status' : {'success' : False, 'message' : 'Could not connect to the libvirt provider. ' + e.message}
            }
            raise tornado.gen.Return(provider_data)
        print ('Century link took ', time.time() - t0)
        raise tornado.gen.Return(provider_data)

    @tornado.gen.coroutine
    def get_provider_status(self, provider):
        """ Works properly it seems. """
        try: 
            clc.v2.SetCredentials(provider['username'], provider['password'])
            self.account = clc.v2.Account()
        except: 
            raise tornado.gen.Return({'success' : False, 'message' : 'Could not connect to provider: ' + e.message})
        raise tornado.gen.Return({'success' : True, 'message': ''})

    @tornado.gen.coroutine
    def server_action(self, provider, server_id, action, kwargs):
        self.get_datacenter(provider)
        servers = self.get_servers_list(provider)
        server = [x for x in servers if x.id == server_id] or [None]
        server = server[0]

        try: 
            getattr(server, action)(**kwargs)
            result = ''
        except Exception as e: 
            result = e.message
        raise tornado.gen.Return({'success' : not result, 'message' : result, 'data' : {}})
        
    @tornado.gen.coroutine
    def api_call(self, provider, data):
        self.get_datacenter(provider)

        method = data['method']
        url = data['url']
        kwargs = data.get('kwargs', {})

        print ('Calling api with : ', method, url, kwargs)
        result = clc.v2.API.Call(method, url, kwargs)
#        print ('Driver api returned : ', result)
        raise tornado.gen.Return(result)

    @tornado.gen.coroutine
    def get_driver_trigger_functions(self):
        conditions = ['domain_full', 'server_can_add_memory', 'server_can_add_cpu']
        actions = ['server_new_terminal', 'server_cpu_full', 'server_memory_full', 'server_set_status', 'server_cpu_critical', 'server_cpu_warning', 'server_cpu_ok', 'server_memory_ok', 'server_memory_warning', 'server_memory_critical', 'server_cpu_full_ok', 'server_memory_full_ok']
        return {'conditions' : conditions, 'actions' : actions}

    @tornado.gen.coroutine
    def domain_full(self, domain, provider = '', server_name = ''):
        cl = salt.client.LocalClient()
        result = cl.cmd('evo-master', 'evo_utils.domain_full', [domain])
        raise tornado.gen.Return(result['evo-master'])

    @tornado.gen.coroutine
    def server_full_cmp(self, server_name, acceptable_values, domain = '', provider = ''):
        cl = salt.client.LocalClient()
        ts_name = server_name.upper()[7:13]
        result = cl.cmd('evo-master', 'evo_utils.server_full_cmp', [ts_name, acceptable_values])
        raise tornado.gen.Return(result['evo-master'])

    @tornado.gen.coroutine
    def server_can_add_memory(self, server_name, domain = '', provider = ''):
        result = yield self.server_full_cmp(server_name, [0,2], domain, provider)
        raise tornado.gen.Return(result)

    @tornado.gen.coroutine
    def server_can_add_cpu(self, server_name, domain = '', provider = ''):
        result = yield self.server_full_cmp(server_name, [0, 1], domain, provider)
        raise tornado.gen.Return(result)

    @tornado.gen.coroutine
    def server_cpu_full(self, server_name, domain = '', provider = ''):
        cl = salt.client.LocalClient()
        ts_name = server_name.upper()[7:13]
        result = cl.cmd('evo-master', 'evo_utils.server_cpu_full', [ts_name])
        raise tornado.gen.Return(result)

    @tornado.gen.coroutine
    def server_cpu_full_ok(self, server_name, domain = '', provider = ''):
        cl = salt.client.LocalClient()
        ts_name = server_name.upper()[7:13]
        result = cl.cmd('evo-master', 'evo_utils.server_cpu_ok', [ts_name])
        raise tornado.gen.Return(result)

    @tornado.gen.coroutine
    def server_memory_full(self, server_name, domain = '', provider = ''):
        cl = salt.client.LocalClient()
        ts_name = server_name.upper()[7:13]
        result = cl.cmd('evo-master', 'evo_utils.server_memory_full', [ts_name])
        raise tornado.gen.Return(result)

    @tornado.gen.coroutine
    def server_memory_full_ok(self, server_name, domain = '', provider = ''):
        cl = salt.client.LocalClient()
        ts_name = server_name.upper()[7:13]
        result = cl.cmd('evo-master', 'evo_utils.server_memory_ok', [ts_name])
        raise tornado.gen.Return(result)

    @tornado.gen.coroutine
    def server_check_hardware(self, provider, server_name, domain = '' , cpu = 0, cpu_operator = '', memory = 0, memory_operator = ''):
        server_name = server_name.upper()
        self.get_datacenter(provider)

        servers = self.get_servers_list(provider)
        server = [x for x in servers if server_name in x.id] or [None]
        server = server[0]

        if cpu_operator: 
            cpu_result = getattr(operator, cpu_operator)(server.cpu, cpu)
            print ('Compared ', server.cpu, cpu_operator, cpu,' got result ', cpu_result)
        else: cpu_result = True
        if memory_operator: 
            memory_result = getattr(operator, memory_operator)(server.memory, memory)
            print ('Compared ', server.memory, memory_operator, memory, ' and got result ', memory_result)
        else: memory_result = True

        end_result = cpu_result and memory_result
        print ('End result is : ', end_result)
        return end_result 

    @tornado.gen.coroutine
    def server_set_status(self, server_name, status, domain = 0, provider = ''):
        cl = salt.client.LocalClient()
        ts_name = server_name.upper()[7:13]
        print ('Setting status for : ', ts_name, ' to ', status)
        result = cl.cmd('evo-master', 'evo_utils.server_set_status', [ts_name, status])

    @tornado.gen.coroutine
    def server_new_terminal(self, provider, server_name, domain):
        print ('Starting new terminal for domain : ', domain)
        sys.path.append('/srv/salt/_modules')
        print ('Appended path ! now is : ', sys.path)
        import evo_manager
#        cl = salt.client.LocalClient(io_loop = tornado.ioloop.current())        
#        job_id = cl.cmd_async('evo_manager.add_terminal', [domain])
        data = evo_manager.new_terminal_data(domain)[3]
        new_minion = yield self.create_minion(provider, data) 
        result = evo_manager.add_terminal(domain, new_minion)
        print ('Result is : ', result)
#        print ('Job id is : ', job_id)
        raise tornado.gen.Return(True)

    @tornado.gen.coroutine
    def server_add_hardware(self, provider, server_name, cpu = 0, memory = 0, domain = ''):
        yield self.server_set_hardware(provider, server_name, cpu = cpu, memory = memory, add = True)

    @tornado.gen.coroutine
    def server_add_cpu(self, provider, server_name, domain = ''): 
        yield self.server_add_hardware(provider, server_name, cpu = 1, memory = 0, domain = domain)

    @tornado.gen.coroutine
    def server_add_memory(self, provider, server_name, domain = ''): 
        yield self.server_add_hardware(provider, server_name, cpu = 0, memory = 1, domain = domain)

    @tornado.gen.coroutine
    def server_memory_status(self, server_name, status, domain = '', provider = ''): 
        cl = salt.client.LocalClient()
        ts_name = server_name.upper()[7:13]
        cl.cmd('evo-master', 'evo_utils.terminal_memory_status', [ts_name, status])

    @tornado.gen.coroutine
    def server_memory_ok(self, server_name, domain = '', provider = ''):
        yield self.server_memory_status(server_name, 'OK', domain, provider)

    @tornado.gen.coroutine
    def server_memory_warning(self, server_name, domain = '', provider = ''):
        yield self.server_memory_status(server_name, 'WARNING', domain, provider)

    @tornado.gen.coroutine
    def server_memory_critical(self, server_name, domain = '', provider = ''):
        yield self.server_memory_status(server_name, 'CRITICAL', domain, provider)

    @tornado.gen.coroutine
    def server_cpu_status(self, server_name, status, provider = '', domain = ''):
        cl = salt.client.LocalClient()
        ts_name = server_name.upper()[7:13]
        cl.cmd('evo-master', 'evo_utils.terminal_cpu_status', [ts_name, status])

    @tornado.gen.coroutine
    def server_cpu_ok(self, server_name, provider = '', domain = ''):
        yield self.server_cpu_status(server_name, 'OK', provider, domain)

    @tornado.gen.coroutine
    def server_cpu_warning(self, server_name, provider = '', domain = ''):
        yield self.server_cpu_status(server_name, 'WARNING', provider, domain)

    @tornado.gen.coroutine
    def server_cpu_critical(self, server_name, provider = '', domain = ''):
        yield self.server_cpu_status(server_name, 'CRITICAL', provider, domain)

    @tornado.gen.coroutine
    def server_set_hardware(self, provider, server_name, cpu = 0, memory = 0, add = False, domain = ''):
        server_name = server_name.upper()

        print ('From args : memory = ', memory)

        self.get_datacenter(provider)
        servers = self.get_servers_list(provider)
        server = [x for x in servers if server_name in x.name and x.status == 'active'] or [None]
        server = server[0]
       
        if add: 
            if cpu: cpu += server.cpu
            if memory: memory += server.memory

        if cpu == server.cpu and memory == server.memory: 
            raise tornado.gen.Return(True)

        print ('Setting cpu to ', cpu, ' and memory to : ', memory)
        try:
            data = []
            if cpu: 
                data.append({
                   "op":"set",
                   "member":"cpu",
                   "value":cpu
                })
            if memory: 
                data.append({
                   "op":"set",
                   "member":"memory",
                   "value":memory
                })
            url = 'servers/%s/%s' % (self.account.alias, server.name)
            print ('Adding hardware at :  ',url, ' with data ', data) 
            result = clc.v2.API.Call('patch', url, json.dumps(data))
            yield self.wait_for_clc_action({'links' : [result]})

        except: 
            import traceback
            traceback.print_exc()
            raise
        raise tornado.gen.Return(True)



    @tornado.gen.coroutine
    def get_steps(self):
        """ Uses the generic get_steps """
        steps = yield super(CenturyLinkDriver, self).get_steps()

        steps[0].add_fields([
            ('location', 'Select the location for the datacenter you want to be using, or use the Primary Datacenter. ', 'options'),
        ])

        self.steps = steps
        raise tornado.gen.Return(steps)

    @tornado.gen.coroutine
    def get_networks(self):
        """ Properly gets networks. The url variable is there in case we need the REST API. """
        networks = self.datacenter.Networks().networks
        networks = [x.name for x in networks]
#        url = '/v2-experimental/networks/{accountAlias}/{dataCenter}'
        raise tornado.gen.Return(networks)

    @tornado.gen.coroutine
    def get_sec_groups(self):
        """ Gets the ordinary Groups, despite being called "get_sec_groups()". The name is kept the same for consistency. The url variable is there in case we need the REST API. """
        sec_groups = self.datacenter.Groups().groups
        sec_groups = [x.name for x in sec_groups]
#        url = '/v2/groups/account/id'
        raise tornado.gen.Return(sec_groups)

    @tornado.gen.coroutine
    def get_images(self):
        """ Gets the images. Currently, lists templates, but in the future, it will use the datastore. The url variable is there in case we need the REST API. """ 
        images = self.datacenter.Templates().templates
#        images = self.api.Call('post', 'Blueprint/GetBlueprints', {'Visibility' : 1})
        images = [x.name for x in images]       
#        url = '/v2/datacenters/account/datacenter/deploymentCapabilities'
        raise tornado.gen.Return(images)

    @tornado.gen.coroutine
    def get_sizes(self):
        """ Returns the flavours kept in the datastore. """
        sizes = self.flavours.keys()
        raise tornado.gen.Return(sizes)

    @tornado.gen.coroutine
    def get_server(self, provider, server_name):
        """ Gets the server by the server name, for instance, TS011, instead of the full id. """
        self.get_datacenter(provider)
        servers = self.get_servers_list(provider)
        server = [x for x in servers if server_name in x.id] or [None]
        server = server[0]
        return server


    @tornado.gen.coroutine
    def get_server_data(self, provider, server_name):
        server = yield self.get_server(provider, server_name)
        raise tornado.gen.Return(server.data)


    @tornado.gen.coroutine
    def delete_server(self, provider, server_name):
        """ Deletes a server, passed to the function via name (not ID).  """
        server = yield self.get_server(provider, server_name)
        success = server.Delete()
        raise tornado.gen.Return(True)

    @tornado.gen.coroutine
    def validate_field_values(self, step_index, field_values):
        """ Authenticates via the python API. """
        if step_index < 0:
            raise tornado.gen.Return(StepResult(
                errors=[], new_step_index=0, option_choices={'location' : self.locations}
            ))
        elif step_index == 0:
#            self.provider_url = field_values['provider_url']
            clc.v2.SetCredentials(field_values['username'], field_values['password'])
            clc.v1.SetCredentials(field_values['username'], field_values['password'])
            self.account = clc.v2.Account() # Maybe just use v1? v2 has no endpoints for blueprints yet...

            if field_values['location'] == 'PrimaryDatacenter': 
                self.datacenter = self.account.PrimaryDatacenter()
            else: 
                self.datacenter = [x for x in clc.v2.Datacenter.Datacenters() if field_values['location'] in x.location][0]

            self.field_values['location'] = self.datacenter.location

#            clc.v1.SetCredentials(field_values['api_key'], field_values['api_secret'])
#            self.api = clc.v1.API #Needed for blueprints and other v1 actions
#            self.token = yield self.get_token(field_values)

      	step_result = yield super(CenturyLinkDriver, self).validate_field_values(step_index, field_values)
        raise tornado.gen.Return(step_result)
      
    @tornado.gen.coroutine
    def create_server(self, provider, data):
        print ('Creating minion with data: ', data)
        try: 
            clc.v2.SetCredentials(provider['username'], provider['password'])
            self.account = clc.v2.Account()
            self.get_datacenter(provider)

            flavour = self.flavours[data['size']]
            print ('Memory is : ', flavour['memory'])
            memory = flavour['memory'] / (2**30)

            server_data = {
              "name": data['server_name'],
              "hostName": data['server_name'],
              "description": "Created from the VA dashboard. ",
              "groupId": self.datacenter.Groups().Get(data['sec_group']).id,
              "sourceServerId": self.datacenter.Templates().Get(data['image']).id,
              "isManagedOS": False,
              "networkId": self.datacenter.Networks().Get(data['network']).id,
              "cpu": flavour['num_cpus'],
              "memoryGB": memory,
              "type": "standard",
              "storageType": "standard",
            }
            if data.get('storage'): 
                server_data['additionalDisks'] = [
                    {
#                        'path' : 'data', 
                        'sizeGB' : data['storage'], 
                        'type' : 'raw'
                    }
                ]

            print ('Extra args are : ',data.get('extra_kwargs'))
            #Extra args are usually supplied by external applications. 
            server_data.update(data.get('extra_kwargs', {}))

            print ('Creating server with data : ', server_data)

            success = clc.v2.API.Call('post', 'servers/%s' % (self.account.alias), json.dumps(server_data), debug = True)


            if data.get('wait_for_finish', True): 
                yield self.wait_for_clc_action(success)

                server_url = [x for x in success['links'] if x['rel'] == 'self'][0]['href']
                success = clc.v2.API.Call('get', server_url)
        except: 
            import traceback
            traceback.print_exc()
        print ('Returning: ', success)
        raise tornado.gen.Return(success)

