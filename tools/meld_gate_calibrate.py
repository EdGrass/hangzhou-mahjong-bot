# -*- coding: utf-8 -*-
"""~~meld_gate_calibrate~~ —— **已退役（2026-09-17 12:0x）**，保留记录，拒绝运行。

原始意图：把候选副露门控放到与 `tools/meld_acceptance.py` **同一个分母**上量，
好回答"c156 到底落在 60.0% 的哪个位置"。

**为什么退役：没通过保真度校验，而且是往"看起来合理"的方向错。**
自校验做法 = 只看 `speedtugc` 打过的房，用同一策略在同一批重建窗口上回放：

    | | 实际（房里真发生） | 模拟（重建窗口上 decdie） |
    |---|---|---|
    | 接受率 | **40.2%** | **56.8%** |

差 **16.6pp**。根因：**我构造的窗口不是 bot 真实被问到的窗口集合**。
门户一个 `a_xxx_r1_b0_t0.json` 里有 **18 个 block**、对应 dec 有 **229 条 response 记录**，
两者并非一一对应 ⇒ 模拟侧把"规则上够资格、但服务端根本没问"的窗口也算成了拒绝/接受。

（顺带说明：这条路也排除了"手牌重建失真"这个解释——把重建修到弃牌前长度保真度
 99.2% 之后，16.6pp 的差距**纹丝不动**，所以问题是**窗口集合的定义**，不是手牌。）

⇒ **标定副露门控只能用两个已验证口径，且两者分母不同、不可相减**：
  1. 臂间比较：`tools/offline_replay.py`（在我方**真实被问到**的 dec 窗口上回放，同窗配对）；
  2. 我方 vs 强者：`tools/meld_acceptance.py`（两侧同码，可比）。

本文件不再产生任何数字。若将来要重做，正确起点是**以 dec 的 `response_*` 记录为窗口集合**，
再想办法把强者也投到同一批窗口上（或用能对齐 block 的事件流）。
"""
from __future__ import annotations
import sys

MSG = ("meld_gate_calibrate 已于 2026-09-17 退役：未通过保真度校验"
       "（同策略 实际 40.2% vs 模拟 56.8%），原因见文件头 docstring。\n"
       "请改用 tools/offline_replay.py（臂间）或 tools/meld_acceptance.py（vs 强者）。")


def main():
    print(MSG, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
