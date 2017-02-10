import json, glob, yaml, datetime
import requests
import subprocess
import traceback
import functools
import tornado
import tornado.gen
from host_drivers import openstack, aws, vcloud, libvirt_driver, generic_driver, century_link


from Crypto.PublicKey import RSA
from concurrent.futures import ProcessPoolExecutor


class DeployHandler(object):
    def __init__(self, datastore, deploy_pool_count, ssh_key_name, ssh_key_path):
        self.ssh_key_name = ssh_key_name
        self.ssh_key_path = ssh_key_path
        self.datastore = datastore
        self.drivers = []

        self.deploy_pool_count = deploy_pool_count
        self.pool = ProcessPoolExecutor(deploy_pool_count)
        

    @tornado.gen.coroutine
    def init_vals(self, store, **kwargs):
        init_vars = {
            'va_flavours' : 'va_flavours', 
        }
        try: 
            store_values = yield self.datastore.get('init_vals')
        except:
            store_values = {}
            print ('No store values found - probably initializing deploy_handler for the first time. Will initialize with cli arguments. ')

        for var in init_vars: 
            if var in kwargs: 
                setattr(self, var, kwargs[var])
            else: 
                if var in store_values: 
                    setattr(self, var, store_values[var])
                else:
                    print ("Variable '%s' defined neither in store nor in arguments and will not be set in deploy handler. This may result with further errors. " % (var))


    def start(self):
        pass

    @tornado.gen.coroutine
    def create_ssh_keypair(self):
        pass

    @tornado.gen.coroutine
    def get_ssh_keypair(self):
        try:
            keydata = self.datastore.get('ssh_keypair')
        except self.datastore.KeyNotFound:
            # create new
            data = yield self.create_ssh_keypair()
            yield self.datastore.insert('ssh_keypair', data)
            raise tornado.gen.Return(data)
        raise tornado.gen.Return({'public': keydata['public'],
            'private': keydata['private']})

    @tornado.gen.coroutine
    def get_drivers(self):
        if not self.drivers: 
            init_vals = yield self.datastore.get('init_vals')
            host_ip =  init_vals['ip'] 
            va_flavours = init_vals['va_flavours']

            kwargs = {
                'host_ip' : host_ip, 
                'key_name' : self.ssh_key_name, 
                'key_path' : self.ssh_key_path, 
            }


            self.drivers = [x(**kwargs) for x in [
                openstack.OpenStackDriver, 
                generic_driver.GenericDriver,
            ]]

            #Libvirt also needs these kwargs. 

            kwargs['flavours'] =  self.va_flavours

            self.drivers += [x(**kwargs) for x in (century_link.CenturyLinkDriver, libvirt_driver.LibVirtDriver)]

        raise tornado.gen.Return(self.drivers)

    @tornado.gen.coroutine
    def get_driver_by_id(self, id_):
        drivers = yield self.get_drivers()
        for driver in drivers:
            driver_id = yield driver.driver_id()
            if driver_id == id_:
                raise tornado.gen.Return(driver)
        raise tornado.gen.Return(None)

    @tornado.gen.coroutine
    def list_hosts(self):
        try:
            hosts = yield self.datastore.get('hosts')
            for host in hosts: 
                driver = yield self.get_driver_by_id(host['driver_name'])
                host_status = yield driver.get_host_status(host)
                host['status'] = host_status
        except self.datastore.KeyNotFound:
            print ('No hosts found. ')
            hosts = []
        raise tornado.gen.Return(hosts)

    @tornado.gen.coroutine
    def create_host(self, driver):
        try:
            new_hosts = yield self.datastore.get('hosts')
        except self.datastore.KeyNotFound:
            new_hosts = []
        try: 
            new_hosts.append(driver.field_values)
            yield self.datastore.insert('hosts', new_hosts)
        except: 
            import traceback
            traceback.print_exc()

    @tornado.gen.coroutine
    def get_states_data(self, states = []):
        states_data = []
        subdirs = glob.glob('/srv/salt/*')
        for state in subdirs:
            try: 
                with open(state + '/appinfo.json') as f: 
                    print ('Opening ', state)
                    states_data.append(json.loads(f.read()))
            except IOError as e: 
                print (state, ' does not have an appinfo file, skipping. ')
            except: 
                print ('error with ', state)
                import traceback
                traceback.print_exc()
        if states: 
            states_data = [x for x in states_data if x['name'] in states]
        try: 
            panels = yield self.datastore.get('panels')
        except: 
            user_panels, admin_panels = ([{'name' : x['name'], 'icon' : x['icon'], 'instances' : [], 'panels' : x.get('panels', {'admin' : [], 'user' : []}[type])} for x in states_data] for type in ['user', 'admin'])
            panels = {'user' : user_panels, 'admin' : admin_panels}
            yield self.datastore.insert('panels', panels)
        raise tornado.gen.Return(states_data)


    @tornado.gen.coroutine
    def get_states(self):
        try: 
            states_data = yield self.datastore.get('states')
        except self.datastore.KeyNotFound:
            states_data = yield self.get_states_data()
            yield self.datastore.insert('states', states_data)
        except: 
            import traceback
            traceback.print_exc()
        raise tornado.gen.Return(states_data)
    

    @tornado.gen.coroutine
    def reset_states(self):
        try: 
            yield self.datastore.delete('states')
            states_data = yield self.get_states_data()
            yield self.datastore.insert('states', states_data)
        except: 
            import traceback
            traceback.print_exc()


    def delete_panel(self, panel_name): 
        try: 
            panels = yield self.datastore.get('panels')
            del panels['user'][panel_name]
            del panels['admin'][panel_name]
            yield self.datastore.insert('panels', panels)
        except: 
            import traceback
            traceback.print_exc()


    @tornado.gen.coroutine
    def store_panel(self, panel):
        try: 
            panels = yield self.datastore.get('panels')

            
            role_user_panels = filter(lambda x: x['name'] == panel['role'], panels['user'])[0]
            if panel['panel_name'] in role_user_panels['instances']: raise tornado.gen.Return()

            role_user_panels['instances'].append(panel['panel_name'])

            role_admin_panels = filter(lambda x: x['name'] == panel['role'], panels['admin'])[0]
            role_admin_panels['instances'].append(panel['panel_name'])

