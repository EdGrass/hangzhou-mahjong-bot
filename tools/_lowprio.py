"""_lowprio.py —— 离线分析用的**自降优先级**助手（Windows，纯 stdlib）。

为什么需要（§9.30 事故）：实盘 A/B 期间跑重离线任务会与 bot 抢 CPU，
曾造成一次 **4.4s 出牌超窗**（服务端替我们打最右一张）。

用法（在任何离线分析脚本**最开头**调用）：
    import sys; sys.path.insert(0, 'tools')
    from _lowprio import lower
    lower()                 # 把本进程降到 BelowNormal；失败也不报错
    lower(idle=True)        # 降到 Idle（最保守）

⚠ **优先级只解决 CPU 争用，不解决内存**：重任务仍须**分块处理**，别像 §9.30 那样一次吃 5.2GB。
"""
from __future__ import annotations
import sys

BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
IDLE_PRIORITY_CLASS = 0x00000040
NORMAL_PRIORITY_CLASS = 0x00000020


def lower(idle: bool = False) -> bool:
    """把当前进程优先级降到 BelowNormal（或 Idle）。返回是否成功。"""
    if not sys.platform.startswith('win'):
        return False
    try:
        import ctypes
        k = ctypes.windll.kernel32
        k.GetCurrentProcess.restype = ctypes.c_void_p          # ⚠ 64 位句柄必须显式声明
        k.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        k.SetPriorityClass.restype = ctypes.c_int
        h = k.GetCurrentProcess()
        cls = IDLE_PRIORITY_CLASS if idle else BELOW_NORMAL_PRIORITY_CLASS
        return bool(k.SetPriorityClass(h, cls))
    except Exception:
        return False


def current_class() -> int | None:
    if not sys.platform.startswith('win'):
        return None
    try:
        import ctypes
        k = ctypes.windll.kernel32
        k.GetCurrentProcess.restype = ctypes.c_void_p
        k.GetPriorityClass.argtypes = [ctypes.c_void_p]
        k.GetPriorityClass.restype = ctypes.c_uint32
        return int(k.GetPriorityClass(k.GetCurrentProcess()))
    except Exception:
        return None


if __name__ == '__main__':
    ok = lower()
    print('lower() =', ok, ' 当前 PriorityClass =', hex(current_class() or 0),
          '（BelowNormal=0x4000 / Idle=0x40 / Normal=0x20）')
