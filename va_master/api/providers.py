from .login import auth_only
import tornado.gen
from tornado.gen import Return
from va_master.utils.va_utils import int_to_bytes
import json
import panels, apps



def get_paths():
    paths = {
        'get' : {
            'drivers' : {'function' : list_drivers, 'args' : ['drivers_handler']},
            'drivers/get_steps' : {'function' : get_driver_steps, 'args' : ['handler', 'driver_name']},

            'providers/get_trigger_functions': {'function' : get_providers_triggers, 'args' : ['provider_name']},
            'providers/get_provider_billing' : {'function' : get_provider_billing, 'args' : ['provider_name']},
            'providers/billing' : {'function' : get_providers_billing, 'args' : ['handler']},
            'providers/get_provider_fields' : {'function' : get_provider_fields, 'args' : ['handler', 'provider_name']},
            'providers/get_provider_servers' : {'function' : get_provider_servers, 'args' : ['handler', 'provider_name']},

            'providers' : {'function' : list_providers, 'args' : ['handler']},

        },
        'post' : {
            'providers' : {'function' : list_providers, 'args' : ['handler']},
            'providers/info' : {'function' : get_providers_info, 'args' : ['handler', 'dash_user', 'required_providers', 'get_billing', 'get_servers', 'sort_by_location']},
            'providers/new/validate_fields' : {'function' : validate_new_provider_fields, 'args' : ['handler', 'driver_id', 'field_values', 'step_index', 'provider_name']},
            'providers/delete' : {'function' : delete_provider, 'args' : ['datastore_handler', 'provider_name']},
            'providers/add_provider' : {'function' : add_provider, 'args' : ['datastore_handler', 'field_values', 'driver_name']},
            'providers/generic_add_server' : {'function' : add_generic_server, 'args' : ['datastore_handler', 'provider_name', 'server']},
        },
        'put' : {
            'providers/new/validate_fields' : {'function' : validate_new_provider_fields, 'args' : ['handler', 'driver_id', 'field_values', 'step_index']},
        },

    }
    return paths

#Utility function used internally in the API. 
@tornado.gen.coroutine
def get_provider_and_driver(handler, provider_name = 'va_standalone_servers'):
    provider = yield handler.datastore_handler.get_provider(provider_name = provider_name)
    driver = yield handler.drivers_handler.get_driver_by_id(provider['driver_name'])

    raise tornado.gen.Return((provider, driver))

@tornado.gen.coroutine
def add_provider(datastore_handler, field_values, driver_name):
    """Creates a provider with the specified field values. Most of the time not used directly, but can be used by external APIs. """
    provider_field_values = {"username": "user", "sizes": [], "images": [], "provider_name": "sample_provider", "servers": [], "driver_name": "generic_driver", "defaults": {}, "sec_groups": [], "password": "pass", "ip_address": "127.0.0.1", "networks": []}
    provider_field_values.update(field_values)

    yield datastore_handler.create_provider(provider_field_values)

    raise tornado.gen.Return(True)


@tornado.gen.coroutine
def add_generic_server(datastore_handler, provider_name, server):
    """Adds a server to the list of servers for the specified provider. """
    base_server = {"hostname" : "", "ip" : "", "local_gb" : 0, "memory_mb" : 0, "status" : "n/a" }
    base_server.update(server)

    yield datastore_handler.add_generic_server(provider_name, base_server)

@tornado.gen.coroutine
def get_provider_billing(handler, provider_name):
    """Returns billing data for the specified provider. """
    provider, driver = yield get_provider_and_driver(handler, provider_name)
    result = yield driver.get_provider_billing(provider)
    raise tornado.gen.Return(result)

@tornado.gen.coroutine
def get_providers_triggers(handler, provider_name):
    """Gets a list of triggers for the specified provider. """
    provider, driver = yield get_provider_and_driver(handler, provider_name)
    result = yield driver.get_driver_trigger_functions()
    raise tornado.gen.Return(result)

