import smbus
import time
import threading
import math
from collections import deque

class Easing:
    """
    一个包含多种缓动函数作为静态方法的集合。
    所有函数接收一个0到1之间的时间进度t，并返回一个0到1之间的位置进度。
    """
    @staticmethod
    def linear(t):
        """无缓动，线性运动。"""
        return t

    @staticmethod
    def ease_in_out_quad(t):
        """二次方缓入缓出。"""
        t *= 2
        if t < 1: return 0.5 * t * t
        t -= 1
        return -0.5 * (t * (t - 2) - 1)

    @staticmethod
    def ease_in_out_cubic(t):
        """三次方缓入缓出，比quad更平滑。"""
        t *= 2
        if t < 1: return 0.5 * t * t * t
        t -= 2
        return 0.5 * (t * t * t + 2)

    @staticmethod
    def ease_out_bounce(t):
        """缓出弹跳效果。"""
        if t < (1 / 2.75): return 7.5625 * t * t
        elif t < (2 / 2.75):
            t -= (1.5 / 2.75)
            return 7.5625 * t * t + 0.75
        elif t < (2.5 / 2.75):
            t -= (2.25 / 2.75)
            return 7.5625 * t * t + 0.9375
        else:
            t -= (2.625 / 2.75)
            return 7.5625 * t * t + 0.984375

class ServoHandle:
    """
    控制单个舵机的句柄，支持指令队列、状态追踪和回调。
    """
    def __init__(self, controller, servo_num: int):
        self.controller = controller
        self.servo_num = servo_num
        self.current_position = 50.0
        self.is_moving = False
        self._lock = threading.Lock()
        self._command_queue = deque()
        self._sequence_thread = None

    def set_position(self, percent: float):
        """立即设置舵机位置。"""
        with self._lock:
            self.controller.set_position_percent(self.servo_num, percent)
            self.current_position = percent

    def _execute_move(self, target_percent, duration, steps, easing_func, on_complete):
        """执行单个移动的核心逻辑。"""
        self.is_moving = True
        start_percent = self.current_position
        change = target_percent - start_percent
        start_time = time.time()

        if change != 0:
            for i in range(steps + 1):
                progress = i / steps
                eased_progress = easing_func(progress)
                new_pos = start_percent + change * eased_progress
                self.set_position(new_pos)
                
                expected_time = start_time + progress * duration
                sleep_time = expected_time - time.time()
                if sleep_time > 0:
                    time.sleep(sleep_time)
        
        self.set_position(target_percent)
        self.is_moving = False
        if on_complete:
            on_complete()

    def move_to(self, target_percent, duration, steps=100, easing_func=Easing.ease_in_out_quad):
        """(阻塞) 平滑移动到目标位置。"""
        self._execute_move(target_percent, duration, steps, easing_func, None)

    def move_to_async(self, target_percent, duration, steps=100, easing_func=Easing.ease_in_out_quad, on_complete=None):
        """(非阻塞) 在后台平滑移动，完成后可触发回调。"""
        thread = threading.Thread(target=self._execute_move, args=(target_percent, duration, steps, easing_func, on_complete))
        thread.start()
        return thread

    def queue_move(self, target_percent, duration, easing_func=Easing.ease_in_out_quad, on_complete=None):
        """将一个移动指令添加到队列中。"""
        command = {
            'target': target_percent,
            'duration': duration,
            'easing_func': easing_func,
            'on_complete': on_complete
        }
        self._command_queue.append(command)
        return self # 支持链式调用

    def _process_queue(self):
        """(内部方法) 按顺序处理指令队列。"""
        while self._command_queue:
            command = self._command_queue.popleft()
            self._execute_move(
                command['target'], command['duration'], 100, 
                command['easing_func'], command['on_complete']
            )
        print(f"舵机 #{self.servo_num} 的序列已完成。")

    def start_sequence(self):
        """启动一个后台线程来执行队列中的所有动作。"""
        if self._sequence_thread and self._sequence_thread.is_alive():
            print(f"舵机 #{self.servo_num} 的序列已在运行。")
            return
        self._sequence_thread = threading.Thread(target=self._process_queue)
        self._sequence_thread.start()
        return self._sequence_thread

