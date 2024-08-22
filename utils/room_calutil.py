import json
import os
import typing

import cv2
from ncnn.utils.objects import Rect
from torch import Size
from typing import Tuple

from utils.cvmatch import image_match_util

# 走的房间路线顺序路线图,第几行第几列
room_route = [
    (1, 0),
    (2, 0),
    (2, 1),
    (2, 2),
    (1, 2),
    (1, 1),
    (1, 2),
    (1, 3),
    (1, 4),
    (1, 5)
]
print(f"布万加刷图的路线图:{room_route}")
all_room = [
    (1, 0),
    (2, 0),
    (2, 1),
    (2, 2),
    (1, 2),
    (1, 1),
    (1, 2),
    (1, 3),
    (1, 4),
    (1, 5),
    (0, 2),
    (0, 1),
    (0, 0)
]

# 获取屏幕每帧的缩放比例
zoom_ratio = 1


def rect_slice_index(rect: Rect, size: Size, point: tuple) -> Tuple[int, int]:
    """
    矩形（范围)，切片索引
    ：param rect：范围
    ：param size： 切片大小 x 方块数量 y 轴方块数量
    ：param point：要索引的坐标
    : return: 如 (4, 1) 则表示目标在切片索引的第 4 行，第 1 列
    """
    rect = Rect(rect.x * zoom_ratio, rect.y * zoom_ratio, rect.w * zoom_ratio, rect.h * zoom_ratio)
    x1, y1, x2, y2 = rect.x, rect.y, rect.x + rect.w, rect.y + rect.h
    width = rect.w / size[0]
    height = rect.h / size[1]
    rects = [
        [(x1 + i * width, y1 + j * height, x1 + (i + 1) * width, y1 + (j + 1) * height) for i in range(size[0])] for
        j in range(size[1])]
    # print(f"所有方块对应的坐标范围:{rects}")
    for i, row in enumerate(rects):
        for j, rect in enumerate(row):
            x1, y1, x2, y2 = rect
            if x1 <= point[0] < x2 and y1 <= point[1] < y2:
                return i, j


def get_cur_room_index(point):
    """
    获取房间索引
    ：param point：要索引的坐标
    : return: 如 (4, 1) 则表示目标在切片索引的第 4 行，第 1 列
    """
    # 锁定获取的范围和每个房间方块的大小
    xy = rect_slice_index(Rect(850, 380, 635, 315), Size((6, 3)), point)
    # 遍历room_route
    cur_ind = None

    for ind,room in enumerate(room_route):
        if xy == room_route[ind]:
            cur_ind = ind
            break
    print(f"当前房间索引:{cur_ind},房间行列号：{xy}")
    return cur_ind,xy


def get_recent_room(cur_room):
    next_room_1 = (cur_room[0],cur_room[1] + 1)
    next_room_2 = (cur_room[0] + 1,cur_room[1])
    next_room_3 = (cur_room[0],cur_room[1] - 1)
    next_room_4 = (cur_room[0] - 1,cur_room[1])
    for ind,room in enumerate(room_route):
        if next_room_1 == room or next_room_2 == room or next_room_3 == room or next_room_4 == room:
            return room
    print("从预设的路线中，没有找到下一个房间")
    for ind,room in enumerate(all_room):
        if next_room_1 == room or next_room_2 == room or next_room_3 == room or next_room_4 == room:
            return room


def get_next_room(cur_room, is_succ_sztroom: bool = False):
    # ind,cur_room = get_cur_room_index(point)
    ind = None
    for i, room in enumerate(room_route):
        if cur_room == room_route[i]:
            ind = i
            break
    if is_succ_sztroom and ind == 4:
        ind = 6

    # 狮子头房间刷过了，不用去了
    if is_succ_sztroom and cur_room == (1, 2):
        return 7, (1, 3)
    # 狮子头房间=5,(1,1) 没有刷，但是不小心进去下一个了,往回走
    if not is_succ_sztroom and ind > 5:
        nex_room = room_route[ind-1]
        return ind-1, nex_room

    # vals转换成连表的形式，用于获取下一个
    if cur_room in room_route:
        try:
            index = room_route.index(cur_room,ind)
        except ValueError:
            index = all_room.index(cur_room,0)

        if index >= len(room_route) - 1:
            return None,None
        next_room = room_route[index + 1]
        return index + 1, next_room


def get_run_direction(cur_room,next_room):
    # (1,0)-(2,0) 走下
    # 计算行走的方向
    if cur_room[0] == next_room[0]:
        if cur_room[1] > next_room[1]:
            return 'left'
        else:
            return 'right'
    else:
        if cur_room[0] > next_room[0]:
            return 'up'
        else:
            return 'down'


def get_tag_by_direction(direction):
    # 计算行走的方向
    if direction == 'up':
        return 'opendoor_u'
    elif direction == 'down':
        return 'opendoor_d'
    elif direction == 'left':
        return 'opendoor_l'
    elif direction == 'right':
        return 'opendoor_r'


parent_directory = os.path.abspath(os.path.join(os.path.abspath(__file__), os.pardir, os.pardir))
with open(f'{parent_directory}/template/布万加房间/cfg.json', 'r',encoding='utf-8') as file:
    cfgs = json.load(file)
img_names = list(filter(lambda x: x.endswith('.png'), os.listdir(f'{parent_directory}/template/布万加房间')))
img_map = {item: cv2.imread(f'{parent_directory}/template/布万加房间/{item}') for item in img_names}


def find_cur_room(screen, confi=0.7):
    """
    根据小地图特征找当前房间
    :param screen: 当前帧
    :param confi: 默认最小置信度
    :return: flag 是否匹配成功, room
    """
    flag = False
    room = None
    if isinstance(cfgs, list):
        confidence = confi
        for cfg in cfgs:
            # 识别区域
            crop = cfg['rect']
            img_name = cfg['img_name']
            img = img_map[img_name]
            res = image_match_util.cvmatch_template_best(img, screen, crop)
            if res is not None:
                # 取可信度最高的匹配结果
                if res['confidence'] > confidence:
                    confidence = res['confidence']
                    room = tuple(cfg['name'])
                    # print(confidence,room)
                    flag = True
    print(f'匹配房间结果：{flag},房间行列号:{room}')
    return flag, room

if __name__ == '__main__':
    t = rect_slice_index(Rect(100, 100, 100, 100), Size((10, 6)), (101.54, 145.864))
    print(get_next_room((1, 1), False))
    print(t)
    print(t == (4, 0))
    print(get_cur_room_index((101.54, 145.864)))
    print(get_run_direction((0, 1), (0, 2)))
    print(get_run_direction((0, 2), (1, 2)))