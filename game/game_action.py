import os
import random
import traceback
from typing import Tuple

from game.attack.attack_master import AttackMaster
from utils import room_calutil
from utils.cvmatch import image_match_util
from utils.template_util import TemplateUtil
from utils.yolov5 import YoloV5s
from game.game_control import GameControl
from adb.scrcpy_adb import ScrcpyADB
import time
import cv2 as cv
from ncnn.utils.objects import Detect_Object
import math
import numpy as np

from vo.game_param_vo import GameParamVO


def get_detect_obj_bottom(obj: Detect_Object) -> Tuple[int, int]:
    """
        计算检测对象的底部中心坐标。

        该函数通过给定的检测对象，计算其矩形区域的底部中心坐标。
        这对于需要对对象进行底部对齐或基于底部进行定位的算法非常有用。

        参数:
        obj: Detect_Object 类型的实例，表示一个检测到的对象，具有矩形属性 rect。

        返回值:
        一个元组 (x, y)，其中 x 是底部中心的横坐标，y 是底部中心的纵坐标。
    """
    return int(obj.rect.x + obj.rect.w / 2), int(obj.rect.y + obj.rect.h)


def get_detect_obj_right(obj: Detect_Object) -> Tuple[int, int]:
    return int(obj.rect.x + obj.rect.w), int(obj.rect.y + obj.rect.h/2)


def get_detect_obj_center(obj: Detect_Object) -> Tuple[int, int]:
    return int(obj.rect.x + obj.rect.w/2), int(obj.rect.y + obj.rect.h/2)


def distance_detect_object(a: Detect_Object, b: Detect_Object):
    """
       计算两个检测对象之间的欧几里得距离。

       参数:
       a: Detect_Object 类型的实例，表示第一个检测对象。
       b: Detect_Object 类型的实例，表示第二个检测对象。

       返回值:
       返回两个检测对象之间的距离，距离值为浮点数。
    """
    return math.sqrt((a.rect.x - b.rect.x) ** 2 + (a.rect.y - b.rect.y) ** 2)


def calc_angle(x1, y1, x2, y2):
    """
        计算两个点之间的角度。

        该函数通过计算两个点(x1, y1)和(x2, y2)构成的向量与x轴的夹角，返回该夹角的度数。
        返回的角度在0到180度之间。

        参数:
        x1 (float): 第一个点的x坐标。
        y1 (float): 第一个点的y坐标。
        x2 (float): 第二个点的x坐标。
        y2 (float): 第二个点的y坐标。

        返回:
        int: 两个点之间的角度，以度为单位。
    """
    angle = math.atan2(y1 - y2, x1 - x2)
    return 180 - int(angle * 180 / math.pi)