class ServoGroup:
    """一个用于协同控制多个舵机的类。"""
    def __init__(self, **servos):
        self.servos = servos # e.g. {'h': horizontal_servo, 'v': vertical_servo}
        self._active_threads = []

    def move_to_pose(self, pose, duration, easing_func=Easing.ease_in_out_quad):
        """
        让组内所有舵机同时移动到一个“姿态”。
        """
        self._active_threads = []
        for name, target_percent in pose.items():
            if name in self.servos:
                servo = self.servos[name]
                thread = servo.move_to_async(target_percent, duration, easing_func=easing_func)
                self._active_threads.append(thread)
        return self

    def wait_for_move(self):
        """等待当前姿态移动完成。"""
        for thread in self._active_threads:
            thread.join()
        print("编组姿态移动完成。")
        return self

class ServoController:
    """
    通过I2C总线控制舵机驱动板的底层类。
    """
    def __init__(self, bus_number=1, board_address=0x2D):
        self.board_address = board_address
        self.servos = {}
        self._bus_lock = threading.Lock()
        try:
            self.bus = smbus.SMBus(bus_number)
            print(f"成功连接到 I2C 总线 {bus_number}，地址为 {hex(board_address)}")
        except Exception as e:
            self.bus = None
            print(f"I2C 初始化失败: {e}")

    def setup_servo(self, servo_num, **kwargs):
        self.servos[servo_num] = kwargs
        print(f"舵机 #{servo_num} 已配置: {kwargs}")
        return ServoHandle(self, servo_num)
        
    def run_initialization_sequence(self, duration_per_move: float = 1.5):
        """
        对所有已配置的舵机执行一次完整的初始化自检序列。
        流程: 归中 -> 最小值 -> 最大值 -> 归中
        """
        print("\n" + "="*50)
        print("--- 开始执行初始化自检序列 ---")
        print("="*50)
        if not self.servos:
            print("没有配置任何舵机，跳过初始化。")
            return

        all_servo_handles = {f"servo_{num}": ServoHandle(self, num) for num in self.servos.keys()}
        group = ServoGroup(**all_servo_handles)

        pose_center = {name: 50 for name in all_servo_handles.keys()}
        pose_min = {name: 0 for name in all_servo_handles.keys()}
        pose_max = {name: 100 for name in all_servo_handles.keys()}

        print("a) 所有舵机归中...")
        group.move_to_pose(pose_center, duration=1.0).wait_for_move()
        time.sleep(0.5)

        print("b) 所有舵机缓慢移动到最小值...")
        group.move_to_pose(pose_min, duration=duration_per_move).wait_for_move()
        time.sleep(0.5)

        print("c) 所有舵机缓慢移动到最大值...")
        group.move_to_pose(pose_max, duration=duration_per_move * 2).wait_for_move()
        time.sleep(0.5)

        print("d) 所有舵机回到中心...")
        group.move_to_pose(pose_center, duration=duration_per_move).wait_for_move()

        print("\n--- 初始化自检序列完成 ---\n")

    def set_position_percent(self, servo_num, percent):
        if self.bus is None: return
        config = self.servos[servo_num]
        percent = max(0, min(100, percent))
        safe_min = config.get('min_safe_percent', 0)
        safe_max = config.get('max_safe_percent', 100)
        max_angle = config.get('max_angle', 180)
        
        safe_range = safe_max - safe_min
        actual_percent = safe_min + (percent / 100.0) * safe_range
        angle = (actual_percent / 100.0) * max_angle
        scaled_value = int(angle / max_angle * 180)

        with self._bus_lock:
            try:
                self.bus.write_byte_data(self.board_address, servo_num, scaled_value)
            except IOError: pass
    
    def cleanup(self):
        if self.bus: self.bus.close(); print("I2C 总线已关闭。")
