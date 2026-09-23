"""bot/meldtrack —— 真机协议侧的本人副露跟踪（MeldTracker）。

服务器快照不含 melds 明细（模拟器扩展键仅本地有），但 speedA 等策略需要
exposed(面子数 e) 与 gangs(杠数 g) 来：
  - 判胡（hu.is_win(hand, exposed, gangs) 长度基准 14-3e-g）
  - 向听基准 need = 4-e
本模块在协议层按【自己提交成功的动作】累计 e/g：
  - peng/chi/直杠成功 → 新面子 e+1（直杠另 g+1）
  - 摸牌回合 gang（暗杠/补杠）→ 由 tile 是否命中已有碰组区分：
      补杠：面子不变、g+1；暗杠：e+1、g+1
局限：服务端未知的重置/撤销边缘（崩溃重赛等）会造成漂移——以 seq=0 重建后
不清零，待测试房间 E2E 校准字段语义（文档记录）。
"""
from __future__ import annotations


class MeldTracker:
    def __init__(self):
        self._melds = []          # [{type: peng|chi|gang, tile}]

    def reset(self):
        self._melds = []

    def record_action(self, action, committed=True):
        """protocol game 层在动作提交成功(或 409 说明早已成功?)后调用。
        committed=False 时忽略（调用方在提交前不能预记）。"""
        if not committed:
            return
        a = (action or {}).get("action")
        tile = (action or {}).get("tile") or ""
        if a == "peng":
            self._melds.append({"type": "peng", "tile": tile})
        elif a == "chi":
            self._melds.append({"type": "chi", "tile": tile})
        elif a == "gang":
            # 命中已有碰组 → 补杠；否则暗杠/直杠
            for m in self._melds:
                if m["type"] == "peng" and m["tile"] == tile:
                    m["type"] = "gang"
                    return
            self._melds.append({"type": "gang", "tile": tile})
        # discard/hu/pass 不动 e/g

    # -- 视图 ---------------------------------------------------------------
    def exposed(self):
        return len(self._melds)

    def gangs(self):
        return sum(1 for m in self._melds if m["type"] == "gang")

    def view_extra(self):
        """注入 strategy view 的键（与模拟器 view 同构的 melds 语义）。"""
        melds = [{"type": m["type"], "tile": m["tile"]} for m in self._melds]
        return {"melds": melds}
