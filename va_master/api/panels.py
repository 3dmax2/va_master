import json

import salt.client
import tornado.gen
import login, apps

from login import auth_only

def get_paths():
    paths = {
        'get' : {
            'panels' : get_panels, 
            'panels/get_panel' : get_panel_for_user,
            'panels/ts_data' : get_ts_data,  
        },
        'post' : {
            'panels/reset_panels': reset_panels, #JUST FOR TESTING
            'panels/new_panel' : new_panel, #JUST FOR TESTING
            'panels/action' : panel_action, #must have instance_name and action in data, ex: panels/action instance_name=nino_dir action=list_users
            'panels/chart_data' : get_chart_data,
        }
    }
    return paths

@tornado.gen.coroutine
def reset_panels(handler): 
    yield handler.config.deploy_handler.reset_panels()

@tornado.gen.coroutine
def new_panel(handler):
    states = yield handler.config.deploy_handler.get_states_data()
    panel = {'panel_name' : handler.data['panel_name'], 'role' : handler.data['role']}
    panel.update([x for x in states if x['name'] == handler.data['role']][0]['panels'])
    yield handler.config.deploy_handler.store_panel(panel)


@tornado.gen.coroutine
def list_panels(handler): 
    user_group = yield login.get_user_type(handler)

    panels = yield handler.config.deploy_handler.datastore.get('panels')
#    print ('All panels are : ', panels)
    panels = panels[user_group]
    print ('Panels for : ', user_group, ' are ', panels)

    raise tornado.gen.Return(panels)

@tornado.gen.coroutine
def panel_action_execute(handler):
    try:
        cl = salt.client.LocalClient()

        instance = handler.data['instance_name']
        instance_info = yield apps.get_app_info(handler)
        state = instance_info[instance]['role']
        action = handler.data['action']


        args = handler.data.get('args', [])

        states = yield handler.config.deploy_handler.get_states()
        state = [x for x in states if x['name'] == state][0]

        print ('Getting ', state['module'] + '.' + action, ' with args : ', args, ' for ', instance)
        result = cl.cmd(instance, state['module'] + '.' + action , args)
        print ('My result is : ', result)
    except: 
        import traceback 
        traceback.print_exc()
    raise tornado.gen.Return(result)

@tornado.gen.coroutine
def get_ts_data(handler):
    cl = salt.client.LocalClient()

    result = cl.cmd('va-monitoring.evo.mk', 'monitoring.chart_data')
    raise tornado.gen.Return(result)

@tornado.gen.coroutine
def get_chart_data(handler):
    cl = salt.client.LocalClient()


    instance = handler.data['instance_name']
    print ('instance_name ', instance)


    args = handler.data.get('args', ['va-directory', 'Ping'])

    result = cl.cmd(instance, 'monitoring_stats.parse' , args)
    raise tornado.gen.Return(result)

##@auth_only
@tornado.gen.coroutine
def panel_action(handler):
    instance_result = yield panel_action_execute(handler)
    raise tornado.gen.Return(instance_result)


##@auth_only(user_allowed = True)
@tornado.gen.coroutine
def get_panels(handler):
    panels = yield list_panels(handler)
    raise tornado.gen.Return(panels)


#@auth_only(user_allowed = True)
@tornado.gen.coroutine
def get_panel_for_user(handler):
    panel = handler.data['panel']

    user_panels = yield list_panels(handler)
    instance_info = yield apps.get_app_info(handler)
    instance_info = instance_info[handler.data['instance_name']]
    print ('Instance info is : ', instance_info)
    state = instance_info['role']

    print ('User panels are : ', user_panels)
    print ('Panel is : ', panel, 'and user panels are : ',  user_panels, 'with data : ', handler.data, ' and we are looking for ', state)
    state = filter(lambda x: x['name'] == state, user_panels)[0]
    if handler.data['instance_name'] in state['instances']:
#            panel = panel[0]
        handler.data['action'] = 'get_panel'
        if 'host' in handler.data:
            args = [handler.data['host'], handler.data['service']]
            handler.data['args'] = [panel] + args
        else:
            handler.data['args'] = [panel]
        try: 
            print ('Executing. ')
            panel = yield panel_action_execute(handler)
        except: 
            import traceback
            traceback.print_exc()

        panel = panel[handler.data['instance_name']]
#        print ('My panel is : ', panel)
        raise tornado.gen.Return(panel)
    else: 
        raise tornado.gen.Return({'error' : 'Cannot get panel. '})



