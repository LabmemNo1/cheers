import numpy as np
from adbutils import adb
import scrcpy
import cv2 as cv
import time

from utils import room_calutil
from utils.cvmatch import image_match_util
from utils.dnf_config import DnfConfig
from utils.yolov5 import YoloV5s


class ScrcpyADB:
    def __init__(self, max_width=0, real_width=2712):
        self.global_cfg = DnfConfig()
        self.real_width = self.global_cfg.get_by_key('resolution')
        self.yolo = YoloV5s(target_size=640,
                            prob_threshold=0.25,
                            nms_threshold=0.45,
                            num_threads=4,
                            use_gpu=True)
        devices = adb.device_list()
        client = scrcpy.Client(device=devices[0], max_width=max_width,max_fps=30)
        # You can also pass an ADBClient instance to it
        adb.connect(self.global_cfg.get_by_key('device'))
        print(devices, client)
        # 缩放比例
        self.zoom_ratio = 1 if max_width == 0 else max_width / real_width
        room_calutil.zoom_ratio = self.zoom_ratio
        self.last_screen = None
        self.draw_screem = None
        self.result = None
        self.window_size = (0, 0)  # 窗口大小 宽高 w,h
        client.add_listener(scrcpy.EVENT_FRAME, self.on_frame)
        client.start(threaded=True)
        self.client = client

    def on_frame(self, frame: cv.Mat):
        if frame is not None:
            self.last_screen = frame
            time.sleep(0.01)
            # 复制一份屏幕数据到screen
            screen = self.last_screen.copy()

            s = time.time()
            result = self.yolo(screen)
            # print(f'匹配耗时{int((time.time() - s) * 1000)} ms')
            self.draw_image(screen, result)
            self.result = result
            self.draw_screem = screen
            if self.window_size == (0, 0):
                self.window_size = self.last_screen.shape[1], self.last_screen.shape[0]

    def draw_image(self, screen, result):
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
            self.plot_one_box([obj.rect.x, obj.rect.y, obj.rect.x + obj.rect.w, obj.rect.y + obj.rect.h], screen,
                                  color=color, label=text, line_thickness=2)

    def plot_one_box(self, x, img_source, color=None, label=None, line_thickness=None):
        """
        画框
        :param x:
        :param img_source:
        :param color:
        :param label:
        :param line_thickness:
        :return:
        """
        # 线条粗细
        tl = line_thickness or round(0.002 * (img_source.shape[0] + img_source.shape[1]) / 2) + 1
        color = color or [0, 255, 0]  # 默认绿色
        c1, c2 = (int(x[0]), int(x[1])), (int(x[2]), int(x[3]))  # 转换坐标为整数

        # 画框
        cv.rectangle(img_source, c1, c2, color, thickness=tl, lineType=cv.LINE_AA)

        if label:
            tf = max(tl - 1, 2)  # 文本字体大小
            text_color = [255, 255, 255]  # 默认白色，可以考虑通过参数传递
            text_color = text_color if color is None else color  # 如果有颜色参数，则使用此颜色作为文字颜色

            # 计算文本位置
            # t_size = cv.getTextSize(label, 0, fontScale=tl / 3, thickness=tf)[0]
            # c2 = c1[0] + t_size[0], c1[1] - t_size[1] - 3

            # 在原位置绘制文本，无背景
            cv.putText(img_source, label, (c1[0], c1[1] - 2), 0, tl / 3, text_color, thickness=tf,
                       lineType=cv.LINE_AA)

    def touch_start(self, x: int or float, y: int or float):
        self.client.control.touch(int(x*self.zoom_ratio), int(y*self.zoom_ratio), scrcpy.ACTION_DOWN)

    def touch_move(self, x: int or float, y: int or float):
        self.client.control.touch(int(x*self.zoom_ratio), int(y*self.zoom_ratio), scrcpy.ACTION_MOVE)

    def touch_end(self, x: int or float, y: int or float):
        self.client.control.touch(int(x*self.zoom_ratio), int(y*self.zoom_ratio), scrcpy.ACTION_UP)

    def tap(self, x: int or float, y: int or float, t=0.01):
        self.touch_start(x, y)
        time.sleep(t)
        self.touch_end(x, y)

    def slow_swipe(self, start_x, start_y, end_x, end_y, duration=1.0, steps=50):
        """
        缓慢滑动屏幕.

        :param end_x:
        :param start_x: X coordinate where the swipe starts
        :param start_y: Y coordinate where the swipe starts
        :param end_y: Y coordinate where the swipe ends
        :param duration: Duration of the swipe in seconds
        :param steps: Number of steps for the swipe
        """
        step_duration = duration / steps  # Time per step

        # Send ACTION_DOWN event at the starting point
        self.touch_start(start_x, start_y)

        # Calculate the step size for each move
        step_size_x = (start_x - end_x) / steps
        step_size_y = (start_y - end_y) / steps

        # Perform the swipe by sending ACTION_MOVE events
        for i in range(steps):
            new_x = start_x - (i + 1) * step_size_x
            new_y = start_y - (i + 1) * step_size_y
            self.touch_move(int(new_x), int(new_y))
            # print(f"移动到坐标：x={start_x},y={new_y}")
            time.sleep(step_duration)

        # Send ACTION_UP event at the end point
        self.touch_end(end_x, end_y)
        # print(f"结束坐标：x={start_x},y={end_y}")


if __name__ == '__main__':
    sadb = ScrcpyADB(640)
    while True:
        time.sleep(0.1)
        if sadb.draw_screem is None:
            continue
        cv.imshow('screen', sadb.draw_screem)
        cv.waitKey(1)

    # sadb.touch_start(1994,937)
    # while True:
    #     if sadb.last_screen is None:
    #         continue
    #     # sadb.match_and_box(sadb.last_screen)
    #     # 点击重新挑战
    #     template_img = cv.imread('../template/again_button.jpg')
    #     crop = (1100, 70, 180, 60)
    #     result = image_match_util.match_template_best(template_img, sadb.last_screen,crop)
    #     while result is None:
    #         print('找再次挑战按钮')
    #         time.sleep(0.5)
    #         frame = sadb.last_screen
    #         result = image_match_util.match_template_best(template_img, frame,crop)
    #         cv.imshow('frame', frame)
    #         cv.waitKey(1)
    #     x, y, w, h = result['rect']
    #     cv.imshow('frame', sadb.last_screen)
    #     cv.waitKey(1)
    #     time.sleep(0.01)

