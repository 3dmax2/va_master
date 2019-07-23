from .login import auth_only
import tornado.gen
import json
import subprocess
import requests, paramiko
import zipfile, tarfile

from va_master.utils.paramiko_utils import ssh_call
from va_master.utils.va_utils import bytes_to_readable, get_route_to_minion, call_master_cmd

from va_master.api.integrations import trigger_all_integrations

from va_master.handlers.server_management import manage_server_type
from va_master.handlers.salt_handler import add_minion_to_server
from va_master.handlers.app_handler import install_new_app, handle_app_action
from tornado.concurrent import run_on_executor, Future

import salt_manage_pillar
from salt.client import Caller, LocalClient

import panels, services, providers
from va_master.handlers.ssh_handler import handle_ssh_action


def get_paths():
    paths = {
        'get' : {
            'apps/set_settings' : {'function' : set_settings, 'args' : ['settings']},
            'apps/vpn_users' : {'function' : get_openvpn_users, 'args' : []},
            'apps/vpn_status' : {'function' : get_openvpn_status, 'args' : []},
#            'apps/add_app' : {'function' : add_app, 'args' : ['provider', 'server_name']},

            'apps/get_user_salt_functions' : {'function' : get_user_salt_functions, 'args' : ['dash_user']},
            'apps/get_all_salt_functions' : {'function' : get_all_salt_functions, 'args' : []},

            'states' : {'function' : get_states, 'args' : ['handler', 'dash_user']},
            'apps' : {'function' : get_states, 'args' : ['handler', 'dash_user']},

        },
        'post' : {
            'state/add' : {'function' : create_new_state,'args' : ['file', 'body', 'filename']},
            'states/reset' : {'function' : reset_states, 'args' : ['datastore_handler']}, 
            'apps/new/validate_fields' : {'function' : validate_app_fields, 'args' : ['handler']},
            'apps/launch_app' : {'function' : launch_app, 'args' : ['handler', 'dash_user']},
            'apps/provision_app' : {'function' : provision_app, 'args' : ['handler', 'dash_user']},
            'apps/change_app_type' : {'function' : change_app_type, 'args' : ['datastore_handler', 'server_name', 'app_type']},
            'apps/install_new_app' : {'function' : install_app, 'args' : ['datastore_handler', 'app_zip', 'app_json']},
            'apps/get_app_required_args' : {'function' : get_app_args, 'args' : ['datastore_handler', 'app_name']},
            'apps/add_minion' : {'function' : add_minion_to_server, 'args' : ['datastore_handler', 'server_name', 'ip_address', 'username', 'password', 'key_filename', 'role']},
            'apps/action' : {'function' : perform_server_action, 'args' : ['handler', 'provider_name', 'action', 'server_name', 'action_type', 'kwargs']},
            'apps/add_vpn_user': {'function' : add_openvpn_user, 'args' : ['username']},
            'apps/revoke_vpn_user': {'function' : revoke_openvpn_user, 'args' : ['username']},
            'apps/list_user_logins': {'function' : list_user_logins, 'args' : ['username']},
            'apps/download_vpn_cert': {'function' : download_vpn_cert, 'args' : ['username', 'handler']},
            'servers/add_server' :  {'function' : add_server_to_datastore, 'args' : ['datastore_handler', 'server_name', 'ip_address', 'hostname', 'manage_type', 'user_type', 'driver_name', 'app_type', 'role', 'kwargs']},
            'servers/manage_server' : {'function' : manage_server_type, 'args' : ['datastore_handler', 'server_name', 'new_type', 'username', 'driver_name', 'role', 'ip_address', 'app_type']},
        }
    }
    return paths


