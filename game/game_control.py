import random
import time
from typing import Tuple

from adb.scrcpy_adb import ScrcpyADB
import math

from utils.dnf_config import DnfConfig


class GameControl:
    def __init__(self, adb: ScrcpyADB):
        self.adb = adb
        self.cfg = adb.global_cfg

    def calc_mov_point(self, angle: float) -> Tuple[int, int]:
        angle = angle % 360
        rx, ry = self.cfg.get_by_key('coordinates', 'wheel_center')
        r = self.cfg.get_by_key('coordinates', 'wheel_radius')

        x = rx + r * math.cos(angle * math.pi / 180)
        y = ry - r * math.sin(angle * math.pi / 180)
        return int(x), int(y)

    def move(self, angle: float, t: float):
        # 计算轮盘x, y坐标
        x, y = self.calc_mov_point(angle)
        self.click(x, y, t)

    def calc_move_point_direction(self, direction: str):
        if direction is None:
            return None
        # 计算轮盘x, y坐标
        angle = 0
        if direction == 'up':
            angle = 90
        if direction == 'down':
            angle = 270
        if direction == 'left':
            angle = 180
        x, y = self.calc_mov_point(angle)
        return x, y

    def attack(self, cnt: int = 1):
        x, y = self.cfg.get_by_key('coordinates', 'attack')
        for i in range(cnt):
            # 点的太快可能被检测，做一点随机
            if i > 0:
                t = random.randint(50, 100)/1000
                time.sleep(t)
            t = random.randint(50, 100) / 1000
            self.click(x, y, t)


    def skill_d(self, t: float = 0.03):
        x, y = self.cfg.get_by_key('coordinates', 'skill_d')
        self.click(x, y, t)

    def skill_f(self, t: float = 0.04):
        x, y = self.cfg.get_by_key('coordinates', 'skill_f')
        self.click(x, y, t)

    def skill_1(self, t: float = 0.03):
        x, y = self.cfg.get_by_key('coordinates', 'skill_1')
        self.click(x, y, t)

    def skill_2(self, t: float = 0.04):
        x, y = self.cfg.get_by_key('coordinates', 'skill_2')
        self.click(x, y, t)

    def skill_3(self, t: float = 0.05):
        x, y = self.cfg.get_by_key('coordinates', 'skill_3')
        self.click(x, y, t)

    def skill_4(self, t: float = 0.04):
        x, y = self.cfg.get_by_key('coordinates', 'skill_4')
        self.click(x, y, t)

    def skill_5(self, t: float = 0.04):
        x, y = self.cfg.get_by_key('coordinates', 'skill_5')
        self.click(x, y, t)

    def skill_t(self, t: float = 0.04):
        x, y = self.cfg.get_by_key('coordinates', 'skill_t')
        self.click(x, y, t)

    def skill_y(self, t: float = 0.04):
        x, y = self.cfg.get_by_key('coordinates', 'skill_y')
        self.click(x, y, t)

    def skill_q(self, t: float = 0.04):
        x, y = self.cfg.get_by_key('coordinates', 'skill_q')
        self.click(x, y, t)

    def skill_w(self, t: float = 0.04):
        x, y = self.cfg.get_by_key('coordinates', 'skill_w')
        self.click(x, y, t)

    def skill_e(self, t: float = 0.04):
        x, y = self.cfg.get_by_key('coordinates', 'skill_e')
        self.click(x, y, t)

    def skill_r(self, t: float = 0.04):
        x, y = self.cfg.get_by_key('coordinates', 'skill_r')
        self.click(x, y, t)

    def skill_up(self, t: float = 0.1):
        x, y = self.cfg.get_by_key('coordinates', 'skill_swip_center')
        x, y = self._ramdon_xy(x, y)
        self.adb.slow_swipe(x, y, x, y - 100, duration=t, steps=1)

    def skill_down(self, t: float = 0.1):
        x, y = self.cfg.get_by_key('coordinates', 'skill_swip_center')
        x, y = self._ramdon_xy(x, y)
        self.adb.slow_swipe(x, y, x, y + 100, duration=t, steps=1)

    def skill_left(self, t: float = 0.1):
        x, y = self.cfg.get_by_key('coordinates', 'skill_swip_center')
        x, y = self._ramdon_xy(x, y)
        self.adb.slow_swipe(x, y, x - 100, y, duration=t, steps=1)

    def skill_right(self, t: float = 0.1):
        x, y = self.cfg.get_by_key('coordinates', 'skill_swip_center')
        x, y = self._ramdon_xy(x, y)
        self.adb.slow_swipe(x, y, x + 100, y, duration=t, steps=1)


    def click(self, x, y, t: float = 0.04):
        x, y = self._ramdon_xy(x, y)
        self.adb.touch_start(x, y)
        time.sleep(t)
        self.adb.touch_end(x, y)

    def _ramdon_xy(self, x, y):
        x = x + random.randint(-5, 5)
        y = y + random.randint(-5, 5)
        return x, y

if __name__ == '__main__':
    ctl = GameControl(ScrcpyADB(1380))
    ctl.move(0,1)
    ctl.move(90,1)
    ctl.move(180,1)
    ctl.move(270,1)


    # ctl.kuangzhan_skill(0)
    # ctl.kuangzhan_skill(1)
    # ctl.kuangzhan_skill(2)
    # ctl.kuangzhan_skill(3)
    # ctl.kuangzhan_skill(4)
    # ctl.kuangzhan_skill(5)
    # ctl.kuangzhan_skill(6)
    # ctl.kuangzhan_skill(7)
    # ctl.kuangzhan_skill(8)
    # ctl.move(180, 3)
    # time.sleep(0.3)
    # ctl.attack()
    # time.sleep(0.3)
    # ctl.move(270, 5)
    # time.sleep(0.3)
    # ctl.attack(3)


