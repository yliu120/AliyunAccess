import argparse
import json
import logging
import string

from typing import Any

from aliyunsdkcore.client import AcsClient
from aliyunsdkeci.request.v20180808.CreateContainerGroupRequest import CreateContainerGroupRequest

FLAGS = None

DEFAULT_CONTAINER_GROUP_NAME = 'test'
DEFAULT_REGION = 'cn-zhangjiakou'
# vCPU x4, Memory 15G, NVIDIA T4 GPU x1
# Please see https://help.aliyun.com/document_detail/25378.html
DEFAULT_INSTANCE = 'ecs.gn6i-c4g1.xlarge'
DEFAULT_SPOT_STRATEGY = 'NoSpot'
DEFAULT_CPU = 4
DEFAULT_GPU = 1
DEFAULT_MEMORY = 15
DEFAULT_NFS_PATH = '/'
VOLUME_TYPE = 'NFSVolume'

# Uses a basic logger.
logging.basicConfig(format='%(asctime)s %(levelname)s:%(message)s',
                    level=logging.DEBUG)


class ConfigValue:
  '''ConfigValue that identifies whether a var is required or not.'''

  def __init__(self, value=None, required=False):
    self._value = value
    self._required = required

  def __eq__(self, obj):
    if isinstance(obj, ConfigValue):
      return self._value == obj.value
    return self._value == obj

  @property
  def required(self):
    return self._required

  @property
  def value(self):
    return self._value

  @value.setter
  def value(self, value):
    self._value = value


class Config:
  '''
  Configuration for setting up an ECI container running Gromacs App.
  A better implementation might be using FlatBuffers/ProtoBuf.
  Here we simply make this python program monolithic to simplify the
  interactions with Aliyun.

  All fields are required unless commented.
  Dynamically construct config object with attr hooks decreases
  readability but it is convenient and necessary to keep this class
  small. Essentially, we need to use FlatBuffers/Protobuf to generate
  APIs automatically for structured data.
  '''
  access_key_id = ConfigValue(required=True)
  access_secret = ConfigValue(required=True)
  region = ConfigValue(value=DEFAULT_REGION, required=True)

  container_group_name = ConfigValue(value=DEFAULT_CONTAINER_GROUP_NAME,
                                     required=True)

  instance_type = ConfigValue(value=DEFAULT_INSTANCE, required=True)
  cpu = ConfigValue(value=DEFAULT_CPU, required=True)
  memory = ConfigValue(value=DEFAULT_MEMORY, required=True)
  gpu = ConfigValue(value=DEFAULT_GPU, required=True)
  container = ConfigValue(required=True)
  image = ConfigValue(required=True)
  volume_name = ConfigValue()
  volume_mount_path = ConfigValue()
  v_switch_id = ConfigValue()
  security_group_id = ConfigValue()
  nfs_server = ConfigValue()
  command = ConfigValue()
  spot_strategy = ConfigValue(value=DEFAULT_SPOT_STRATEGY)

  @classmethod
  def validate(cls):
    for k, v in vars(cls).items():
      if isinstance(v, ConfigValue) and v.required and v is None:
        raise ValueError('Config key: {k} should not be none.'.format(k=k))

  @classmethod
  def is_registered_key(cls, key):
    return hasattr(cls, key)

  @classmethod
  def as_config(cls, json_dict):
    for key, value in json_dict.items():
      if not cls.is_registered_key(key):
        raise ValueError("Unknown key in the JSON input file: " + key)
      if isinstance(getattr(cls, key), ConfigValue):
        cls.__dict__[key].value = value

    config_values = [(key, value)
                     for (key, value) in vars(cls).items()
                     if isinstance(value, ConfigValue)]
    for key, value in config_values:
      if isinstance(value, ConfigValue):
        # For convenience and safety purpose, dynamically adds accessors to
        # config values.
        # To access the value of each config, we just need to call
        # config.KeyInCamelCase, e.g., config.Command
        setattr(
            cls,
            # key_in_camel_case => KeyInCamelCase
            string.capwords(key, '_').replace('_', ''),
            getattr(cls, key).value)

    cls.validate()
    return cls


def build_volumes(config):
  '''For simplicity, only one volume is allowed in the config.'''
  if config.VolumeName is None:
    return [], []
  return [{
      "Name": config.VolumeName,
      "MountPath": config.VolumeMountPath
  }], [{
      "Name": config.VolumeName,
      # We only support NFS type.
      "Type": VOLUME_TYPE,
      "NFSVolume.Server": config.NfsServer,
      "NFSVolume.Path": DEFAULT_NFS_PATH,
      "NFSVolume.ReadOnly": False,
  }]


def create_container_request(config):
  request = CreateContainerGroupRequest()
  request.set_accept_format('json')
  request.set_ContainerGroupName(config.ContainerGroupName)
  request.set_RestartPolicy('Never')
  request.set_SpotStrategy(config.SpotStrategy)
  request.set_InstanceType(config.InstanceType)
  request.set_VSwitchId(config.VSwitchId)
  request.set_SecurityGroupId(config.SecurityGroupId)

  if config.container is None:
    raise ValueError("Unable to create a request from a null container.")

  volume_mounts, volumes = build_volumes(config)
  request.set_Containers([{
      'Image': config.Image,
      # As having one container in the group, it shares the name of the group.
      'Name': config.ContainerGroupName,
      'Cpu': config.Cpu,
      'Memory': config.Memory,
      'Gpu': config.Gpu,
      'VolumeMounts': volume_mounts,
      "Commands": config.Command
  }])
  request.set_Volumes(volumes)
  return request


def main(_):
  with open(FLAGS.conf, 'r') as f:
    config = json.load(f, object_hook=Config.as_config)

  client = AcsClient(config.AccessKeyId,
                     config.AccessSecret,
                     config.Region,
                     debug=FLAGS.debug)
  request = create_container_request(config)
  response = client.do_action_with_exception(request)
  logging.info(str(response))


if __name__ == '__main__':
  parser = argparse.ArgumentParser(
      description='Create Gromacs Container on Aliyun ECI')
  parser.add_argument('--conf',
                      type=str,
                      default='',
                      help='The configuration file in JSON format.')
  parser.add_argument('--debug', type=bool, default=False, help='Debug mode.')

  FLAGS, unparsed = parser.parse_known_args()
  main(unparsed)