#TODO finish documentation properly. 
@tornado.gen.coroutine
def list_providers(handler):
    """
        description: Gets a list of providers from the datastore. Adds the driver name to the list, and gets the status. Gets a list of servers for each provider and, if there are any hidden servers, they are removed from the list. Also returns various dashboard-specific data which helps with formatting on the frontend. 
        output: '{"providers": [{"username": "admin", "provider_conf": "provider_conf", "provider_ip": "https://127.0.0.1", "sec_groups": ["No security groups. "], "sizes": ["va-small"], "profile_conf_dir": "/etc/salt/cloud.profiles.d/some_profile.conf", "servers": [{"status": "ACTIVE", "ip": "127.0.0.1", "used_ram": 1442.01171875, "used_disk": 1, "cost": 0, "size": "va-small", "used_cpu": 1, "hostname": "va-master", "estimated_cost": 0, "provider": "lxd", "provider_name": "lxd"}, "steps": [{"fields": [{"blank": false, "type": "str", "id": "provider_name", "value": "lxd", "name": "Name for the host"}, {"blank": false, "type": "str", "id": "username", "value": "admin", "name": "Username"}, {"blank": false, "type": "str", "id": "password", "value": "admin", "name": "Password"}, {"blank": false, "type": "str", "id": "location", "value": "googl", "name": "Enter the location of the host"}, {"blank": false, "type": "str", "id": "provider_ip", "value": "https://10.81.160.1:8443", "name": "IP of the lxc host."}], "name": "Provider info"}, {"fields": [{"blank": false, "type": "description", "id": "netsec_desc", "value": "", "name": "Current connection info"}, {"blank": false, "type": "options", "id": "network", "value": "", "name": "Pick network"}, {"blank": false, "type": "options", "id": "sec_group", "value": "", "name": "Pick security group"}], "name": "Network & security group"}, {"fields": [{"blank": false, "type": "options", "id": "image", "value": "", "name": "Image"}, {"blank": false, "type": "options", "id": "size", "value": "", "name": "Size"}], "name": "Image & size"}], "provider_name": "lxd", "password": "admin", "networks": ["lxdbr0", "lo", "eth0"]}]}'
    """
    datastore_handler = handler.datastore_handler
    drivers_handler = handler.drivers_handler

    providers = yield datastore_handler.list_providers()
    hidden_servers = yield datastore_handler.get_hidden_servers()

    for provider in providers: 
        driver = yield drivers_handler.get_driver_by_id(provider['driver_name'])
        provider['servers'] = yield driver.get_servers(provider)
        
        provider_status = yield driver.get_provider_status(provider)
        provider['status'] = provider_status

        if hidden_servers: 
            provider['servers'] = [x for x in provider['servers'] if x['hostname'] not in hidden_servers]

    providers = [x for x in providers if x['provider_name']]

    for p in providers: 
        driver = yield handler.drivers_handler.get_driver_by_id(p['driver_name'])
        steps = yield driver.get_steps()
        steps = [x.serialize() for x in steps]
        for step in steps: 
            for field in step['fields']: 
                field['value'] = p.get(field['id'], '')
        p['steps'] = steps

    raise tornado.gen.Return({'providers': providers})


@tornado.gen.coroutine
def delete_provider(datastore_handler, provider_name):
    """Deletes the provider with provider_name. """
    yield datastore_handler.delete_provider(provider_name)

@tornado.gen.coroutine
def get_provider_fields(handler, provider_name):
    drivers_handler = handler.drivers_handler
    datastore_handler = handler.datastore_handler

    provider = yield datastore_handler.get_provider(provider_name)
    driver_name = provider['driver_name']
    driver = yield drivers_handler.get_driver_by_id(driver_name)

    steps = yield driver.get_steps()
    steps = [x.serialize() for x in steps]
    result = {'id' : driver_name, 'optionChoices' : {}}

    if provider_name: 
        for step in steps: 
            for field in step['fields']: 
                field['value'] = provider.get(field['id'], '') or provider['defaults'].get(field['id'], '')
                if field.get('option_choices'): 
                    result['optionChoices'].update(field['option_choices'])
                    
    result['steps'] = steps
    raise tornado.gen.Return(result)


@tornado.gen.coroutine
def get_driver_steps(handler, driver_name):
    drivers_handler = handler.drivers_handler

    driver = yield drivers_handler.get_driver_by_id(driver_name)
    steps = yield driver.get_steps()
    steps = [x.serialize() for x in steps]

    raise tornado.gen.Return(steps)

#TODO specify steps
@tornado.gen.coroutine
def list_drivers(drivers_handler):
    """
        description: Gets a list of drivers. 
        output: '{"id" : "provider_id", "friendly_name" : "Provider", "steps" : []}'
    """
    drivers = yield drivers_handler.get_drivers()
    out = {'drivers': []}
    for driver in drivers:
        driver_id = yield driver.driver_id()
        name = yield driver.friendly_name()
        steps = yield driver.get_steps()
        steps = [x.serialize() for x in steps]
        out['drivers'].append({'id': driver_id, 'friendly_name': name, 'steps': steps})
    raise tornado.gen.Return(out)

