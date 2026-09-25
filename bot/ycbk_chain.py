# -*- coding: utf-8 -*-
"""`bot/ycbk_chain.py` —— **役 3→役 5 候选链的 YouCaiBiKao=true 保险孪生**（R1502）。

## 为什么必须有这个文件

接入指南 §1.6：`YouCaiBiKao`（有财必拷响 = 手上**有白**时不许平胡，只能爆头/杠开/链）**每场可不同**，
以 `/rules` 为准。而 `tools/rules_guard.py` 会在**上线那一刻**比对"赛事 config ↔ 将要上场的臂"：
不一致 ⇒ `_switch_to_official.ps1` 直接 throw ⇒ **上不了线**。

在 R1502 之前，仓库里只有 4 个孪生（`speedvalueycbk` / `speedgangtakefixedycbk` /
`speedmeldmore0chiycbk` / `speedmeldtol2chiycbk`），而**役 3→役 5 判词链上的臂一根都没有**
（`speedvaluebc` / `speedvaluebaotouv5` / `speedvaluebcmeldp45` / `speedvaluebaotouvmeld` /
`speedvaluebcvmeld` / `speedvaluemeld*` / `speedc151`）。后果是：**若正式赛 `YouCaiBiKao=true`，
我们十天选出来的那根赢家臂根本不能部署**，唯一逃生阀是退回 `speedvalueycbk` —— 等于把优化成果丢掉。
`_final_event_ready.py` 的注释（R1463）当时就写明了这个窘境。

## 做法（与既有孪生完全同构，不新增任何策略逻辑）

`FastYCBKMixin`（`bot/ycbk_fast.py`）提供两半：
  * `GOD_MELD = False` ⇒ 白不再充当顺刻的搭子，选择器自然转向"4 副露 + 单张白"= 爆头路线；
  * `YOU_CAI_BI_KAO = True` + `decide()` 包装 ⇒ **拒绝宣一个会被 409 掐掉的平胡**，改为继续打（含弃牌钩子）。

本文件只是把这两半**多继承**到链上每根臂上，剂量档（`claim_p`）与母臂保持一致（否则"孪生"就不是同一个策略了）。

## 使用纪律（和既有孪生一样）

孪生**只在显式选中时才被用到** ⇒ 不影响任何现有臂、也不影响正在跑的 A/B；
阶梯是 `YouCaiBiKao=false`，孪生在那上面会**错误拦掉合法平胡** ⇒ **不要**拿它跑阶梯 A/B，
它的验证路径是**单测（`tests/test_ycbk_twins.py`）+ rules_guard**。
上线判据只有一条：`python -X utf8 tools/rules_guard.py --strategy <arm> --token-file <TOK>`
返回 **2（= 需换闸门臂）** 时才换孪生。
"""
from __future__ import annotations

from .speedc151 import SpeedC151
from .speedvaluebaotouv import SpeedValueBaotouV5
from .speedvaluebaotouvmeld import SpeedValueBaotouVMeld
from .speedvaluebc import SpeedValueBC
from .speedvaluebcmeld import SpeedValueBCMeld
from .speedvaluebcv import SpeedValueBCV
from .speedvaluebcvmeld import SpeedValueBCVMeld
from .speedvaluemeld import SpeedValueMeld
from .ycbk_fast import FastYCBKMixin


class SpeedC151YCBK(FastYCBKMixin, SpeedC151):
    """`speedc151`（役 2 基线）的 YCBK 孪生。"""

    def __init__(self, name="speedc151ycbk"):
        super().__init__(name)


class SpeedValueBCYCBK(FastYCBKMixin, SpeedValueBC):
    """`speedvaluebc`（役 3 候选 A）的 YCBK 孪生。"""

    def __init__(self, name="speedvaluebcycbk"):
        super().__init__(name)


class SpeedValueBCVYCBK(FastYCBKMixin, SpeedValueBCV):
    """`speedvaluebcv`（役 4 的 V 轴挂 BC 基线）的 YCBK 孪生。"""

    def __init__(self, name="speedvaluebcvycbk"):
        super().__init__(name)


class SpeedValueBCMeldYCBK(FastYCBKMixin, SpeedValueBCMeld):
    """`speedvaluebcmeld`（BC + 学习副露）的 YCBK 孪生。"""

    def __init__(self, name="speedvaluebcmeldycbk"):
        super().__init__(name)


class SpeedValueBCMeldP45YCBK(FastYCBKMixin, SpeedValueBCMeld):
    """`speedvaluebcmeldp45`（役 4 A 行候选，剂量对齐 0.45）的 YCBK 孪生。"""

    def __init__(self, name="speedvaluebcmeldp45ycbk"):
        super().__init__(name, claim_p=0.45)


class SpeedValueBCVMeldYCBK(FastYCBKMixin, SpeedValueBCVMeld):
    """`speedvaluebcvmeld`（三层部署臂 BC+V+副露）的 YCBK 孪生。"""

    def __init__(self, name="speedvaluebcvmeldycbk"):
        super().__init__(name)


class SpeedValueBCVMeldP40YCBK(FastYCBKMixin, SpeedValueBCVMeld):
    """`speedvaluebcvmeldp40`（役 5 组合臂，剂量 0.40）的 YCBK 孪生。"""

    def __init__(self, name="speedvaluebcvmeldp40ycbk"):
        super().__init__(name, claim_p=0.40)


class SpeedValueBCVMeldP35YCBK(FastYCBKMixin, SpeedValueBCVMeld):
    """`speedvaluebcvmeldp35`（役 5 组合臂，剂量 0.35）的 YCBK 孪生。"""

    def __init__(self, name="speedvaluebcvmeldp35ycbk"):
        super().__init__(name, claim_p=0.35)


class SpeedValueMeldYCBK(FastYCBKMixin, SpeedValueMeld):
    """`speedvaluemeld`（NONE 行的副露轴）的 YCBK 孪生。"""

    def __init__(self, name="speedvaluemeldycbk"):
        super().__init__(name)


class SpeedValueMeldP45YCBK(FastYCBKMixin, SpeedValueMeld):
    """`speedvaluemeldp45`（NONE 行役 4 候选，剂量 0.45）的 YCBK 孪生。"""

    def __init__(self, name="speedvaluemeldp45ycbk"):
        super().__init__(name, claim_p=0.45)


class SpeedValueMeldP40YCBK(FastYCBKMixin, SpeedValueMeld):
    """`speedvaluemeldp40`（NONE 行剂量 0.40）的 YCBK 孪生。"""

    def __init__(self, name="speedvaluemeldp40ycbk"):
        super().__init__(name, claim_p=0.40)


class SpeedValueBaotouV5YCBK(FastYCBKMixin, SpeedValueBaotouV5):
    """`speedvaluebaotouv5`（役 3 候选 B）的 YCBK 孪生。"""

    def __init__(self, name="speedvaluebaotouv5ycbk"):
        super().__init__(name)


class SpeedValueBaotouVMeldYCBK(FastYCBKMixin, SpeedValueBaotouVMeld):
    """`speedvaluebaotouvmeld`（役 4 B 行候选 = V 基线 + 学习副露）的 YCBK 孪生。"""

    def __init__(self, name="speedvaluebaotouvmeldycbk"):
        super().__init__(name, claim_p=0.45)