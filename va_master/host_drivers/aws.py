from . import base
from .base import Step, StepResult
from tornado.httpclient import AsyncHTTPClient, HTTPRequest
import tornado.gen
import json
from va_master import datastore

import subprocess

PROVIDER_TEMPLATE = '''VAR_PROVIDER_NAME:
  id: VAR_APP_ID
  key: VAR_APP_KEY
  keyname: VAR_KEYNAME
  private_key: VAR_PRIVATE_KEY
  driver: ec2

  minion:
    master: VAR_THIS_IP
    master_type: str

  grains: 
    node_type: broker
    release: 1.0.1

  # The name of the configuration profile to use on said minion
  #ubuntu if deploying on ubuntu
  ssh_username: ec2-user
  ssh_interface: private_ips

#  These are optional
  location: VAR_REGION
#  availability_zone: VAR_AVAILABILITY_ZONE
'''


PROFILE_TEMPLATE = '''VAR_PROFILE_NAME:
    provider: VAR_PROVIDER_NAME
    image: VAR_IMAGE
    size: VAR_SIZE
    securitygroup: VAR_SEC_GROUP'''


AWS_CONFIG_TEMPLATE = '''[profile VAR_PROVIDER_NAME]
aws_access_key_id=VAR_APP_ID
aws_secret_access_key=VAR_APP_KEY
region=VAR_REGION
output=json
'''

class AWSDriver(base.DriverBase):

    def __init__(self, key_path = '/etc/salt/', key_name = '', provider_name = 'aws_provider', profile_name = 'aws_instance', host_ip = '192.168.80.39'):
        if not key_name: 
            #probably use uuid instead
            key_name = 'aws_key_name'
        self.key_path = key_path + ('/' * (not key_path[-1] == '/')) + key_name
        self.key_name = key_name

        self.datastore = datastore.ConsulStore()
        self.datastore.insert('sec_groups', ['default'])

        self.regions = ['ap-northeast-1', 'ap-southeast-1', 'ap-southeast-2', 'eu-west-1', 'sa-east-1', 'us-east-1', 'us-west-1', 'us-west-2']

        provider_vars = {'VAR_THIS_IP' : host_ip, 'VAR_PROVIDER_NAME' : provider_name, 'VAR_KEYNAME' : key_name, 'VAR_PRIVATE_KEY' : self.key_path}

        profile_vars = {'VAR_PROVIDER_NAME' : provider_name, 'VAR_PROFILE_NAME' : profile_name}
        super(AWSDriver, self).__init__(PROVIDER_TEMPLATE, PROFILE_TEMPLATE, provider_vars = provider_vars, profile_vars = profile_vars)
        self.aws_config = AWS_CONFIG_TEMPLATE

    @tornado.gen.coroutine
    def driver_id(self):
        raise tornado.gen.Return('aws')

    @tornado.gen.coroutine
    def friendly_name(self):
        raise tornado.gen.Return('AWS')

    @tornado.gen.coroutine
    def new_host_step_descriptions(self):
        raise tornado.gen.Return([
            {'name': 'Host Info'},
            {'name': 'Security'}
        ])

    @tornado.gen.coroutine
    def get_salt_configs(self):
        yield super(AWSDriver, self).get_salt_configs()
        for var_name in self.provider_vars: 
            self.aws_config = self.aws_config.replace(var_name, self.provider_vars[var_name])
        self.provider_name = self.provider_vars['VAR_PROVIDER_NAME']
        self.profile_name = self.profile_vars['VAR_PROFILE_NAME']

        with open('/etc/salt/cloud.providers.d/' + self.provider_name, 'w') as f: 
            f.write(self.provider_template)
        with open('/etc/salt/cloud.profiles.d/' + self.profile_name, 'w') as f: 
            f.write(self.profile_template)
        with open('/root/.aws/config', 'w') as f: 
            f.write(self.aws_config)

        raise tornado.gen.Return((self.provider_template, self.profile_template))

    @tornado.gen.coroutine
    def get_steps(self):
        host_info = Step('Host info')
        host_info.add_field('app_id', 'Application ID', type = 'str')
        host_info.add_field('app_key', 'Application Key', type = 'str')

        net_sec = Step('Region & security group')
        net_sec.add_field('netsec_desc', 'Current connection info', type = 'description')
        net_sec.add_field('region', 'Region', type = 'options')
        net_sec.add_field('sec_group', 'Pick security group', type = 'options')
        net_sec.add_field('insert_sec_group', 'Create security group', type = 'str', blank = True)

        raise tornado.gen.Return([host_info, net_sec])

    @tornado.gen.coroutine
    def validate_field_values(self, step_index, field_values):
        if step_index < 0:
            raise tornado.gen.Return(StepResult(
                errors=[], new_step_index=0, option_choices={}
            ))
        elif step_index == 0:
            self.provider_vars['VAR_APP_ID'] = field_values['app_id']
            self.provider_vars['VAR_APP_KEY'] = field_values['app_key']

            security_groups = yield self.datastore.get('sec_groups')

            raise tornado.gen.Return(StepResult(errors=[], new_step_index=1, option_choices={                    'sec_group' : security_groups, 
                    'region' : self.regions,
            }))
        elif step_index == 1:
            if field_values['insert_sec_group']: 
                security_groups = yield self.datastore.get('sec_groups')
                security_groups.append(field_values['insert_sec_group'])
                yield self.datastore.insert('sec_groups', security_groups)
                raise tornado.gen.Return(StepResult(errors=[], new_step_index=1, option_choices={                    'sec_group' : security_groups, 
                    'region' : self.regions,
            }))
            self.profile_vars['VAR_SEC_GROUP'] = field_values['sec_group']
            self.provider_vars['VAR_REGION'] = field_values['region']
            
            configs = yield self.get_salt_configs()


            passphrase = 'some_generated_pass'
            cmd = ['ssh-keygen', '-f', self.key_path, '-t', 'rsa', '-b', '4096', '-P', passphrase]

            cmd_aws = ['aws', 'ec2', 'import-key-pair', '--key-name', self.key_name, '--public-key-material',  'file://' + self.key_path + '.pub', '--profile', 'aws_provider']

            cmd_new_instance = ['salt-cloud', '--profile=' + self.profile_name, self.profile_name + '_instance']
            with open('/tmp/cmd_line', 'w') as f: 
                f.write(str(subprocess.list2cmdline(cmd_aws)))
                f.write(str(subprocess.list2cmdline(cmd)))
            subprocess.call(cmd)
            subprocess.call(cmd_aws)
            subprocess.call(cmd_new_instance)


            raise tornado.gen.Return(configs)
#            yield hosts.create_host(some_args)

