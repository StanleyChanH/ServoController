# Raspberry Pi Servo Controller Library

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

通过树莓派5的I2C接口控制亚博智能16路舵机驱动板的Python库，提供平滑运动控制、队列指令、多舵机协同等高级功能。

## 🛠 硬件要求
- 树莓派5
- 亚博智能16路舵机驱动板 (I2C地址: 0x2D)
- 舵机 (支持所有度数舵机)

## ⚙️ 安装
使用[uv](https://github.com/astral-sh/uv)进行Python环境管理：
```bash
# 创建虚拟环境
uv venv .venv
source .venv/bin/activate

# 同步安装依赖 (推荐)
uv sync

# 或使用传统安装方式
uv pip install -e .
```

## 🚀 快速开始
```python
from servo_controller_library import ServoController, Easing

# 初始化控制器
controller = ServoController(board_address=0x2D)

# 配置舵机
servo1 = controller.setup_servo(1, max_angle=180)
servo2 = controller.setup_servo(2, max_angle=270, min_safe_percent=10, max_safe_percent=90)

# 执行初始化自检
controller.run_initialization_sequence()

# 单舵机控制
servo1.move_to(75, duration=1.5)  # 阻塞式移动
servo2.move_to_async(25, duration=2)  # 非阻塞移动

# 舵机编组控制
from servo_controller_library import ServoGroup
group = ServoGroup(pan=servo1, tilt=servo2)
group.move_to_pose({'pan': 50, 'tilt': 75}, duration=2)
```

## 📚 API参考

### `ServoController`
| 方法 | 参数 | 描述 |
|------|------|------|
| `setup_servo(servo_num, **kwargs)` | `max_angle=180`, `min_safe_percent=0`, `max_safe_percent=100` | 配置舵机参数并返回ServoHandle |
| `run_initialization_sequence(duration_per_move=1.5)` | - | 执行自检序列 (归中→最小→最大→归中) |
| `cleanup()` | - | 关闭I2C总线连接 |

### `ServoHandle`
| 方法 | 描述 |
|------|------|
| `move_to(target, duration, steps=100, easing_func=Easing.ease_in_out_quad)` | 阻塞式平滑移动 |
| `move_to_async(...)` | 非阻塞移动，支持完成回调 |
| `queue_move(target, duration, easing_func, on_complete)` | 添加动作到指令队列 |
| `start_sequence()` | 启动后台线程执行队列指令 |

### `ServoGroup`
| 方法 | 描述 |
|------|------|
| `move_to_pose(pose_dict, duration, easing_func)` | 协同控制多舵机到指定姿态 |
| `wait_for_move()` | 等待所有舵机完成移动 |

### `Easing` 缓动函数
- `linear`: 线性运动
- `ease_in_out_quad`: 二次缓入缓出
- `ease_in_out_cubic`: 三次缓入缓出
- `ease_out_bounce`: 弹跳效果

## 🧪 示例应用
完整示例见 [servo_demostration.ipynb](servo_demostration.ipynb)，包含：
1. 初始化与自检
2. 平滑移动控制
3. 异步操作与回调
4. 动作队列编排
5. 舵机编组协同控制

## 🤝 贡献指南
欢迎通过Pull Request贡献代码：
1. Fork本仓库
2. 创建功能分支 (`git checkout -b feature/your-feature`)
3. 提交更改 (`git commit -am 'Add some feature'`)
4. 推送到分支 (`git push origin feature/your-feature`)
5. 创建Pull Request

## 📜 许可证
本项目采用 [MIT License](LICENSE)