@tornado.gen.coroutine
def validate_new_provider_fields(handler, driver_id, field_values, step_index, provider_name = ''):
    """Used when adding new providers. Makes sure all the fields are entered properly, and proceeds differently based on what driver is being used. """

    step_index = int(step_index)
    drivers_handler = handler.drivers_handler
    datastore_handler = handler.datastore_handler
    found_driver = yield drivers_handler.get_driver_by_id(driver_id)

    driver_steps = yield found_driver.get_steps()
    if step_index >= len(driver_steps) or step_index < -1:
        raise Exception('Step index was : ' + str(step_index) + ' but the number of steps is : ' + str(driver_steps))

    if step_index < 0 or driver_steps[step_index].validate(field_values):
        result = yield found_driver.validate_field_values(step_index, field_values)
        if result.new_step_index == -1:
            datastore_handler.create_provider(found_driver.field_values)
        result = result.serialize()
    else:
        result = {
            'errors': ['Some fields are not filled.'],
            'new_step_index': step_index,
            'option_choices': None
        }

    if provider_name: 
        provider = yield handler.datastore_handler.get_provider(provider_name)
        for field in result['fields']: 
            field['value'] = provider.get(field['id'], '')


    raise tornado.gen.Return(result)


@tornado.gen.coroutine
def get_providers_billing_data(handler):
    drivers_handler = handler.drivers_handler
    datastore_handler = handler.datastore_handler

    providers = yield datastore_handler.list_providers()

    provider_drivers = yield [drivers_handler.get_driver_by_id(x['driver_name']) for x in providers]
    providers_data = [x[0].get_provider_billing(provider = x[1]) for x in zip(provider_drivers, providers)]

    result = yield providers_data
    result = [x for x in result if x]

    raise tornado.gen.Return(result)


@tornado.gen.coroutine
def get_providers_billing(handler):
    providers_billing_data = yield get_providers_billing_data(handler)
    providers = []
    for provider in providers_billing_data: 
        p = {
                'provider': provider['provider']['provider_name'], 
                'subRows': [{
                    'server': server['hostname'], 
                    'cpu': server['used_cpu'], 
                    'memory': int_to_bytes(server['used_ram']), 
                    'hdd': int_to_bytes(server['used_disk']), 
                    'cost': server['cost'], 
                    'e_cost': server['estimated_cost']
                } for server in provider['servers']]

        }
        for attr in ['cpu', 'memory', 'hdd', 'cost', 'e_cost']: 
            if provider['provider'].get(attr): 
                p[attr] = provider['provider'][attr]
        providers.append(p)

    result = { 
        'dataSource': providers, 
        'rows': [
        {
            'key': 'provider', 
            'label': 'Provider'
        }, {
            'key': 'server', 
            'label': 'Server' 
        }], 
        'data': [ 
        {
            'key': 'cpu', 
            'label': 'CPU',
            'type' : 'number', 
        }, {
            'key': 'memory', 
            'label': 'Memory',
            'type' : 'number',
        }, {
            'key': 'hdd', 
            'label': 'HDD',
            'type' : 'number',
        }, {
            'key': 'cost', 
            'label': 'Cost',
            'type' : 'number',
        }, {
            'key': 'e_cost', 
            'label': 'Estimated cost',
            'type' : 'number',
        }] 
    }
    raise tornado.gen.Return(result)