class GameAction:

    def __init__(self, ctrl: GameControl):
        self.ctrl = ctrl
        self.global_cfg = ctrl.adb.global_cfg
        self.param = GameParamVO()
        self.attack = AttackMaster(ctrl)
        self.yolo = self.ctrl.adb.yolo
        self.adb = self.ctrl.adb

    def find_result(self):
        while True:
            screen = self.ctrl.adb.draw_screem
            if screen is None:
                time.sleep(0.01)
                continue
            result = self.ctrl.adb.result
            cv.imshow('screen', screen)
            cv.waitKey(1)
            return screen, result

    def display_image(self, screen, result):
        if screen is None:
            return
        for obj in result:
            color = (2 ** (obj.label % 9) - 1, 2 ** ((obj.label + 4) % 9) - 1, 2 ** ((obj.label + 8) % 9) - 1)

            cv.rectangle(screen,
                         (int(obj.rect.x), int(obj.rect.y)),
                         (int(obj.rect.x + obj.rect.w), int(obj.rect.y + + obj.rect.h)),
                         color, 2
                         )
            text = f"{self.yolo.class_names[int(obj.label)]}:{obj.prob:.2f}"
            self.adb.plot_one_box([obj.rect.x, obj.rect.y, obj.rect.x + obj.rect.w, obj.rect.y + obj.rect.h], screen,
                                  color=color, label=text, line_thickness=2)
        cv.imshow('screen', screen)
        cv.waitKey(1)

    def get_cur_room_index(self):
        """
        获取当前房间的索引，需要看地图
        :return:
        """
        route_map = None
        result = None
        fail_cnt = 0
        while True:
            self.ctrl.click(2105, 128)
            time.sleep(0.5)
            # screen = self.ctrl.adb.last_screen
            # if screen is None:
            #     continue
            # result = self.yolo(screen)
            screen, result = self.find_result()
            # self.display_image(screen, result)
            route_map = self.find_one_tag(result, 'map')
            if route_map is not None:
                break
            else:
                fail_cnt += 1
                time.sleep(0.05)
                if fail_cnt > 8:
                    print('*******************************地图识别失败*******************************')
                    return None, None, None

        if route_map is not None:
            time.sleep(0.2)
            # 关闭地图
            _, result2 = self.find_result()
            tmp = self.find_one_tag(result2, 'map')
            if tmp is not None:
                self.ctrl.click(2105, 128)
            point = self.find_one_tag(result, 'point')
            if point is None:
                return None, None, None
            # 转换成中心点的坐标
            point = get_detect_obj_center(point)
            route_id, cur_room = room_calutil.get_cur_room_index(point)
            return route_id, cur_room, point

        return None, None, None

    def move_to_next_room(self):
        """
        过图
        :return:
        """
        self.param.mov_start = False
        # 下一个房间的方向
        direction = None
        # mov_start = False
        lax, lay = 0, 0  # 英雄上次循环的坐标
        move_door_cnt = 0
        hero_no = 0
        first_find_door_time = None
        while True:
            screen, result = self.find_result()
            # 2 判断是否过图成功
            ada_image = cv.adaptiveThreshold(cv.cvtColor(self.ctrl.adb.last_screen, cv.COLOR_BGR2GRAY), 255, cv.ADAPTIVE_THRESH_GAUSSIAN_C, cv.THRESH_BINARY_INV, 13, 3)
            if np.sum(ada_image) <= 600000:
                print('*******************************过图成功*******************************')
                self.param.mov_start = False
                self.param.cur_room = self.param.next_room
                self.adb.touch_end(0, 0)
                return result
            # 如果有怪物和装备，就停止过图
            if len(self.find_tag(result, ['Monster_szt', 'Monster_ds', 'Monster', 'equipment'])) > 0:
                print('有怪物或装备，停止过图')
                self.param.mov_start = False
                self.adb.touch_end(0, 0)
                return result

            # 1 先确定要行走的方向
            if direction is None:
                # route_id, cur_room, point = self.get_cur_room_index()
                flag, cur_room = room_calutil.find_cur_room(self.adb.last_screen)
                if flag is False:
                    route_id, cur_room, point = self.get_cur_room_index()
                if cur_room is None:
                    print('没有找到地图和当前房间')
                    return result
                _, next_room = room_calutil.get_next_room(cur_room, self.param.is_succ_sztroom)
                # if next_room is None:
                #     next_room = room_calutil.get_recent_room(cur_room)
                if next_room is None:
                    print('没有找到下一个房间')
                    return result
                self.param.cur_room = cur_room
                self.param.next_room = next_room
                if cur_room == (1,1):
                    self.param.is_succ_sztroom = True
                direction = room_calutil.get_run_direction(cur_room, next_room)
                mx, my = self.ctrl.calc_move_point_direction(direction)
                self.move_to_xy(mx, my)
                screen, result = self.find_result()

            else:
                # 按方向走起来
                mx, my = self.ctrl.calc_move_point_direction(direction)
                self.move_to_xy(mx, my)

            print(f'当前所在房间id：{self.param.cur_room},移动方向：{direction}，当前是否移动：{self.param.mov_start}')

            # 3 先找到英雄位置，在找到对应方向的门进入
            hero = self.find_one_tag(result, 'hero')
            if hero is None:
                hero_no += 1
                print(f'没有找到英雄,{hero_no}次。')
                # mov_start = False
                # self.adb.touch_end(0, 0)
                if hero_no > 8:
                    hero_no = 0
                    self.no_hero_handle(result)
                continue

            hx, hy = get_detect_obj_bottom(hero)
            diff = abs(hx-lax)+abs(hy-lay)
            # 如果数据没什么变化，说明卡墙了
            lax, lay = hx, hy
            print(f'正在过图：英雄位置：{hx},{hy}，与上次的位置变化值：{diff}...')

            # 4 按照对应方向找对应的门
            doortag = room_calutil.get_tag_by_direction(direction)

            door = self.find_tag(result, doortag)
            # go = self.find_tag(result, 'go')

            if len(door) > 0:
                if first_find_door_time is None:
                    first_find_door_time = time.time()
                # 看到门4秒没有过去，说明卡了随机移动
                if time.time() - first_find_door_time > 4:
                    print(f'*******************************看到门4秒没有过去，说明卡了,随机移动*******************************')
                    self.no_hero_handle(result, mov_time=1)
                    first_find_door_time = time.time()
                    continue
                self.move_to_target(door,hero, hx, hy, screen)
                time.sleep(0.1)
                print(f'发现门，往门的方向走。。。。{doortag},移动时间...')
                continue
            else:
                print('没有找到方向门，继续找')

            time.sleep(0.1)
            move_door_cnt += 1
            max_cnt = 50
            if move_door_cnt > max_cnt:
                move_door_cnt = 0
                print(f'***************过门次数超过{max_cnt}次，随机移动一下*******************************')
                self.no_hero_handle(result,mov_time=1)



    def move_to_target(self, target: list, hero, hx, hy, screen):
        min_distance_obj = min(target, key=lambda a: distance_detect_object(hero, a))
        ax, ay = get_detect_obj_bottom(min_distance_obj)
        if self.yolo.class_names[int(min_distance_obj.label)] == 'opendoor_l':
            ax, ay = get_detect_obj_right(min_distance_obj)
        # 装备标了名称，所以要加40，实际上在下方
        if self.yolo.class_names[int(min_distance_obj.label)] == 'equipment':
            ay += 60
        self.craw_line(hx, hy, ax, ay, screen)

        angle = calc_angle(hx, hy, ax, ay)
        # 根据角度计算移动的点击点
        sx, sy = self.ctrl.calc_mov_point(angle)
        # self.ctrl.click(sx, sy, 0.1)
        self.move_to_xy(sx, sy)

    def no_hero_handle(self, result=None, mov_time = 0.3):
        """
        找不到英雄或卡墙了，随机移动，攻击几下
        :param result:
        :param t:
        :return:
        """
        if result is not None and self.find_one_tag(result, 'hero') is not None:
            win_w, win_h = self.adb.window_size
            hero = self.find_one_tag(result, 'hero')
            hx, hy = get_detect_obj_bottom(hero)
            if hx < win_w/5:
                angle = 0
            elif hx > 4*win_w/5:
                angle = 180
            else:
                angle = (self.param.next_angle % 4) * 90 + random.randrange(start=-15, stop=15)
        else:
            angle = (self.param.next_angle % 4) * 90 + random.randrange(start=-15, stop=15)
        print(f'正在随机移动。。。随机角度移动{angle}度。')
        self.param.next_angle = (self.param.next_angle + 1) % 4
        sx, sy = self.ctrl.calc_mov_point(angle)
        self.param.mov_start = False
        self.ctrl.attack(3)
        self.move_to_xy(sx, sy)
        time.sleep(mov_time)

    def move_to_xy(self, x, y, out_time=3):
        """
        移动到指定位置,默认2秒超时
        :param x:
        :param y:
        :return:
        """
        x = x + random.randint(-5, 5)
        y = y + random.randint(-5, 5)
        if (time.time() - self.param.move_time_out) >= out_time:
            self.param.move_time_out = time.time()
            self.param.mov_start = False
        if not self.param.mov_start:
            self.param.mov_start = True
            self.adb.touch_end(x, y)
            time.sleep(0.03)
            self.adb.touch_start(x, y)
            time.sleep(0.01)

        else:
            # print(f'~~~~~正在移动到{x},{y}...')
            self.adb.touch_move(x, y)

    def pick_up_equipment(self):
        """
        捡装备
        :return:
        """
        self.param.mov_start = False
        # 检查装备的次数
        check_cnt = 0
        hero_no = 0
        start_pick = time.time()
        while True:
            screen, result = self.find_result()

            hero = self.find_tag(result, 'hero')
            if len(hero) == 0:
                hero_no += 1
                print(f'没有找到英雄,{hero_no}次。')
                if hero_no > 5:
                    time.sleep(0.2)
                    hero_no = 0
                    self.no_hero_handle(result)
                continue

            monster = self.find_tag(result, ['Monster', 'Monster_ds', 'Monster_szt','card'])
            if len(monster) > 0:
                print('找到怪物，或者发现卡片，停止捡装备。。')
                return result

            hero = hero[0]
            hx, hy = get_detect_obj_bottom(hero)

            equipment = self.find_tag(result, 'equipment')
            if len(equipment) > 0:
                print('找到装备数量：', len(equipment))
                self.move_to_target(equipment, hero, hx, hy, screen)
                if time.time() - start_pick > 3:
                    print('捡装备，超过3秒，随机移动。。。')
                    self.no_hero_handle(mov_time=1)
                    start_pick = time.time()

            else:
                # 没有装备就跳出去
                check_cnt += 1
                if check_cnt >= 5:
                    print(f'没有装备，停止移动。当前移动状态：{self.param.mov_start}')
                    if self.param.mov_start:
                        self.param.mov_start = False
                        self.adb.touch_end(0, 0)
                    return result
                print(f'没有找到装备:{check_cnt} 次。。。')
                continue


    def attack_master(self):
        """
        找到怪物，攻击怪物
        :return:
        """
        self.param.mov_start = False
        attak_cnt = 0
        check_cnt = 0
        print(f'开始攻击怪物,当前房间：{self.param.cur_route_id}')
        mov_to_master_start = time.time()
        attack_distance = self.global_cfg.get_by_key('attack_distance')
        attack_distance = attack_distance if attack_distance is None else 600
        room_skill_flag = True
        while True:
            # 找到牌子
            screen, result = self.find_result()
            card = self.find_tag(result, ['card','go','opendoor_l','opendoor_r','opendoor_u','op'])
            if len(card) > 0:
                print('找到翻牌的卡片，不攻击')
                return

            hero = self.find_tag(result, 'hero')
            if len(hero) == 0:
                print(f'没有找到英雄,随机移动攻击')
                self.no_hero_handle(result)
                continue

            hero = hero[0]
            hx, hy = get_detect_obj_bottom(hero)
            cv.circle(screen, (hx, hy), 5, (0, 0, 125), 5)
            # 开启一次性的状态技能
            if self.param.skill_start is not True:
                self.param.skill_start = True
                self.attack.state_skill()
                # self.ctrl.skill_right()
            # 有怪物，就攻击怪物
            monster = self.find_tag(result, ['Monster', 'Monster_ds', 'Monster_szt'])
            if len(monster) > 0:
                check_cnt=0
                print('怪物数量：', len(monster))
                if room_skill_flag:
                    room_skill_flag = False
                    # 先来一套固定技能，然后在随机打
                    print(f'开始释放房间{self.param.cur_room}的固定技能。。。')
                    self.attack.room_skill(self.param.cur_room)

                # 最近距离的怪物坐标
                nearest_monster = min(monster, key=lambda a: distance_detect_object(hero, a))
                distance = distance_detect_object(hero, nearest_monster)
                ax, ay = get_detect_obj_bottom(nearest_monster)
                # 判断在一条直线上再攻击
                y_dis = abs(ay - hy)
                print(f'最近距离的怪物坐标：{ax},{ay},距离：{distance},y距离：{y_dis}')
                ratio = room_calutil.zoom_ratio
                if self.param.cur_room == (1,1) and attak_cnt == 0:
                    attak_cnt += 1
                    # 狮子头房间放觉醒
                    self.attack.unique_skill()
                    continue

                if distance <= attack_distance * ratio and y_dis <= 100*ratio:
                    # 面向敌人
                    angle = calc_angle(hx, hy, ax, hy)
                    sx, sy = self.ctrl.calc_mov_point(angle)
                    self.param.mov_start = False
                    self.move_to_xy(sx, sy)
                    # self.ctrl.move(angle, 0.3)
                    print(f'====================敌人与我的角度{angle}==攻击怪物，攻击次数：{attak_cnt}，当前房间,{self.param.cur_room}')
                    attak_cnt += 1
                    # 释放连招，懒得细分不同类型技能了，一股脑放吧
                    self.attack.buff_skill()
                    self.attack.hurt_skill()

                    mov_to_master_start = time.time()

                # ax, ay = get_detect_obj_center(nearest_monster)
                # 怪物在右边,就走到怪物走边400的距离
                if ax > hx:
                    ax = int(ax - (attack_distance-100) * ratio)
                else:
                    ax = int(ax + (attack_distance-100) * ratio)
                self.craw_line(hx, hy, ax, ay, screen)
                angle = calc_angle(hx, hy, ax, ay)
                sx, sy = self.ctrl.calc_mov_point(angle)
                # self.param.mov_start = False
                self.move_to_xy(sx, sy,1)
                if time.time()-mov_to_master_start > 3:
                    self.no_hero_handle(mov_time=1)
                    mov_to_master_start = time.time()


            else:
                time.sleep(0.1)
                check_cnt += 1
                if check_cnt >= 5:
                    print(f'没有找到怪物:{check_cnt}次。。。')
                    return


    def craw_line(self, hx, hy, ax, ay, screen):
        # cv.circle(screen, (hx, hy), 5, (0, 0, 125), 5)
        # 计算需要移动到的的坐标
        cv.circle(screen, (hx, hy), 5, (0, 255, 0), 5)
        cv.circle(screen, (ax, ay), 5, (0, 255, 255), 5)
        cv.arrowedLine(screen, (hx, hy), (ax, ay), (255, 0, 0), 3)
        cv.imshow('screen', screen)
        cv.waitKey(1)


    def find_tag(self, result, tag):
        """
        根据标签名称来找到目标
        :param result:
        :param tag:
        :return:
        """
        hero = [x for x in result if self.yolo.class_names[int(x.label)] in tag]
        return hero

    def find_one_tag(self,result,tag):
        """
        根据标签名称来找到目标
        :param result:
        :param tag:
        :return:
        """
        reslist = [x for x in result if self.yolo.class_names[int(x.label)] == tag]
        if len(reslist) == 0:
            print(f'没有找到标签{tag}')
            return None
        else:
            return reslist[0]

    def reset_start_game(self):
        """
        重置游戏，回到初始状态
        :return:
        """
        while True:
            screen, result = self.find_result()

            card = self.find_tag(result, 'card')
            select = self.find_tag(result, 'select')
            start = self.find_tag(result, 'start')
            if len(select) > 0:
                self.ctrl.click(294,313)
                time.sleep(0.5)
                self.ctrl.click(1640,834)
                return
            elif len(start) > 0:
                time.sleep(0.5)
                self.ctrl.click(1889, 917)
                return
            elif len(card) > 0:
                print('打完了，去翻牌子')
                time.sleep(3)
                # 翻第三个牌子
                self.ctrl.click(1398,377)
                time.sleep(0.5)
                self.ctrl.click(1398,377)
                time.sleep(1.5)
                self.param.cur_room = (1, 5)

                return
            else:
                return

    def again(self):
        try:
            if self.param.cur_room != (1, 5) and self.param.cur_room != (1, 4):
                return
            screen, result = self.find_result()
            if len(self.find_tag(result, ['equipment','Monster', 'Monster_ds', 'Monster_szt'])) > 0:
                return

            template_util = TemplateUtil()
            # 发现修理装备，就修理
            screen = self.ctrl.adb.last_screen
            repair_res = template_util.find_template('修理装备',screen)
            if repair_res is not None:
                print('发现修理装备按钮,点击修理装备')
                # x, y, w, h = repair_res['rect']
                self.ctrl.click(repair_res[0] / self.ctrl.adb.zoom_ratio, repair_res[1] / self.ctrl.adb.zoom_ratio)
                time.sleep(0.8)
                # 点击修理
                self.ctrl.click(1056, 950)
                time.sleep(0.8)
                self.ctrl.click(repair_res[0] / self.ctrl.adb.zoom_ratio, repair_res[1] / self.ctrl.adb.zoom_ratio)
                time.sleep(0.2)

            # 截取区域 xywh，在电脑用截图工具拿到
            again_btn = template_util.find_template('再次挑战地下城',screen)
            if again_btn is None:
                return

            # 发现了再次挑战，就重开
            print('发现再次挑战按钮,点击重开')
            # x, y, w, h = result['rect'] #{'confidence': 0.748958170413971, 'rect': (1129, 129, 128, 24)}
            self.ctrl.click(again_btn[0] / self.ctrl.adb.zoom_ratio, again_btn[1] / self.ctrl.adb.zoom_ratio)
            print('成功点击再次挑战按钮')
            time.sleep(0.8)
            self.ctrl.click(1304, 691)
            # 初始化参数
            self.param = GameParamVO()

        except Exception as e:
            print('没有找到再次挑战按钮:', e)


    def test(self):
        print(f'开始释放房间{self.param.cur_room}的固定技能。。。')
        self.attack.room_skill(self.param.cur_room)


