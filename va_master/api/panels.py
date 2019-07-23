import json, yaml, subprocess, importlib, inspect, socket

import salt.client
import tornado.gen
import login, apps, services

from login import auth_only, create_user_api
from va_master.handlers.app_handler import handle_app_action
from salt.client import LocalClient 

def get_paths():
    paths = {
        'get' : {
            'panels' : {'function' : list_panels, 'args' : ['datastore_handler', 'dash_user']}, 
            'panels/stats' : {'function' : get_panels_stats, 'args' : ['handler', 'dash_user']},
            'panels/get_panel' : {'function' : get_panel_for_user, 'args' : ['handler', 'server_name', 'panel', 'provider', 'args', 'dash_user']},
            'panels/get_services_and_logs' : {'function' : get_services_and_logs, 'args' : ['datastore_handler']},
        },
        'post' : {
            'panels/sync_salt_minions' : {'function' : sync_salt_minions, 'args' : ['datastore_handler', 'dash_user']},
            'panels/remove_orphaned_servers' : {'function' : remove_orphaned_servers, 'args' : ['datastore_handler']},

            'panels/get_panel' : {'function' : get_panel_for_user, 'args' : ['server_name', 'panel', 'provider', 'handler', 'args', 'dash_user']},
            'panels/new_panel' : {'function' : new_panel, 'args' : ['datastore_handler', 'server_name', 'role']},
            'panels/remove_panel' : {'function' : remove_panel, 'args' : ['datastore_handler', 'server_name', 'role', 'dash_user']},

            'panels/action' : {'function' : panel_action, 'args' : ['handler', 'server_name', 'action', 'args', 'kwargs', 'module', 'dash_user']}, #must have server_name and action in data, 'args' : []}, ex: panels/action server_name=nino_dir action=list_users
            'panels/chart_data' : {'function' : get_chart_data, 'args' : ['server_name', 'args']},
            'panels/serve_file' : {'function' : salt_serve_file, 'args' : ['handler', 'server_name', 'action', 'args', 'kwargs', 'module']},
            'panels/serve_file_from_url' : {'function' : url_serve_file, 'args' : ['handler', 'server_name', 'url_function', 'module', 'args', 'kwargs']},
            'panels/get_panel_pdf' : {'function' : get_panel_pdf, 'args' : ['server_name', 'panel', 'pdf_file', 'provider', 'handler', 'args', 'kwargs', 'dash_user', 'filter_field']},
            'panels/export_table' : {'function' : export_table, 'args' : ['handler', 'panel', 'server_name', 'dash_user', 'export_type', 'table_file', 'args', 'provider', 'kwargs', 'filter_field']}
        }
    }
    return paths


def get_minion_role(minion_name = '*'):
    cl = LocalClient()
    role = cl.cmd(minion_name, 'grains.get', arg = ['role'])
    if minion_name != '*': 
        role = role[minion_name]
    return role


@tornado.gen.coroutine
def new_panel(datastore_handler, server_name, role):
    """ 
        description: Adds a new panel for a server to the datastore. The server needs to use a role (salt or custom) which has been added to the datastore. Refer to the apps documentation for how to use apps and panels. Typically called by other functions but may be enabled, mostly for testing or external apps. 
        arguments: 
          - server_name: The server for which the panels will be added, for instance server_name=va-directory
          - role: The role which defines the panels, for instance role=directory. This role should have an appinfo.json file, and be added to the datastore previously. Refer to the apps documentation. 
    """

    yield datastore_handler.add_panel(server_name, role)


@tornado.gen.coroutine
def remove_orphaned_servers(datastore_handler):
    """
        description: Removes servers with providers that no longer exist. This would typically happen during testing or deployment. 
    """
    servers = yield datastore_handler.datastore.get_recurse('server/')
    providers = yield datastore_handler.datastore.get_recurse('providers/')
    providers = [x['provider_name'] for x in providers]

    for server in servers: 
        if server.get('provider_name', '') not in providers: 
            print ('Server ', server['server_name'], ' has : ', server.get('provider_name'), ' not in ', providers, ' deleting. ')
            yield datastore_handler.delete_object(object_type = 'server', server_name = server['server_name'])

