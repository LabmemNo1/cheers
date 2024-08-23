import os
from time import sleep

import cv2
import yaml

from game import GameControl
from utils import dnf_config, room_calutil
from utils.dnf_config import DnfConfig
from vo.game_param_vo import GameParamVO


def get_by_key(yaml_obj, *key):
    return dnf_config.get_by_key(yaml_obj, *key)


class AttackMaster():
    def __init__(self, ctrl: GameControl):
        self.ctrl = ctrl
        # self.param = param
        # global_cfg = DnfConfig()
        # self.global_cfg = global_cfg
        self.global_cfg = ctrl.adb.global_cfg
        cur_role = self.global_cfg.get_by_key('cur_role')
        role_config = self.global_cfg.get_by_key('role_config')
        # role_config为list，每个元素包含role_name和path，遍历找出role_name=cur_role的配置
        role_yaml_path = None
        for role_config_item in role_config:
            if role_config_item['role_name'] == cur_role:
                role_yaml_path = role_config_item['path']
                break
        if role_yaml_path is None:
            raise Exception("未找到当前角色的配置")
        # 读取到当前角色的配置
        role_yaml = DnfConfig(role_yaml_path)
        self.role_yaml = role_yaml.cur_yaml
        # 记录伤害技能到第几个了
        self.skill_cnt = 0
        print(self.role_yaml)

    def state_skill(self):
        """
        释放一次性的加状态技能
        :return:
        """
        self.release_skill("state_skills")

    def unique_skill(self):
        """
        释放觉醒大招技能逻辑
        :return:
        """
        self.release_skill("unique_skills")

    def buff_skill(self):
        """
        释放加buff的技能
        :return:
        """
        self.release_skill("buff_skills")

    def hurt_skill(self):
        """
        释放打伤害的技能
        :return:
        """
        # self.release_skill("room_skills")
        self.release_skill("hurt_skills")

    def is_ready(self, skill: str,last_screen):
        """
        看技能是否准备好，冷却完成
        :param skill: 技能名称
        :return:
        """
        if not skill or skill == 'move' or skill == 'attack':
            return True
        skill_position = self.global_cfg.get_by_key('coordinates', skill)
        if not isinstance(skill_position, list):
            return True
        ratio = room_calutil.zoom_ratio
        skill_position = (int(skill_position[0] * ratio), int(skill_position[1] * ratio))
        # 从中心点向四周扩散的偏移量
        offset = int(40*ratio)
        # 判断技能是否冷却的阈值，当像素点小于这个阈值，说明技能正在冷却
        some_threshold = int(440*ratio)
        crop = (
            skill_position[0] - offset, skill_position[1] - offset, skill_position[0] + offset,
            skill_position[1] + offset)

        # 读取屏幕截图中的技能图标区域
        skill_icon = last_screen[crop[1]:crop[3], crop[0]:crop[2]]
        # 将图标转换为灰度图像
        gray_icon = cv2.cvtColor(skill_icon, cv2.COLOR_BGR2GRAY)

        # 使用二值化处理，分离冷却遮罩
        _, thresholded = cv2.threshold(gray_icon, 120, 255, cv2.THRESH_BINARY)

        # 计算非零像素数量
        non_zero_pixels = cv2.countNonZero(thresholded)
        # cv2.imshow("skill_icon", skill_icon)
        # cv2.imshow("thresholded", thresholded)
        # cv2.waitKey(1)
        # print(f'技能{skill}非零像素数量:{non_zero_pixels} 阈值:{some_threshold}')

        # 如果非零像素数量小于某个阈值，说明图标是灰色的，技能正在冷却
        if non_zero_pixels < some_threshold:  # 你可以根据实际情况调整阈值
            print(f"技能 {skill}，正在冷却中...")
            return False
        else:
            print(f"技能 {skill}，完成冷却，可以释放")
            return True

    def release_skill(self, skill_type='buff_skills'):
        buff_skills = get_by_key(self.role_yaml, skill_type)
        if not buff_skills:
            return
        role_name = get_by_key(self.role_yaml, 'role_name')
        # 伤害技能包含两层list，需要取一套技能释放
        if skill_type == "hurt_skills":
            i = self.skill_cnt % len(buff_skills)
            buff_skills = buff_skills[i]
            print(f'...正在释放【{role_name}】的第【{i}】套技能连招...')
            self.skill_cnt = i + 1

        else:
            print(f'...正在释放【{role_name}】的【{skill_type}】技能...')
        self.do_skills(buff_skills)

    def do_skills(self, buff_skills,if_vaild=True):
        # 在同一画面校验是否cd
        last_screen = self.ctrl.adb.last_screen
        for skill in buff_skills:
            try:
                skill_name = get_by_key(skill, 'skill_name')
                # 技能还在冷却，则跳过
                if if_vaild and not self.is_ready(skill_name,last_screen):
                    continue
                # 释放技能
                skill_method = getattr(self.ctrl, skill_name)
                time = get_by_key(skill, 'time')
                param = get_by_key(skill, 'param')
                if time:
                    skill_method(time)
                elif param:
                    skill_method(*param)
                else:
                    skill_method()
                # 配置了等待时间，则等待
                wait = get_by_key(skill, 'wait')
                if wait:
                    sleep(wait)
            except Exception as e:
                print(e)

    def room_skill(self, cur_room):
        """
        房间技能
        :param cur_room:
        :return:
        """
        # self.release_skill("room_skills")
        # elif skill_type == "room_skills":
        buff_skills = get_by_key(self.role_yaml, 'room_skills')
        if buff_skills is None:
            print(f'...所有房间技能未配置...')
            return
        for skill in buff_skills:
            room = get_by_key(skill, 0,'room_ij')
            if cur_room == tuple(room):
                print(f'...正在释放【{cur_room}】房间技能...')
                buff_skills = skill[1:]
                self.do_skills(buff_skills)
                return
        print(f'...【{cur_room}】房间技能未配置...')



if __name__ == '__main__':
    attack_master = AttackMaster(None)
    attack_master.room_skill((1,1))
    # attack_master.hurt_skill()
    # attack_master.state_skill()
    # attack_master.buff_skill()
    pass