@tornado.gen.coroutine
def get_openvpn_users():
    """
        description: Gets openvpn users and current status. Then merges users to find currently active ones and their usage data. 
        output: 
          active: 
            - test_user
          revoked: 
            - test_user_2
          status: {}
        visible: True
    """

    cl = LocalClient()
    openvpn_users = call_master_cmd('openvpn.list_users')

    if type(openvpn_users) == str: 
        raise Exception("Could not get openvpn users list. Contact your administrator for more information. ")

    #openvpn_users returns {"revoked" : [list, of, revoked, users], "active" : [list, of, active, users], "status" : {"client_list" : [], "routing_table" : []}}
    #We want to convert it to {"revoked" : [], "status" : [client, list], active" : [{"name" : "", "check" : False, "connected" : True/False}]}

    users = {'revoked' : openvpn_users['revoked']}
    users_names = [i['Common Name'] for i in openvpn_users['status']['client_list']]
    users['active'] = [{'name' : x, 'check' : False, 'connected' : x in users_names} for x in openvpn_users['active']]
    users['status'] = openvpn_users['status']['client_list'] or []

    #Virtual address is missing from client_list, we have to find it in the routing table and update it. 
    for x in openvpn_users['status']['client_list']:
        x.update({
            'Real Address' : [y.get('Virtual Address') for y in openvpn_users['status']['routing_table'] if y['Real Address'] == x['Real Address']][0]
        })
       
    #Make bytes human readable
    for k in ['Bytes Received', 'Bytes Sent']:
        for x in openvpn_users['status']['client_list']:
            x[k] = bytes_to_readable(x[k])

    raise tornado.gen.Return(users)

@tornado.gen.coroutine
def get_openvpn_status():
    """Just gets the openvpn status information, which lists the current clients. """

    status = call_master_cmd('openvpn.get_status')
    raise tornado.gen.Return(status)

@tornado.gen.coroutine
def add_openvpn_user(username):
    """
        description: Creates a new openvpn user. 
        arguments: 
          - name: username
            description: The username for the new user
            required: True
            type: string
            example: test_user
        visible: True
        
    """

    success = call_master_cmd('openvpn.add_user', kwarg = {'username' : username})
    if not success:
        raise Exception('Adding an openvpn user returned with an error. ')
    raise tornado.gen.Return({'success' : True, 'data' : None, 'message' : 'User added successfuly. '})

@tornado.gen.coroutine
def revoke_openvpn_user(username):
    """
        description: Revokes an existing vpn user
        arguments: 
          - name: username
            description: The username of the user to be revoked
            required: True
            type: string
            
    """

    success = call_master_cmd('openvpn.revoke_user', kwarg = {'username' : username})
 
    if success:
        raise Exception('Revoking %s returned with an error. ' % (username))
    raise tornado.gen.Return({'success' : True, 'data' : None, 'message' : 'User revoked successfuly. '})

    raise tornado.gen.Return(success)   

@tornado.gen.coroutine
def list_user_logins(username): 
    """
        description: Provides a list of previous openvpn logins. 
        arguments: 
          - name: username
            description: Will return a list of logins for the user with this username
            required: True
            type: string
        output: A list of user logins. 
    """

    success = call_master_cmd('openvpn.list_user_logins', kwarg = {'username' : username})
    if type(success) == str:
        raise Exception('Listing user logins returned with an error. ')
    raise tornado.gen.Return(success)

@tornado.gen.coroutine
def download_vpn_cert(username, handler):
    """
        description: Downloads the vpn certificate for the required user. Works by copying the file to /tmp/{username}_vpn.cert and then serving it through Tornado. 
        arguments: 
          - name: username
            description: Returns the vpn cert for this username. 
        output: Serves the vpn cert for the user. 
        visible: True
    """
    success = call_master_cmd('openvpn.get_config', kwarg = {'username' : username})

    cert_has_error = yield handler.has_error(cert)
    if cert_has_error:
        raise Exception('Getting certificate for %s returned with an error. ' % (username))

    vpn_cert_path = '/tmp/' + username + '_vpn.cert'
    with open(vpn_cert_path, 'w') as f: 
        f.write(cert)
 
    handler.serve_file(vpn_cert_path)
    raise tornado.gen.Return({'data_type' : 'file'})

