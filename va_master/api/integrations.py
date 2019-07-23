import uuid
import tornado.gen

import documentation

def get_paths():
    paths = {
        'get' : {
            'integrations' : {'function' : list_integrations, 'args' : ['datastore_handler']},
#            'triggers/clear' : {'function' : clear_triggers, 'args' : ['provider_name']}, #Just for resting!!!
        },
        'post' : {
            'integrations/add_trigger':  {'function' : add_trigger, 'args' : ['datastore_handler', 'receiver_app', 'donor_app', 'trigger']},
            'integrations/triggered': {'function' : receive_trigger, 'args' : ['handler', 'event_name', 'receiver_app', 'donor_app', 'dash_user']},
#            'triggers/load_triggers' : {'function' : load_triggers, 'args' : ['provider_name', 'triggers']},
#            'triggers/edit_trigger' : {'function' : edit_trigger, 'args' : ['provider_name', 'trigger_id', 'trigger']},
        },
        'delete' : {
#            'triggers/delete_trigger' : {'function' : delete_trigger, 'args' : ['provider_name', 'trigger_id']},
        },
    }
    return paths

#   This is the current form, check below for how this will look. 

# {
#     "new_trigger" : 
#     {
#             "donor_app": "bamboo",
#             "receiver_app": "deputy",
#             "event": {
#                 "name": "bamboo.create_employee",
#                 "data_prefix": "payload.employee"
#             },
#             "conditions": [{
#                 "args_map": {
#                     "DateOfBirth": "bornDate",
#                     "MainAddress": "address1"
#                 },
#                 "func_name": "user_birth_valid"
#             }],
#             "actions": [{
#                 "args_map": {
#                     "FirstName": "firstName",
#                     "LastName": "lastName",
#                     "DisplayName" : "displayName"
#                 },
#                 "func_name": "create_employee"
#             }]
#     }
# }

# So this is getting an overhaul, this is some pseudocode of how it's gonna work and all that jazz. 
# Concept: App A triggers an Event. This Event is part of a Trigger; Each Trigger having an Event, Conditions and Actions. 
# Trigger checks the Conditions, if all of them work, calls all its actions. 


# Creating a Trigger: 
# 1. Select an App
#   - We list Apps via /api/apps
#   ? Do we care _which_ specific server of that type sent a message? 
#     ! For the moment no, any server of the same app activates the same trigger. 
# 2. Select an Event
#   - App functions which are documented and have type: event are listed like this
#   - These functions are documented by definition, ergo have a list of arguments
# 3. Choose Conditions
#   - Skipped for now, but should be used eventually. 
# 4. Chose Actions
#   - Same as Events, except any documented function can be used as an Action. 
#   - And we also have arguments for these. 
#   - This all means we can map arguments to other arguments. 
# 5. ???
# 6. Profit!


# Triggers used to be saved for a specific provider. So for instance, providers/va_clc would have a triggers key, as so - `providers/va_clc: {"provider_name" : "va_clc", ..., "triggers" : [{...}, ...]}. 
# Granted, this was in the old-styled datastore, which we've abandoned since. Anyway, we will now have different keys for all the triggers, as so - `event_triggers/va_bamboo.new_user: {"triggers" : [], "name" : ""}`
# Triggers are triggered based on their event name, so a call at `/api/triggers/event/va_bamboo.add_user` will trigger all Triggers with `va_bamboo.add_user` as their event name. 
# Potentially also maybe have a list of events? 


# In the end, triggers will have a slightly modified structure: 

#   Example trigger: 
#    new_trigger = {
#        "event" : {
#            "name" : "va_bamboo.add_user", 
#            #"provider_name" : "va_clc", # Triggers should now be strong independent entities, see above, but should also probably work somehow with drivers? 
#        }
#        "conditions" : [
#            {
#                "server_name" : "va_deputy", 
#                "module" : "va_deputy_api", 
#                "func" : "user_valid", 
#                "args_map" : {"FirstName" : "firstName", "LastName" : "LastName"}
#            }
#        ],
#        "actions" : [
#            {
#                "server_name" : "va_deputy", 
#                #"module" : "va_deputy_api", #no need to select, since we choose the server, and the server has that type of app. 
#                "func" : "add_user", 
#                "args_map" : {
#                    "FirstName" : "firstName", 
#                    "Lastname" : "lastName", 
#                    "DisplayName" : "displayName",
#                }
#            }
#        ]
#    }
    