def run():
    ctrl = GameControl(ScrcpyADB(1384)) #1384
    action = GameAction(ctrl)

    while True:
        try:
            # 根据出现的元素分配动作
            if len(action.find_tag(action.find_result()[1], 'equipment'))>0:
                print('--------------------------------发现装备，开始捡起装备--------------------------------')
                action.pick_up_equipment()
            if len(action.find_tag(action.find_result()[1], ['go', 'go_d', 'go_r', 'go_u','opendoor_d', 'opendoor_r', 'opendoor_u', 'opendoor_l'])) > 0:
                print('--------------------------------发现门，开始移动到下一个房间--------------------------------')
                action.move_to_next_room()
            if len(action.find_tag(action.find_result()[1], ['Monster', 'Monster_ds', 'Monster_szt'])) > 0:
                print('--------------------------------发现怪物，开始攻击--------------------------------')
                action.attack_master()
            if len(action.find_tag(action.find_result()[1], ['select', 'start', 'card']))>0:
                print('--------------------------------发现选择框或牌子卡片，开始选择--------------------------------')
                action.reset_start_game()
            action.again()
        except Exception as e:
            action.param.mov_start = False
            print(f'出现异常:{e}')
            traceback.print_exc()

    print('程序结束...')
    while True:
        print('全部完成，展示帧画面...')
        screen, result = action.find_result()
        time.sleep(0.1)


def test():
    ctrl = GameControl(ScrcpyADB(1384))
    action = GameAction(ctrl)

    while True:
        try:
            action.find_result()
            print('--------------------------------test start--------------------------------')
            cv.imwrite('test.jpg', action.adb.last_screen)
            res = room_calutil.find_cur_room(action.adb.last_screen)
            action.param.cur_room = res[1]
            action.test()

            print(res)
            time.sleep(1)
            print('--------------------------------test end--------------------------------')

        except Exception as e:
            action.param.mov_start = False
            print(f'出现异常:{e}')
            traceback.print_exc()



if __name__ == '__main__':
    """
    启动入口
    :author: Cheers。。
    """
    run()
    # test()