@tornado.gen.coroutine
def perform_server_action(handler, action, server_name, provider_name = '', action_type = '', args = [], kwargs = {}): 
    """Calls required action on the server through the driver. """

    #Either we expect {action_type: ssh, action: some_action} or action: ssh/some_action  (or provider | app for the action type)
    if not action_type: 
        if '/' not in action: 
            raise Exception('action_type argument is empty, so action is expected to be in format <action_type/<action> (example: ssh/show_processes), but instead action was : ' + str(action))
        action_type, action = action.split('/')

    server = yield handler.datastore_handler.get_object('server', server_name = server_name)


    result = None
    if action_type == 'app' : 
        result = yield handle_app_action(handler, server = server, action = action, args = args, kwargs = kwargs)
    else: 
        provider_name = provider_name or 'va_standalone_servers'
        
        provider, driver = yield providers.get_provider_and_driver(handler, provider_name) 
        result = yield driver.server_action(provider, server_name, action)

    if type(result) != dict: 
        result = {'success' : True, 'message' : '', 'data' : result}

    result['message'] = 'Action %s completed successfuly. ' % action
    raise tornado.gen.Return(result)


@tornado.gen.coroutine
def get_states(handler, dash_user):
    """
        description: Gets all states from the datastore. Stats can be read from the consul kv store by doing `consul kv get -recurse states/`. This data is populated when doing `python -m va_master manage --reset-state. The state data is retrieved from the appinfo.json files in their respective folders. Each appinfo has needs to have a module, panels, name, description, version, icon, dependency, substate and path field. 
        output: [{"name": "state_name", "icon": "fa-icon", "module": "va_module", "servers": [], "dependency": "", "version": "1.2", "path": "-", "panels": [{"name": "Friendly name", "key": "module.panel_name"}], "substates": ["substate"], "description": ""}]
    """
    
    datastore_handler = handler.datastore_handler
    states_data = yield datastore_handler.get_states_and_apps()
    panels_data = yield panels.list_panels(datastore_handler, dash_user)

    default_panels = {'admin' : [], 'user' : []}

    print (state['name'] for x in states_data)
    for state in states_data: 
        state_panel = [x for x in panels_data if x['name'] == state['name']]
        if not state_panel: 
            raise Exception(state['name'] + 'was not found in the list of states : ' + str([x['name'] for x in panels_data]))
        state_panel = state_panel[0]
        state['servers'] = state_panel['servers']
        state['panels'] = state.get('panels', default_panels)[dash_user['type']]
    raise tornado.gen.Return(states_data)

#WIP function - TODO check if it still works properly. 
@tornado.gen.coroutine
def create_new_state(datastore_handler, file_contents, body, filename):
    """Creates a new state from a file, unpack it to the state directory and add it to the datastore. """

    data = file_contents[0]
    files_archive = data['body']
    state_name = data['filename']

    #TODO maybe get it from config? 
    salt_path = '/srv/salt/'
    tmp_archive = '/tmp/' + state_name 

    with open(tmp_archive, 'w') as f:
        f.write(files_archive)

    new_state = {
        'name' : data['name'],
        'version' : data['version'],
        'description' : data['description'], 
        'icon' : data['icon'], 
        'dependency' : data['dependency'], 
        'path' : data['path'],
        'substates' : data['substates']
    }

    with open(salt_path + tar_ref.getnames()[0] + '/appinfo.json', 'w') as f: 
        f.write(json.dumps(new_state))

    tar_ref = tarfile.TarFile(tmp_archive)
    tar_ref.extractall(salt_path)

    yield datastore_handler.add_state(new_state)

    tar_ref.close()

@tornado.gen.coroutine
def reset_states(datastore_handler):
    yield datastore_handler.datastore.delete('states/', {'recurse' : True})
    yield datastore_handler.import_states_from_states_data()

@tornado.gen.coroutine
def install_app(datastore_handler, app_zip, app_json):

    print (app_zip)
    app_zip = app_zip[0]['body']
    app_json = app_json[0]['body']
    print (app_json)
    app_json = json.loads(app_json)
    tmp_app = '/tmp/%s.tar.gz' % (app_json['name'])

    with open(tmp_app, 'w') as f:
        f.write(app_zip)
    yield install_new_app(datastore_handler, app_json, tmp_app)

@tornado.gen.coroutine
def get_app_args(datastore_handler, app_name):
    app = yield datastore_handler.get_object(object_type = 'app', app_name = app_name)
    raise tornado.gen.Return(app['required_args'])

@tornado.gen.coroutine
def change_app_type(datastore_handler, server_name, app_name):
    pass