@tornado.gen.coroutine
def sync_salt_minions(datastore_handler, dash_user):
    """
        description: Adds panels for existing salt minions where panels haven't been added yet, and removes panels for servers which have been deleted externally. Also typically happens during testing or deploymend. 
        output: A list of unresponsive minions.
    """
    minions = get_minion_role('*')
    unresponsive_minions = []
    for user_type in ['user', 'admin']: 
        for minion in minions: 
            panel_type = user_type + '_panel'
            panel = yield datastore_handler.get_object(object_type = panel_type, name = minions[minion])

            if not panel: 
                print ('No panel for ', minion, minions[minion])
                continue

            if not minions[minion]: 
                unresponsive_minions.append([minion, minions[minion]])
                continue

            print ('Panel : ', panel, ' for ', minions[minion])
            if minion not in panel['servers']: 
                print ('Panel servers are : ', panel['servers'], ' and adding ', minion)
                panel['servers'].append(minion)
            yield datastore_handler.insert_object(object_type = panel_type, name = minions[minion], data = panel)

        panels = yield datastore_handler.list_panels(user_type)
        print ('Now clearing panels')
        for panel in panels: 
            panel_type = user_type + '_panel'

            for server in panel['servers']:
                server_role = minions.get(server, '')

                if server not in minions or server_role != panel['name']: 
                    print (server, ' not in ', minions, ' so removing it. ')
                    panel['servers'] = [x for x in panel['servers'] if x != server]
            yield datastore_handler.insert_object(object_type = panel_type, name = panel['name'], data = panel)


    if unresponsive_minions: 
        raise tornado.gen.Return({'success' : True, 'message' : 'There were unresponsive minions. ', 'data' : unresponsive_minions})
    else: 
        raise tornado.gen.Return({'success' : True, 'message' : '', 'data' : {}})

@tornado.gen.coroutine
def remove_panel(datastore_handler, server_name, dash_user, role = None):
    server_role = role or get_minion_role(server_name)
    panel_type = dash_user['type'] + '_panel'
    panel = yield datastore_handler.get_object(object_type = panel_type, name = server_role)
    panel['servers'] = [x for x in panel['servers'] if x != server_name]
    panels = yield datastore_handler.insert_object(object_type = panel_type, name = server_role, data = panel)

@tornado.gen.coroutine
def list_panels(datastore_handler, dash_user):
    """ 
        description: Returns a list of the panels for the logged in user. Panels are retrieved from the panels/<user_type>/<role> key in the datastore, with user_type being user/admin and is retrieved from the auth token, and role being one of the apps added to the datastore. See the apps documentation for more info. 
        output: '[{"servers": [], "panels": [{"name": "User-friendly name", "key": "module.panel_name"}], "name": "role_name", "icon": "fa-icon"}]'
        visible: True
    """

    panels = yield datastore_handler.get_panels(dash_user['type'])

    raise tornado.gen.Return(panels)

@tornado.gen.coroutine
def panel_action_execute(handler, server_name, action, args = [], dash_user = {}, kwargs = {}, module = None, timeout = 30):
    """ 
        description: Executes the function from the action key on the minion specified by server_name by passing the args and kwargs. If module is not passed, looks up the panels and retrieves the module from there. 
        output: Whatever the action returns. 
        arguments: 
          - name: server_name
            description: The server where the action will be called. 
            type: string
            req: True
            example: va-server
          - name: action
            derscription: The action to call on the server. 
            type: string
            req: True
            example: my_action
          - name: args
            description: A list of arguments to call the action with
            req: False
            default: []
            example: ['arg1', 'arg2']
          - name: kwargs
            description: A dictionary of keyword arguments to pass to the action. 
            type: dict
            req: False
            default: {}
            example: {'key1' : 'val1', 'key2' : 'val2'}
          - name: module
            description: The module with which the function will be called. 
            type: string
            req: False
            default: Whatever the module is for the server role in the datastore. 
            example: "If we have a server at server/va-server: {'role': 'directory', ...}, we take the module from the directory app. "
    """
    datastore_handler = handler.datastore_handler

    server = yield datastore_handler.get_object(object_type = 'server', server_name = server_name)

    if server.get('app_type', 'salt') == 'salt': 

        if dash_user.get('username'):
            user_funcs = [x['func_path'] for x in dash_user['functions']]
