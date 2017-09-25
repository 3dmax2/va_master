import json

import salt.client
import tornado.gen
import login, apps

from login import auth_only

def get_paths():
    paths = {
        'get' : {
            'panels' : {'function' : get_panels, 'args' : ['handler']}, 
            'panels/get_panel' : {'function' : get_panel_for_user, 'args' : ['server_name', 'panel', 'provider', 'handler', 'args', 'dash_user']},
        },
        'post' : {
            'panels/get_panel' : {'function' : get_panel_for_user, 'args' : ['server_name', 'panel', 'provider', 'handler', 'args', 'dash_user']},
            'panels/reset_panels': {'function' : reset_panels, 'args' : []}, #JUST FOR TESTING
            'panels/new_panel' : {'function' : new_panel, 'args' : ['panel_name', 'role']},
            'panels/action' : {'function' : panel_action, 'args' : ['server_name', 'action', 'args', 'kwargs', 'module', 'dash_user']}, #must have server_name and action in data, 'args' : []}, ex: panels/action server_name=nino_dir action=list_users
            'panels/chart_data' : {'function' : get_chart_data, 'args' : ['server_name', 'args']},
            'panels/serve_file' : {'function' : salt_serve_file, 'args' : ['handler', 'server_name', 'action', 'args', 'kwargs', 'module']},
            'panels/serve_file_from_url' : {'function' : url_serve_file, 'args' : ['handler', 'server_name', 'url_function', 'module', 'args', 'kwargs']},
        }
    }
    return paths

@tornado.gen.coroutine
def reset_panels(deploy_handler): 
    yield deploy_handler.reset_panels()

@tornado.gen.coroutine
def new_panel(deploy_handler, panel_name, role):
    states = yield deploy_handler.get_states_data()
    panel = {'panel_name' : panel_name, 'role' : role}
    panel.update([x for x in states if x['name'] == role][0]['panels'])
    yield deploy_handler.store_panel(panel)


@tornado.gen.coroutine
def list_panels(deploy_handler, handler): 
    user_group = yield login.get_user_type(handler)

    panels = yield deploy_handler.datastore.get('panels')
    panels = panels[user_group]

    raise tornado.gen.Return(panels)

@tornado.gen.coroutine
def panel_action_execute(deploy_handler, server_name, action, args = [], dash_user = '', kwargs = {}, module = None, timeout = 30):
    if dash_user.get('username'):
        user_funcs = yield deploy_handler.get_user_salt_functions(dash_user['username'])
        if action not in user_funcs and dash_user['type'] != 'admin':
            print ('Function not supported')
            #TODO actually not allow user to do anything. This is just for testing atm. 
        
    server_info = yield apps.get_app_info(deploy_handler, server_name)
    state = server_info['role']

    states = yield deploy_handler.get_states()
    state = [x for x in states if x['name'] == state] or [{'module' : 'openvpn'}]
    state = state[0]

    if not module:
        module = state['module']

    cl = salt.client.LocalClient()
    print ('Calling salt module ', module + '.' + action, ' on ', server_name, ' with args : ', args, ' and kwargs : ', kwargs)
    result = cl.cmd(server_name, module + '.' + action , args, kwarg = kwargs, timeout = timeout)
    result = result.get(server_name)

    raise tornado.gen.Return(result)

@tornado.gen.coroutine
def salt_serve_file(deploy_handler, handler, server_name, action, args = [], dash_user = '', kwargs = {}, module = None):
    server_info = yield apps.get_app_info(deploy_handler, server_name)
    state = server_info['role']

    states = yield deploy_handler.get_states()
    state = [x for x in states if x['name'] == state] or [{'module' : 'openvpn'}]
    state = state[0]

    if not module:
        module = state['module']

    yield handler.serve_file('test', salt_source = {"tgt" : server_name, "fun" : module + '.' + action, "arg" :  args})
    raise tornado.gen.Return({"data_type" : "file"})


#This is just temporary - trying to get backup download working properly. 
@tornado.gen.coroutine
def salt_serve_file_get(deploy_handler, handler, server_name, action, hostname, backupnumber, share, path, module = None):
    server_info = yield apps.get_app_info(deploy_handler, server_name)
    state = server_info['role']

    states = yield deploy_handler.get_states()
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


@tornado.gen.coroutine
def url_serve_file(deploy_handler, handler, server_name, url_function, module = None, args = [], kwargs = {}):
    server_info = yield apps.get_app_info(deploy_handler, server_name)
    state = server_info['role']

    states = yield deploy_handler.get_states()
    state = [x for x in states if x['name'] == state] or [{'module' : 'openvpn'}]
    state = state[0]

    if not module:
        module = state['module']

    cl = salt.client.LocalClient()
    url = cl.cmd(server_name, module + '.' + url_function, arg = args, kwarg = kwargs).get(server_name)

    yield handler.serve_file('test', url_source = url)
    raise tornado.gen.Return({"data_type" : "file"})

@tornado.gen.coroutine
def get_chart_data(deploy_handler, server_name, args = ['va-directory', 'Ping']):
    cl = salt.client.LocalClient()

    result = cl.cmd(server, 'monitoring_stats.parse' , args)
    raise tornado.gen.Return(result)

@tornado.gen.coroutine
def panel_action(deploy_handler, actions_list = [], server_name = '', action = '', args = [], kwargs = {}, module = None, dash_user = {}):
    if not actions_list: 
        actions_list = [{"server_name" : server_name, "action" : action, "args" : args, 'kwargs' : {}, 'module' : module}]

    servers = [x['server_name'] for x in actions_list]
    results = {x : None for x in servers}
    for action in actions_list: 
        server_result = yield panel_action_execute(deploy_handler, action['server_name'], action['action'], action['args'], action['kwargs'], action['module'])
        results[action['server_name']] = server_result

    if len(results.keys()) == 1: 
        results = results[results.keys()[0]]
    raise tornado.gen.Return(results)


@tornado.gen.coroutine
def get_panels(deploy_handler, handler):
    panels = yield list_panels(deploy_handler, handler)
    raise tornado.gen.Return(panels)

@tornado.gen.coroutine
def get_panel_for_user(deploy_handler, handler, panel, server_name, dash_user, args = [], provider = None, kwargs = {}):

    user_panels = yield list_panels(deploy_handler, handler)
    server_info = yield apps.get_app_info(deploy_handler, server_name)
    state = server_info['role']

    #This is usually for get requests. Any arguments in the url that are not arguments of this function are assumed to be keyword arguments for salt. 
    if not args: 
        kwargs = {x : handler.data[x] for x in handler.data if x not in ['handler', 'panel', 'instance_name', 'dash_user', 'method', 'server_name', 'path']}
    else: 
        kwargs = {}

    state = filter(lambda x: x['name'] == state, user_panels)[0]
    if server_name in state['servers']:
        action = 'get_panel'
        if type(args) != list and args: 
            args = [args]
        args = [panel] + args
        panel  = yield panel_action_execute(deploy_handler, server_name, action, args, dash_user, kwargs = kwargs)
        raise tornado.gen.Return(panel)
    else: 
        raise tornado.gen.Return(False)