#            panels['user'][panel['role']] = role_user_panels
#            panels['admin'][panel['role']] = role_admin_panels
            print ('New panels are : ', panels)
            yield self.datastore.insert('panels', panels)
        except: 
            import traceback
            traceback.print_exc()


    @tornado.gen.coroutine
    def reset_panels(self):
        try: 
            yield self.datastore.delete('panels')
        except: 
            import traceback
            traceback.print_exc()


    @tornado.gen.coroutine
    def store_app(self, app, host):
        try: 
            hosts = yield self.datastore.get('hosts')
            host = [h for h in hosts if h['hostname'] == host][0]
            host['instances'].append(app)
            yield self.datastore.insert('hosts', host)
        except: 
            import traceback
            traceback.print_exc()

    @tornado.gen.coroutine
    def generate_top_sls(self):
        states = yield self.datastore.get('states')
        with open('/srv/salt/top.sls.base') as f: 
            current_top_sls = yaml.load(f.read())

        for state in states:
            print ('Adding state : ', state['name'])
            current_top_sls['base']['role:' + state['name']] = [{'match' : 'grain'}] + state['substates']
        try: 
            with open('/srv/salt/top.sls.tmp', 'w') as f:
                f.write(yaml.safe_dump(current_top_sls))
        except: 
            import traceback
            traceback.print_exc()


    @tornado.gen.coroutine
    def store_action(self, user, path, data):
        try: 
            actions = yield self.datastore.get('actions')
        except: 
            actions = []
        actions.append({
            'username' : user['username'], 
            'type' : user['type'], 
            'path' : path, 
            'data' : str(data), 
            'time' : str(datetime.datetime.now())
        })
        yield self.datastore.insert('actions', actions)

    @tornado.gen.coroutine
    def get_actions(self, number_actions, filters = {}):
        all_actions = yield self.datastore.get('actions')
        actions = all_actions[:number_actions] if number_actions else all_actions
        raise tornado.gen.Return(all_actions[:number_actions])