#            user_funcs = yield datastore_handler.get_user_salt_functions(dash_user['username'])
            if action not in user_funcs and dash_user['type'] != 'admin':
                print ('Function not supported', action)
                raise Exception('User attempting to execute a salt function but does not have permission. ')

        if not module:
            print ('Getting role for ', server_name)
            state = get_minion_role(server_name) 

            state = yield datastore_handler.get_state(name = state)
            if not state: state = {'module' : 'openvpn'}
            module = state['module']

        cl = salt.client.LocalClient()
        result = cl.cmd(server_name, module + '.' + action , arg = args, kwarg = kwargs, timeout = timeout)
        
        result = result.get(server_name)
    #        raise Exception('Calling %s on %s returned an error. ' % (module + '.' + action, server_name))

    else: 
        result = yield handle_app_action(handler, server, action, args, kwargs)

    #This is very finicky design. We import the function here to resolve circular imports with integrations (see TODO there as well)
    #TODO find a way to properly resolve this, probably by writing another module somewhere somehow. 
    from integrations import handle_app_trigger

    yield handle_app_trigger(handler, dash_user, server_name, action)

    raise tornado.gen.Return(result)

@tornado.gen.coroutine
def salt_serve_file(handler, server_name, action, args = [], dash_user = '', kwargs = {}, module = None):
    """Serves a file by using a salt module. The module function but be able to be called with range_from and range_to arguments. """
    datastore_handler = handler.datastore_handler
    server_info = yield apps.get_app_info(server_name)
    state = server_info['role']

    states = yield datastore_handler.get_states_and_apps()
    state = [x for x in states if x['name'] == state] or [{'module' : 'openvpn'}]
    state = state[0]

    if not module:
        module = state['module']

    yield handler.serve_file('test', salt_source = {"tgt" : server_name, "fun" : module + '.' + action, "arg" :  args})
    raise tornado.gen.Return({"data_type" : "file"})


#This is just temporary - trying to get backup download working properly. 
@tornado.gen.coroutine
def salt_serve_file_get(handler, server_name, action, hostname, backupnumber, share, path, module = None):
    datastore_handler = handler.datastore_handler
    server_info = yield apps.get_app_info(server_name)
    state = server_info['role']

    states = yield datastore_handler.get_states_and_apps()
    state = [x for x in states if x['name'] == state] or [{'module' : 'openvpn'}]
    state = state[0]

    if not module:
        module = state['module']

    kwargs = {
        'hostname' : hostname, 
        'backupnumber' : backupnumber, 
        'share' : share, 
        'path' : path, 
        'range_from' : 0,
    }

    yield handler.serve_file('test', salt_source = {"tgt" : server_name, "fun" : module + '.' + action, "kwarg" : kwargs})
    raise tornado.gen.Return({"data_type" : "file"})

    if not module:
        module = state['module']

    yield handler.serve_file('test', salt_source = {"tgt" : server_name, "fun" : module + '.' + action, "arg" :  args})
    raise tornado.gen.Return({"data_type" : "file"})


#This is just temporary - trying to get backup download working properly. 
@tornado.gen.coroutine
def url_serve_file(handler, server_name, url_function, module = None, args = [], kwargs = {}):
    """Serves a file by utilizing a url. The server must have a function which returns the url. This will call that function with the supplied args and kwargs. """
    datastore_handler = handler.datastore_handler
    server_info = yield apps.get_app_info(server_name)
    state = server_info['role']

    states = yield datastore_handler.get_states_and_apps()
    state = [x for x in states if x['name'] == state] or [{'module' : 'openvpn'}]
    state = state[0]

    if not module:
        module = state['module']

    cl = salt.client.LocalClient()
    url = cl.cmd(server_name, module + '.' + url_function, arg = args, kwarg = kwargs).get(server_name)

    yield handler.serve_file('test', url_source = url)
    raise tornado.gen.Return({"data_type" : "file"})

@tornado.gen.coroutine
def get_chart_data(server_name, args = ['va-directory', 'Ping']):
    """Gets chart data for the specified server."""
    cl = salt.client.LocalClient()

    result = cl.cmd(server_name, 'monitoring_stats.parse' , args)
    raise tornado.gen.Return(result)