@tornado.gen.coroutine
def validate_app_fields(handler):
    """
        description: Allows creating servers. Creates a server by going through a validation scheme similar to that for adding providers. Requires that you send a step index as an argument, whereas the specifics for the validation are based on what driver you are using. If no provider_name is sent, creates a server on the va_standalone_servers provider, which is mostly invisible, and its servers are treated as standalone. 
        arguments: TODO
        hide: True
    """
    provider, driver = yield providers.get_provider_and_driver(handler, handler.data.get('provider_name', 'va_standalone_servers'))

    kwargs = handler.data
    step = handler.data.pop('step')

    fields = yield driver.validate_app_fields(step, **kwargs)

    # If the state has extra fields, then there are 3 steps, otherwise just 2. 
    if step == 3: 
        handler.data.update(fields)
        try:
            result = yield handler.executor.submit(launch_app, handler)
        except: 
            import traceback
            traceback.print_exc()
    raise tornado.gen.Return(fields)


@tornado.gen.coroutine
def get_app_info(server_name):
    """Gets mine inventory for the provided instance. """

    server_info = call_master_cmd('mine.get', arg = [server_name, 'inventory'])
    if not server_info: 
        raise Exception('Attempted to get app info for %s but mine.get returned empty. ' % (server_name))
    raise tornado.gen.Return(server_info)


def write_pillar(data):
    """Writes the supplied data as a yaml file in to a credentials file and adds it to the top credentials. """

    pillar_path = '/srv/pillar/%s-credentials.sls' % (data.get('server_name'))
    with open(pillar_path, 'w') as f: 
        pillar_str = ''

        #We need a pillar that looks like this: 
        #field1: some_value
        #field2: some_other_value

        for field in data.get('extra_fields'): 
            pillar_str += '%s: %s\n' % (field, data['extra_fields'][field])
        f.write(pillar_str)
    salt_manage_pillar.add_server(data.get('server_name'), data.get('role', ''))


@tornado.gen.coroutine
def provision_app(handler, dash_user):
    yield trigger_all_integrations(handler, dash_user, event_name = 'va-master.apps/launch_app', kwargs = {'status' : 'Initialized'})
#    yield tornado.gen.sleep(15)

    new_server = yield launch_app(handler, dash_user)
    yield trigger_all_integrations(handler, dash_user, event_name = 'va-master.apps/launch_app', kwargs = {'status' : 'Created'})
#    yield tornado.gen.sleep(15)

    result = yield add_minion_to_server(handler.datastore_handler, handler.data['server_name'], new_server['ip_address'], handler.data['role'], key_filename = '/root/.ssh/va-master.pem', username = handler.data.get('username', 'root'))
    yield trigger_all_integrations(handler, dash_user, event_name = 'va-master.apps/launch_app', kwargs = {'status' : 'Completed'})



@tornado.gen.coroutine
def launch_app(handler, dash_user):
    """
        description: "Launches a server based on the data supplied. This is dependent on the specific data required by the providers. 
    The default for starting servers is using salt-cloud -p <profile> <minion_name>, where the drivers are responsible for creating the configuration files. 
    Some drivers work independent of salt though, such as libvirt. 
    If the extra_fields key is supplied, it will create a specific pillar for the server. 
    If provider_name is not sent, it will create a va_standalone server, with the invisible driver va_standalone_servers. 
    If role is sent, then the function will try to get data for the minion using salt-call mine.get  <minion_name> inventory. If it does this successfully, it will add the server to the datastore, and add a ping service for the server. 
Updates the subscriptions status. "
        output: None
        arguments: 
          - name: provider_name
            description: The provider which will be used to create a server. If none, the it will be added as a standalone server. 
            type: string
            required: False
            default: va_standalone_servers
          - name: server_name 
            description: The name of the server which will be used to display the server on the va-master.
            type: string
            required: True
          - name: ip
            description: The IP address of the server. If not set, then it is up to the provider to return an ip address for the server. 
            type: string
            required: False 
          - name: role
            description: The role of the server. This is typically used for salt, but in general, servers should have an app associated with them. 
            required: True
        visible: True
        event: True
        data_prefix: "kwargs"
    """

    data = handler.data
    print ('Creating with data : ', data)
    try:
        provider, driver = yield providers.get_provider_and_driver(handler, data.get('provider_name', 'va_standalone_servers'))
    
        if data.get('extra_fields', {}) : 
            write_pillar(data)
    except: 
        import traceback
        traceback.print_exc()

    result = yield driver.create_server(provider, data)

    if provider.get('provider_name') and provider.get('provider_name', '') != 'va_standalone_servers': 
        yield add_server_to_datastore(handler.datastore_handler, server_name = data['server_name'], hostname = data['server_name'], manage_type = 'provider', driver_name = provider['driver_name'], ip_address = data.get('ip'))

    if data.get('role', False):

        yield panels.new_panel(handler.datastore_handler, data['server_name'], data['role'])
        minion_info = None

        retries = 0
        while not minion_info and retries < int(handler.data.get('mine_retries', '10')):
            minion_info = yield get_app_info(handler.data['server_name'])
            minion_info.update({'type' : 'app'})

            retries += 1
            if not minion_info: 
                yield tornado.gen.sleep(10)

