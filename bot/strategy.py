"""策略接口。

协议层（game.py）只把「当前局面视图」交给策略、把策略返回的动作提交给服务器，
不包含任何牌技判断。实现 Strategy 即可接入（当前唯一实现：bot/speed.py SpeedA）。

动作格式与对局 API 一致（服务端纯验证，非法 409）：
    {"action": "discard|chi|peng|gang|hu|pass", "tile": "1w", "tiles": [...]}
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class Strategy(ABC):
    """对局策略接口。decide 每次被调用都应尽快返回（服务端有超时兜底）。"""

    @abstractmethod
    def decide(self, view):
        """给定本人视角局面视图（见 bot/model.snap_view 输出），返回动作 dict 或 None。

        - None：本回合无可提交动作（非本人回合/窗口，或主动不响应）。
        - draw 且轮到我：可返回 discard/hu/gang；
        - response_ 窗口且有响应权：可返回 chi/peng/gang/pass。
        """
        raise NotImplementedError