# Update: Previous trigger is out, now we have a differnet type of logic. Instead of focusing on triggers or events, we focus on integrations. So an integration is an object consisting of a donor app, receiver app, and a list of triggers. 


#{
#    "donor_app": "va-email",
#    "receiver_app": "va-cloudshare",
#    "events": [{
#            "event_name": "va_email.add_user_recipient",
#            "conditions": [{
#                "func_name": "check_user_legit"
#            }, {
#                "func_name": "check_user_in_ldap"
#            }],
#            "actions": [{
#                "func_name": "add_contact_vcard"
#            }]
#        },
#        {
#            "event_name": "va_email.add_user",
#            "conditions": [{
#                "func_name": "check_user_legit"
#            }, {
#                "func_name": "check_user_not_in_cloudshare"
#            }],
#            "actions": [{
#                "func_name": "add_cloudshare_user"
#            }]
#        }
#    ]
#}



@tornado.gen.coroutine
def add_trigger(datastore_handler, donor_app, receiver_app, trigger):
    integration = yield datastore_handler.get_object('app_integration', donor_app = donor_app, receiver_app = receiver_app)
    integration = integration or {'receiver_app' : receiver_app, 'donor_app' : donor_app, 'triggers' : []}
    trigger['id'] = str(uuid.uuid4()).split('-')[0]
    integration['triggers'].append(trigger)
    yield datastore_handler.insert_object('app_integration', donor_app = donor_app, receiver_app = receiver_app, data = integration)

@tornado.gen.coroutine
def delete_integration(datastore_handler, event_name, integration_id):
    event_integrations = yield datastore.get_objects('event_integrations', event_name = event_name)
    event_integrations = {'integrations' : [x for x in event_integrations['integrations'] if x['id'] != integration_id]}
    yield datastore_handler.insert_object('event_integrations', event_name = event_name, data = event_integrations)


#TODO
@tornado.gen.coroutine
def edit_integration(datastore_handler, provider_name, integration_id, integration):
    """Finds the integration by the id and sets it to the new integration's data. """

    provider = yield datastore_handler.get_provider(provider_name) 

    edited_integration_index = provider['integrations'].index([x for x in provider['integrations'] if x['id'] == integration_id][0])    
    integration['id'] = provider['integrations'][edited_integration_index]['id']
    provider['integrations'][edited_integration_index] = integration

    yield datastore_handler.create_provider(provider)


@tornado.gen.coroutine
def list_integrations(datastore_handler):
    """Returns an object with all providers and their respective integrations. """
    events = yield datastore_handler.datastore.get_recurse('app_integration/')
    raise tornado.gen.Return(events)

@tornado.gen.coroutine
def get_trigger_kwargs_from_data(handler, trigger, request_data, args_map, event_data_prefix = ''):
    print ('Getting ', trigger['event_name'].split('.'))
    print ('Request data is : ', request_data)
    func_group, func_name = trigger['event_name'].split('.')

    print ('Getting ', func_name, func_group)
    event_func = yield documentation.get_function(handler, func_name, func_group)
    print ('Have : ', event_func)
    event_func_prefix = event_func.get('data_prefix', '')
    event_data_prefix =  event_data_prefix or event_func_prefix

    prefix_keys = event_data_prefix.split('.')
    for prefix_key in prefix_keys:
        if prefix_key:
            request_data = request_data.get(prefix_key)
            if not request_data:
                print ('Key ', prefix_key, ' not found in ', request_data)
                raise tornado.gen.Return({})

    #NOTE this line is kinda fishy - if the request data doesn't contain all keys, we just ignore the missing ones. 
    #This was added so that the dashboard calls which send positional arguments don't mess everything up. However, I should think of a better way to handle that. 
    kwargs = {key: request_data.pop(args_map[key]) for key in args_map if request_data.get(args_map[key])}


    #We go through the args_map to see if any argument has a wildcard value.
    #Wildcard arguments just get all the data that hasn't been used up by the regular arguments. 
    wildcard = [x for x in args_map if args_map[x] == '*'] or [None]
    wildcard = wildcard[0]
    if wildcard:
        kwargs[wildcard] = request_data

    if args_map.get('*'):
        kwargs[args_map] = request_data
    print ('FInal kwargs are : ', kwargs)
    raise tornado.gen.Return(kwargs)