@tornado.gen.coroutine
def panel_action(handler, actions_list = [], server_name = '', action = '', args = [], kwargs = {}, module = None, dash_user = {}, call_functions = []):
    """
        description: Performs a list of actions on multiple servers. If actions_list is not supplied, will use the rest of the arguments to call a single function on one server.
        output: Whatever the actions return. If calling multiple actions on multiple servers, the results are filtetred by server. 
        visible: True
        arguments: 
          - name: actions_list
            description: A list of actions to be taken. Each action should have the same arguments as the base functions. If the other arguments are empty, then this argument must have at least one value. 
            req: False
            type: list
            default: []
            example: '[{"server_name" : "va-server", "action" : "list_users", "args" : ["some", "list"], "kwargs" : {"some_key" : "some_val"}, "module" : ""}]'
          - name: server_name
            description: The server on which the specified action will be called. If empty, then actions_list must have at least one action in it. 
            req: False
            type: string
            default: ""
            example: va-server
          - name: action
            description: The action which will be called on the server. If empty, then actions_list must have at least one action in it. 
            req: False
            type: string
            default: ""
            example: list_users
          - name: args
            description: A list of arguments to pass to the action
            req: False
            type: list
            default: []
          - name: kwargs
            description: A dictionary of key-pair values to pass to the action. 
            req: False
            type: dict
            default: {}
          - name: module
            description: The module to call the actions on. If empty, the module is retrieved from the role of the server. 
            req: False
            type: string
            default: Taken from the role of the server
            example: va_utils
    """
    #NOTE temporary fix for a bug - some forms return action as a list of one value, for example ['add_multiple_user_recipients'], where it should just be a string. 
    if type(action) == list: 
        if len(action) == 1: 
            action = action[0]

    if not actions_list: 
        actions_list = [{"server_name" : server_name, "action" : action, "args" : args, 'kwargs' : kwargs, 'module' : module}]

    servers = [x['server_name'] for x in actions_list]
    results = {x : None for x in servers}
    for action in actions_list:
        server_key = action['server_name']
        server_result = yield panel_action_execute(handler, server_name = action['server_name'], \
            dash_user = dash_user, \
            action = action['action'], \
            args = action['args'], \
            kwargs = action['kwargs'], \
            module = action['module'])
        results[server_key] = server_result

        #call_functions is a list of functions to call at the end of the action. Usually used with actions such as va_directory.add_user, which then wants to get the data of list_users
        if call_functions: 
            results[server_key] = {}
            for f in call_functions: 
                new_result = yield panel_action_execute(handler, server_name = action['server_name'], dash_user = dash_user, action = f['action'], module = action['module'])[server_key]
                results[server_key][f['table_name']] = new_result

    if len(results.keys()) == 1: 
        results = results[results.keys()[0]]
    raise tornado.gen.Return(results)



@tornado.gen.coroutine
def get_services_and_logs(datastore_handler):
    logfile = '/var/log/vapourapps/va-master.log'
    with open(logfile) as f:
        logs = f.read().split('\n')

    serv = yield services.get_all_checks()
    passing_services, crit_services, warn_services = 0, 0, 0
    info_logs, critical_logs = 0, 0

    info_severities = ['info', 'notices', 'debug', 'warning']
    crit_severities = ['err', 'crit', 'alert', 'emerg']

    for service in serv: 
        for check in serv[service]: 
            if check.get('Status', '') in ['passing']: 
                passing_services += 1
            elif check.get('Status', '') in ['critical']: 
                crit_services += 1
            elif check.get('Status') in ['warning']: 
                warn_services += 1

    for log in logs: 
        if not log: continue
        try:
            log = json.loads(log)
        except: 
            continue
        if log['severity'] in info_severities: 
            info_logs += 1
        elif log['severity'] in crit_severities: 
            critical_logs += 1

    warning_logs = 10

    raise tornado.gen.Return({"critical_logs" : critical_logs, "info_logs" : info_logs, "warning_logs" : warning_logs, "passing_services" : passing_services, "critical_services" : crit_services, "warning_services" : warn_services})


@tornado.gen.coroutine
def get_panels_stats(handler, dash_user):
    """
        description: Gets various stats for the panels that are shown on next to the name of every va-master panel. 
        output: {"providers" : 10, "servers" : 10, "services" : 10, "vpn" : 10, "apps" : 10}
    """ 
        
    datastore_handler = handler.datastore_handler
    providers = yield datastore_handler.list_providers()
    providers = [x for x in providers if x['provider_name'] != 'va_standalone_servers']
    servers = yield datastore_handler.datastore.get_recurse('server/')
    serv = yield services.list_services()
    serv = len(serv) - 1 #One service is the default consul one, which we don't want to be counted
