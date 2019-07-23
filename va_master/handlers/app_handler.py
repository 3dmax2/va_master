import tornado, sys, subprocess, importlib


@tornado.gen.coroutine
def install_new_app(datastore_handler, app_json, path_to_app):
    success = yield install_app_package(path_to_app)
    if success: 
        yield add_app_to_store(datastore_handler, app_json)

@tornado.gen.coroutine
def remove_app(datastore_handler, app_name):
    success = yield uninstall_app_package(app_name)
    if success: 
        yield remove_app_from_store(datastore_handler, app_name)

@tornado.gen.coroutine
def change_app_type(datastore_handler, app_name, app_type):
    server = yield datastore_handler.get_object(object_type = 'server', server_name = app_name)
    server['type'] = 'app'
    server['app_type'] = app_type

    yield datastore_handler.insert_object(object_type = 'server', server_name = app_name, data = server)

@tornado.gen.coroutine
def add_app_to_store(datastore_handler, app_json):
    yield datastore_handler.insert_object(object_type = 'app', app_name = app_json['name'], data = app_json)
    empty_panel = {'admin' : [], 'user' : []}
   
    for user_type in ['user', 'admin']: 
        panel_type = user_type + '_panel'
        panel = yield datastore_handler.get_object(object_type = panel_type, name = app_json['name'])

        servers = []
        if panel: 
            servers = panel['servers']
 
        panel = {
            'name' : app_json['name'],
            'icon' : app_json['icon'],
            'servers' : servers,
            'panels' : app_json.get('panels', empty_panel)[user_type]
        }
        yield datastore_handler.store_panel(panel, user_type)

@tornado.gen.coroutine
def remove_app_from_store(datastore_handler, app_name):
    yield datastore_handler.datastore.delete(app_name)

@tornado.gen.coroutine
def install_app_package(path_to_app):
    print ('Path : ', path_to_app)
    result = yield handle_app_package(path_to_app, 'install')
    raise tornado.gen.Return(result)

@tornado.gen.coroutine
def remove_app_package(path_to_app):
    result = yield handle_app_package(path_to_app, 'uninstall')
    raise tornado.gen.Return(result)

#After consulting several forum/SE threads, this is the prefered way to install pip packages.
#Evidently, pip.main has been moved to an internal command and is unsafe.
@tornado.gen.coroutine
def handle_app_package(path_to_app, action = 'install'):
    if action not in ['install', 'uninstall']:
        raise Exception('Attempted to handle app package with action: ' + str(action))

    print ('App is : ', path_to_app)
    install_cmd = [sys.executable, '-m', 'pip', 'install', path_to_app, '--upgrade']
    print ('Installing with : ', subprocess.list2cmdline(install_cmd))
    try:
        subprocess.call(install_cmd)
    except:
        raise tornado.gen.Return(False)

    raise tornado.gen.Return(True)


@tornado.gen.coroutine
def handle_app_action(handler, server, action, args, kwargs):
    datastore_handler = handler.datastore_handler
    kwargs.update(handler.data)
    app = yield datastore_handler.get_object('app', app_name = server['role'])
    app_action = app['functions'][action]
    app_args = {}
    for arg in app_action.get('args', []):
        app_args[arg] = server.get(arg) or kwargs.get(arg)

    app_module = app['module']
    app_module = importlib.import_module(app_module)
    print ('Sending ', app_args)
    result = getattr(app_module, action)(**app_args)
    raise tornado.gen.Return(result)