@tornado.gen.coroutine
def handle_app_trigger(handler, dash_user, server_name, action):
    print ('Handling ')
    datastore_handler = handler.datastore_handler

    server = yield datastore_handler.get_object('server', server_name = server_name)
    if server.get('role'):
        server_app = yield datastore_handler.get_object('state', name = server['role'])
        if not server_app: 
            server_app = yield datastore_handler.get_object('app', app_name = server['role'])

        module = server_app['module']

        event_name = module + '.' + action
        donor_app = server_app['name']
        integrations = yield handler.datastore.get_recurse('app_integration/%s' % (donor_app, ))
        result = {}
        for integration in integrations:
            app_result = yield receive_trigger(handler, dash_user, donor_app, integration['receiver_app'], event_name)
            result[integration['receiver_app']] = app_result

        raise tornado.gen.Return(result)


@tornado.gen.coroutine
def trigger_all_integrations(handler, dash_user, event_name, donor_app = 'va-master', kwargs = {}):
    integrated_apps = yield handler.datastore_handler.datastore.get_recurse('app_integration/%s' % (donor_app))
    result = {}
    for app in integrated_apps: 
        trigger_result = yield receive_trigger(handler, dash_user, donor_app, app['receiver_app'], event_name, kwargs)
        result[app['receiver_app']] = result

    raise tornado.gen.Return(result)
        


@tornado.gen.coroutine
def receive_trigger(handler, dash_user, donor_app, receiver_app, event_name, kwargs = {}):
    app_integrations = yield handler.datastore_handler.get_object('app_integration', donor_app = donor_app, receiver_app = receiver_app)

#    print ('I AM IN TRIGGER WITH ', app_integrations)
    
    triggers = app_integrations.get('triggers', [])
    results = []
    for trigger in triggers: 
        if trigger['event_name'] == event_name: 
#            print ('Delivering ', event_name, ' because my trigger wanted ', trigger['event_name'])
            all_servers = yield handler.datastore.get_recurse('server/')
            servers_to_call = [x for x in all_servers if x.get('role', '') == receiver_app] 

            conditions_satisfied = True
            for condition in trigger.get('conditions', []): 
                pass #TODO check condition

#            print ('Conditions good. ')
            if conditions_satisfied: 
                for server in servers_to_call:
                    for action in trigger['actions']: 
#                        print ('Action is : ', action)
                        action_kwargs = yield get_trigger_kwargs_from_data(handler, trigger, handler.data, action['args_map'])
#                        print ('Got em : ', kwargs)
                        action_kwargs.update(action.get('extra_args', {}))
                        action_kwargs.update(kwargs)
#                        print ('Calling integration ')
#                        print ('salt ' +  server['server_name'] + ' '  + action['func_name']  + ' ' + str(handler.data.get('args', [])) + ' ' + str(kwargs))
                        new_result = ''

                        #NOTE: This is here to resolve circular imports with panels
                        #This is a pretty bad solution only to temporarily solve a problem, and we should resolve this properly. 
                        #TODO probably write another module (a handler maybe?) dedicated to executing panel actions which will hold panel_action_execute so both panels.py and integrations.py can import it
                        #I don't know what the logical idea behind this module would be, but I'll think of something. 
                        from va_master.api.panels import panel_action_execute
                        new_result = yield panel_action_execute(handler, dash_user = dash_user, server_name = server['server_name'], action = action['func_name'], kwargs = action_kwargs, args = handler.data.get('args', []))
#                        print ('Result : ', new_result)
                        results.append(new_result)

        else:
            print('Expecting ', event_name, ' but receiving : ', trigger['event_name'])


    raise tornado.gen.Return(results)

