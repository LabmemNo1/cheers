import os
import sys

import yaml


def get_by_key(yaml_obj, *key):
    try:
        res = yaml_obj
        for k in key:
            res = res[k]
        return res
    except KeyError:
        return None


class DnfConfig:
    def __init__(self, path='global.yaml'):
        # 获取当前工作目录的父目录
        # 如果是可执行文件
        if getattr(sys, 'frozen', False):
            parent_directory = os.path.abspath(os.path.join(os.path.abspath(os.path.dirname(sys.executable)), os.pardir))
        else:
            parent_directory = os.path.abspath(os.path.join(os.path.abspath(__file__), os.pardir, os.pardir))
        
        role_yaml = f'{parent_directory}/config/{path}'
        self.cur_yaml = yaml.load(open(role_yaml, "r", encoding="utf-8"), Loader=yaml.FullLoader)

    def get_by_key(self, *key):
        return get_by_key(self.cur_yaml, *key)

# cfg = DnfConfig()
# ttt = cfg.get_by_key('coordinates','attack')
# print(ttt)
