"""策略接口与骨架期示例策略。

**这是后续接入真实牌技的唯一接触面**：协议层（game.py）只负责把「当前局面视图」
交给策略、把策略返回的动作提交给服务器，不包含任何牌技判断。

替换方式：实现 Strategy 接口（或子类化 NaiveStrategy 重写 decide），
在 run_bot.py 里把 strategy 传进去即可，协议层无需改动。

动作格式与对局 API 一致（服务端纯验证，非法 409）：
    {"action": "discard|chi|peng|gang|hu|pass", "tile": "1w", "tiles": [...]}
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from .model import my_turn, window_pending


class Strategy(ABC):
    """对局策略接口。decide 每次被调用都应尽快返回（服务端有超时兜底）。"""

    @abstractmethod
    def decide(self, view):
        """给定本人视角局面视图（见 bot/model.snap_view 输出），返回动作 dict 或 None。

        - None：本回合无可提交动作（非本人回合/窗口，或主动不响应）。
        - draw 且轮到我：可返回 discard/hu/gang（骨架期请勿返回非法动作，
          如抓打圈 catch_play 只能 discard 刚摸的牌）。
        - response_ 窗口且有响应权：可返回 chi/peng/gang/pass。
        """
        raise NotImplementedError


class NaiveStrategy(Strategy):
    """骨架期示例策略（等价指南最小 Bot，无任何牌技）：

    - 摸牌后出牌：抓打圈只出刚摸的牌，否则出手牌第一张；
    - 碰/吃/明杠窗口一律过（pass）；
    - 从不主动提交 hu —— 若真能胡，由服务端出牌思考超时「自动胡」兜底
      （本策略每次都秒回 discard，故实际不会触发自动胡；积分损失可接受，
      本阶段只验证协议链路）。
    """

    def __init__(self, name="naive"):
        self.name = name

    def decide(self, view):
        if my_turn(view):
            # 摸牌后行动权
            if view["god"]["catch_play"] and view["drawn_tile"]:
                # 抓打圈：只能打出刚摸到的牌（打财神后的那一圈限制）
                return {"action": "discard", "tile": view["drawn_tile"]}
            if view["my_hand"]:
                # 出牌打第一张（无策略）
                return {"action": "discard", "tile": view["my_hand"][0]}
            return None
        if window_pending(view):
            # 响应窗口（碰/吃/明杠）：一律过
            return {"action": "pass", "tile": ""}
        return None