#TODO specify output
@tornado.gen.coroutine
def get_providers_info(handler, dash_user, get_billing = True, get_servers = True, required_providers = [], sort_by_location = False):
    """
        description: Gets all info fior all providers - servers and their usages, the provider usage, images, sizes, networks, security groups, billing info and all provider datastore data. If get_billing is false, then the billing data will be empty. Same for get_servers. If required_providers is set, the providers are filtered to only show the providers with a provider_name in that list. If sort_by_location is true, then this sorts providers in a dictionary object where the keys are the locations of the providers. 
        output: A list of providers with stats for their servers and provider-specific stats. 
        arguments: 
          - name: get_billing
            description: If set, also returns billing data for the providers. 
            required: False
            type: bool
            default: True
          - name: get_servers
            description: If set, also returns all servers
            required: False
            type: bool
            default: True
          - name: required_providers
            description: If set, only returns data for specified providers
            required: False
            type: list
            default: list
          - sort_by_location: 
            description: 'If set, sorts providers by location, as {"loc1" : ["list", "of", "providers"], "loc2" : [...]}'
            required: False
            type: bool
            default: False
    """
    drivers_handler = handler.drivers_handler
    datastore_handler = handler.datastore_handler

    hidden_servers = yield datastore_handler.get_hidden_servers()
    providers = yield datastore_handler.list_providers()

    if required_providers: 
        providers = [provider for provider in providers if provider['provider_name'] in required_providers]

    provider_drivers = yield [drivers_handler.get_driver_by_id(x['driver_name']) for x in providers]
    providers_data = [x[0].get_provider_data(provider = x[1], get_servers = get_servers, get_billing = get_billing) for x in zip(provider_drivers, providers)]
    providers_info = yield providers_data
   
    states = yield panels.list_panels(datastore_handler, dash_user)

    for p_info in zip(providers_info, providers):
        provider = p_info[0]
        provider_kv = p_info[1]

        provider['provider_name'] = provider_kv['provider_name']
        provider['location'] = provider_kv['location']

        if hidden_servers: 
            provider['servers'] = [x for x in provider['servers'] if x['hostname'] not in hidden_servers]

        for server in provider['servers']:
            server_panel = [x for x in states if server.get('hostname', '') in x['servers']] or [{'icon' : 'fa-server'}]
            server['icon'] = server_panel[0]['icon']
            datastore_server = yield datastore_handler.get_object(object_type = 'server', server_name = server.get('server_name', server.get('hostname', '')))
            if not datastore_server: 
                if provider['provider_name']: 
                    print ('Did not find server', server.get('hostname'), 'in kv, inserting now with ', provider_kv['driver_name'], provider_kv['provider_name'])
                    datastore_server = yield apps.manage_server_type(datastore_handler, server_name = server.get('hostname'), new_type = 'provider', driver_name = provider_kv['driver_name'], provider_name = provider_kv['provider_name'])
                else: 
                    print ('Found standalone server: ', server.get('hostname'), server, ' adding now. ')
                    yield apps.add_server_to_datastore(datastore_handler, server_name = server['server_name'], ip_address = server['ip_address'], hostname = server['hostname'], manage_type = 'ssh', username = server['username'], kwargs = {'password' : server.get('password', ''), 'location' : server.get('location', '')})
#                    datastore_server = yield apps.manage_server_type(datastore_handler, server_name = server.get('hostname'), new_type = 'ssh', ip_address = server['ip_address'], username = server['username'], role = server.get('role')i)

            server.update(datastore_server)
            server['managed_by'] = server.get('managed_by', ['unmanaged'])
            server['available_actions'] = server.get('available_actions', {})

    providers_info = [x for x in providers_info if x['provider_name']]

    standalone_default_values = {'size' : ''}
    standalone_provider = yield datastore_handler.get_provider('va_standalone_servers')
    standalone_driver = yield drivers_handler.get_driver_by_id('generic_driver')
    standalone_servers = yield standalone_driver.get_servers(standalone_provider)
    standalone_provider_data = yield standalone_driver.get_provider_data({'provider_name' : 'va_standalone_servers'})


    for s in standalone_servers: 
        print ('Have : ', s, ' for servers')
        datastore_server = yield datastore_handler.get_object(object_type = 'server', server_name = server.get('server_name', server.get('hostname', '')))
        s.update(datastore_server)

    for v in standalone_default_values: 
        [x.update({v : x.get(v, standalone_default_values[v])}) for x in standalone_servers]

    standalone_locations = set([x.get('location', 'va-master') for x in standalone_servers])
    standalone_providers = [
        {
            "provider_name" : "", 
            "servers" : [x for x in standalone_servers if x.get('location', 'va-master') == l], 
            "provider_usage" : standalone_provider_data['provider_usage'],
            "status" : standalone_provider_data['status'],
            "location" : l,
        } for l in standalone_locations]

    print ('Standalone are : ', standalone_providers)
    providers_info += standalone_providers

    if sort_by_location: 
        #Convert to {"location" : [list, of, providers], "location2" : [list, of, other, providers]}


        providers_info = {l : 
            [x for x in providers_info if x.get('location', 'va-master') == l] for l in [x.get('location', 'va-master')
         for x in providers_info]}

    raise tornado.gen.Return(providers_info)


@tornado.gen.coroutine
def get_provider_servers(handler, provider_name):
    """
        description: Gets a list of servers for the specified provider. 
        arguments: 
          - name: provider_name
            description: Will query the provider with this name for a list of servers it provisions. 
            type: string
            required: True
            example: va_provider
        output: 
          - status: ACTIVE,
            ip: 10.81.160.75
            used_ram: 1435.83984375
            used_disk: 1
            cost: 0
            size: va-master
            used_cpu: 1
            hostname: va-master
            estimated_cost: 0
            provider: lxd
            provider_name: lxd 
        visible: True
    """
    provider, driver = yield get_provider_and_driver(handler, provider_name)
    result = yield driver.get_servers(provider)
    raise tornado.gen.Return(result)