#        yield services.add_services_presets(minion_info, ['ping'])

#        if not minion_info: 
#            raise tornado.gen.Return({"success" : False, "message" : "No minion_info, something probably went wrong with trying to start the instance. ", "data" : None})
#        else: 
#            yield manage_server_type(handler.datastore_handler, server_name = data['server_name'], new_type = 'app', role = data['role'])


    raise tornado.gen.Return(result)

#WIP - todo finish this function
@tornado.gen.coroutine
def get_all_salt_functions(datastore_handler):
    """ Gets all salt functions for all minions. """
    cl = LocalClient()
    states = yield datastore_handler.get_states_and_apps()

    functions = cl.cmd('*', 'sys.doc')
    result = {
        [i for i in x if x[states[x]['module']] in i] 
    for x in functions}

    raise tornado.gen.Return(result)

@tornado.gen.coroutine
def get_user_salt_functions(datastore_handler, dash_user):
    """Gets all functions tagged as 'salt' from the datastore for the logged in user. """

    salt_functions = yield datastore_handler.get_user_salt_functions(dash_user['username'])
    raise tornado.gen.Return(salt_functions)
    
@tornado.gen.coroutine
def add_user_salt_functions(datastore_handler, dash_user, functions):
    """Adds the list of salt functions for use for the logged in user. """

    yield datastore_handler.add_user_salt_functions(dash_user['username'], functions)

@tornado.gen.coroutine
def set_settings(settings):
    '''WIP function - writes a pillar using the settings. '''
    pillar_file = '/srv/pillar/nekoj.sls'
    with open(pillar_file, 'r') as f:
        a = yaml.load(f.read())

    a.update(settings)

    with open(pillar_file, 'w') as f:
        f.write(yaml.dump(a, default_flow_style=False))


@tornado.gen.coroutine
def add_server_to_datastore(datastore_handler, server_name, ip_address, hostname = None, manage_type = None, username = None, driver_name = None, role = None, app_type = 'salt', kwargs = {}):
    ''' 
    Main function for adding servers to the datastore. Servers are added to the `server/<server_name>` handles in the datastore, and have a server_namd and ip address. 
    In addition, servers can be managed by ssh, winexe or provider, which defines what actions can be called on them. This is done by holding values for a "managed_by" : ["ssh", "provider", "ssh"] list, and then holding values for an "available_actions" : {"provider" : [...], "ssh" : [...]} field. 
    If the server is not in the datastore, this function will add it.
    If it is, it will simply update the server_type, managed_by and available_actions fields. 
    '''

    import traceback
    traceback.print_exc()

    server = yield datastore_handler.get_object(object_type = 'server', server_name = server_name)

    to_add_server = False
    if not server: 
        to_add_server = True

    server.update(kwargs)
    print ('Server is : ', server)

    for attr in ['ip_address', 'hostname']:
        if locals()[attr]: 
            server[attr] = locals()[attr]

    if to_add_server:
        print ('Did not find ', server_name, ' now inserting it. ')
        print ('Server is : ', server, 'kwargs were : ', kwargs)
        yield datastore_handler.insert_object(object_type = 'server', server_name = server_name, data = server)

    if manage_type: 
        server = yield manage_server_type(datastore_handler, server_name, manage_type, username = username, driver_name = driver_name, kwargs = kwargs, ip_address = ip_address, role = role, app_type = app_type)

    raise tornado.gen.Return(server)