#    vpn = yield apps.get_openvpn_users()
    vpn = {'users' : []}
    states = yield apps.get_states(handler, dash_user)
    
    integrations = yield handler.datastore_handler.datastore.get_recurse('app_integration/')

    result = {'providers' : len(providers), 'servers' : len(servers), 'services' : serv, 'vpn' : len(vpn['users']), 'apps' : len(states), "integrations" : len(integrations)}
    raise tornado.gen.Return(result)

@tornado.gen.coroutine
def get_panel_for_user(handler, panel, server_name, dash_user, args = [], kwargs = {}):
    """
        description: Returns the required panel from the server for the logged in user. This is done by calling module.get_panel, if that module has a defined get_panel function, otherwise from va_utils.get_panel. 
        output: TODO
        visible: True
        arguments: 
          - name: panel
            description: The name of the panel to show the user
            req: True
            type: string
            example: directory.list_users
          - name: server_name
            description: The name of the server which will return the panel
            req: True
            type: string
            example: va-directory
          - name: args
            description: Any arguments which might be sent to the panel
            req: False
            default: []
          - name: kwargs
            description: Any key-value arguments which might be sent to the panel
            req: False
            default: {}
    """

    datastore_handler = handler.datastore_handler
    user_panels = yield list_panels(datastore_handler, dash_user)
    #This is usually for get requests. Any arguments in the url that are not arguments of this function are assumed to be keyword arguments for salt.
    #TODO Also this is pretty shabby, and I need to find a better way to make GET salt requests work. 
    ignored_kwargs = ['datastore', 'handler', 'datastore_handler', 'drivers_handler', 'panel', 'instance_name', 'dash_user', 'method', 'server_name', 'path', 'args']
    if not kwargs: 
        kwargs = {x : handler.data[x] for x in handler.data if x not in ignored_kwargs}

    action = 'get_panel'
    if type(args) != list and args: 
        args = [args]
    args = [panel] + args
    
    server = yield datastore_handler.get_object(object_type = 'server', server_name = server_name)
    if server.get('app_type', 'salt') == 'salt':
        state = get_minion_role(server_name) 
        state = yield datastore_handler.get_state(name = state)
        args = [state['module']] + args

    panel  = yield panel_action_execute(handler, server_name, action, args, dash_user, kwargs = kwargs, module = 'va_utils')
    raise tornado.gen.Return(panel)

@tornado.gen.coroutine
def export_table(handler, panel, server_name, dash_user, export_type = 'pdf', table_file = '/tmp/table', args = [], provider = None, kwargs = {}, filter_field = ''):
    table_func = 'va_utils.get_%s' % export_type
    table_file = table_file + '.' + export_type
    if not args: 
        args = list(args)
    cl = LocalClient()
    panel = yield get_panel_for_user(handler = handler, panel = panel, server_name = server_name, dash_user = dash_user, args = args, provider = provider, kwargs = kwargs)
    print ('Getting ', export_type, '  with filter : ', filter_field)
    result = cl.cmd('G@role:va-master', fun = table_func, tgt_type = 'compound', kwarg = {'panel' : panel, 'table_file' : table_file, 'filter_field' : filter_field})
    yield handler.serve_file(table_file)


@tornado.gen.coroutine
def get_panel_pdf(handler, panel, server_name, dash_user, pdf_file = '/tmp/table.pdf', args = [], provider = None, kwargs = {}, filter_field = ''):
    if not args: 
        args = list(args)
    cl = LocalClient()
    panel = yield get_panel_for_user(handler = handler, panel = panel, server_name = server_name, dash_user = dash_user, args = args, provider = provider, kwargs = kwargs)
    result = cl.cmd('va-master', 'va_utils.get_pdf', kwarg = {'panel' : panel, 'pdf_file' : pdf_file, 'filter_field' : filter_field})
    if not result['va-master']: 
        yield handler.serve_file(pdf_file)
        raise tornado.gen.Return({'data_type' : 'file'})
    raise Exception('PDF returned a value - probably because of an error. ')

