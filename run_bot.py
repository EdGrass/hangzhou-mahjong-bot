"""CLI 入口：运行 bot 或免认证冒烟自检。

用法：
    python run_bot.py --smoke [--server URL]            免认证冒烟（版本自检 + fan-calc）
    python run_bot.py <参赛令牌> [锦标赛id] [--server URL]   完整协议循环

- 报名令牌（门户「报名」/「测试房间」派发）：自动发现锦标赛，无需锦标赛 id；
- 全局令牌（门户「我的 AI 身份」签发，v24 起须门户绑定）：必须显式带锦标赛 id。
- 服务器地址：默认 https://10.240.169.190:18080；可用 --server 或环境变量 HM_SERVER 覆盖。
"""
from __future__ import annotations

import argparse
import sys
import time

import bot  # noqa: F401  （触发 __init__，含版本常量）
from bot.api import ApiError, Client
from bot.protocol import run_tournament
from bot.smoke import run_smoke
from bot.speed import SpeedBase, SpeedCore  # noqa: F401（引擎父类）
from bot.warmup import warmup_strategy
from bot.util import ensure_utf8, log, server_from_env  # noqa: F401

# 实盘策略：唯一竞技策略 SpeedE（孤字优先/副露收益，见 bot/speede.py）。
# 实验变体（speedx*/speedh/probe*）经 L1/L2/窗口 A/B 判定后移除（防重登记见
# docs/iter/queue.md + reports/）；协议层自杠机器与窗口审计工具链保留。
STRATEGY_FACTORIES = {
    "speedE": lambda: __import__("bot.speede", fromlist=["SpeedE"]).SpeedE(),
    "speedk": lambda: __import__("bot.speedk", fromlist=["SpeedK"]).SpeedK(),
    "speedu": lambda: __import__("bot.speedu", fromlist=["SpeedU"]).SpeedU(),
    "speedv": lambda: __import__("bot.speedv", fromlist=["SpeedV"]).SpeedV(),
    "speedp": lambda: __import__("bot.speedp", fromlist=["SpeedP"]).SpeedP(),
    "speedm": lambda: __import__("bot.speedm", fromlist=["SpeedM"]).SpeedM(),
    "speedt": lambda: __import__("bot.speedt", fromlist=["SpeedT"]).SpeedT(),
    "speedtm": lambda: __import__("bot.speedtm", fromlist=["SpeedTM"]).SpeedTM(),
    "speedw": lambda: __import__("bot.speedw", fromlist=["SpeedW"]).SpeedW(),
    "speedwm": lambda: __import__("bot.speedwm", fromlist=["SpeedWM"]).SpeedWM(),
    "speedtqm": lambda: __import__("bot.speedtqm", fromlist=["SpeedTQM"]).SpeedTQM(lead=1),
    "speedtp": lambda: __import__("bot.speedtp", fromlist=["SpeedTP"]).SpeedTP(),
    "speedtma": lambda: __import__("bot.speedtma", fromlist=["SpeedTMA"]).SpeedTMA(),
    "speedtu": lambda: __import__("bot.speedtu", fromlist=["SpeedTU"]).SpeedTU(),
    "speedtv": lambda: __import__("bot.speedtv", fromlist=["SpeedTV"]).SpeedTV(),
    "speedtug": lambda: __import__("bot.speedtug", fromlist=["SpeedTUG"]).SpeedTUG(),
    "speedtugc": lambda: __import__("bot.speedtugc", fromlist=["SpeedTUGC"]).SpeedTUGC(),
    "speedc067": lambda: __import__("bot.speedc067", fromlist=["C067Policy"]).C067Policy(
        model_path="var/c067_bc_net.pt"),
    "speedc068": lambda: __import__("bot.speedc068", fromlist=["C068Policy"]).C068Policy(
        model_path="var/c068_bc_net.pt"),
    "speedc068lo0": lambda: __import__("bot.speedc068", fromlist=["C068Policy"]).C068Policy(
        model_path="var/c068_bc_lo0_net.pt", lo=0, hi=2),
    "speedc073w2": lambda: __import__("bot.speedc068", fromlist=["C068Policy"]).C068Policy(
        model_path="var/c073_orig_w2_net.pt", lo=0, hi=2),
    "speedc073w4": lambda: __import__("bot.speedc068", fromlist=["C068Policy"]).C068Policy(
        model_path="var/c073_orig_w4_net.pt", lo=0, hi=2),
    "speedc117": lambda: __import__("bot.speedc117", fromlist=["C117Policy"]).C117Policy(
        model_path="var/c073_orig_w4_net.pt", lo=0, hi=2, cand_order="ukeire"),
    "speedc118": lambda: __import__("bot.speedc118", fromlist=["C118Policy"]).C118Policy(
        model_path="var/c073_orig_w4_net.pt", lo=0, hi=2),
    "speedc121": lambda: __import__("bot.speedc121", fromlist=["C121Policy"]).C121Policy(
        model_path="var/c073_orig_w4_net.pt", meld_path="var/c121_meld_net.pt", lo=0, hi=2, claim_p=0.60),
    "speedc117n": lambda: __import__("bot.speedc117n", fromlist=["C117NPolicy"]).C117NPolicy(),
    # C130：SpeedTUGC + 选择性 rollout（允许跨向听权衡）。**未上线**，
    # 依据见 docs/iter/reports/field-audit-20260915.md §13/§17：sim 不能排序、且搜索有延迟预算。
    "speedc130": lambda: __import__("bot.speedc130", fromlist=["C130Policy"]).C130Policy(),
    # C131：speedtugc 的单变量候选 —— 弃牌搜索里白板不补面子（保留作万能听 → 爆头形）。
    # 目标层：持白局（占局数 ~51%、却吃掉 ~85% 的得分差距）。
    "speedc131": lambda: __import__("bot.speedc131", fromlist=["SpeedC131"]).SpeedC131(),
    # C132：speedtugc 的单变量候选 —— 非听牌段并列时改按 **live 进张(ukeire)** 排序
    # （基线在未听牌段完全不看进张，离线审计落后最优进张 4.99 张）
    "speedc132": lambda: __import__("bot.speedc132", fromlist=["SpeedC132"]).SpeedC132(),
    # C135：speedtugc 的单变量候选 —— 未听牌段并列改按**真进张**（bot/ukeire.py）打破
    # （与已作废的 c117/c132 的区别：那两个用的是"邻接张数"代理，不看向听）
    "speedc135": lambda: __import__("bot.speedc135", fromlist=["SpeedC135"]).SpeedC135(),
    # ★ 2026-09-20（R753）：c135 的**有界延迟版**（预登记 §1bis；40ms 预算 + 超预算回退基线）
    "speedc135d": lambda: __import__("bot.speedc135d", fromlist=["SpeedC135D"]).SpeedC135D(budget_ms=40.0),
    # C197：c135 的**单变量**候选 —— 并列时再往前看**一步**（有界二步前瞻）。
    # 依据 R520：53.7% 的未听牌弃牌决策里"最大 1 步真进张"是并列的 ⇒ 二步信息有面；
    # 只对最小向听组、只看活张最多的前 k 个进张，带 300ms deadline（超时退回纯 u1）。
    "speedc197": lambda: __import__("bot.speedc197", fromlist=["SpeedC197"]).SpeedC197(),
    # C198：c135（真进张排序）+ **爆头形保形**（只在"可胡"点生效；见 bot/speedc198.py 与 R526/R527）。
    "speedc198": lambda: __import__("bot.speedc198", fromlist=["SpeedC198"]).SpeedC198(),
    # C200：c135 + "两摸内和了期望"（待ち宽度进目标函数；见 R543 / bot/speedc200.py）。
    "speedc200": lambda: __import__("bot.speedc200", fromlist=["SpeedC200"]).SpeedC200(),
    # C201：c135 + 両面优先并列键（见 bot/speedc201.py / R544）。
    "speedc201": lambda: __import__("bot.speedc201", fromlist=["SpeedC201"]).SpeedC201(),
    # C202：c135 + 加权"両面数"（λ 由 C202_LAMBDA 控制，见 R545）。
    "speedc202": lambda: __import__("bot.speedc202", fromlist=["SpeedC202"]).SpeedC202(),
    # C203：c135 + **带宽**式"待ち形状优先"（DELTA 由 C203_DELTA 控制，见 R545）。
    "speedc203": lambda: __import__("bot.speedc203", fromlist=["SpeedC203"]).SpeedC203(),
    # C205：s=1 时改用"两摸和了期望"V1（和了导向目标；见 R543/R548）。
    "speedc205": lambda: __import__("bot.speedc205", fromlist=["SpeedC205"]).SpeedC205(),
    # C206：s=1 且手上有白时，按"爆头导向的 V1"（白→任意牌听的转化）排序（见 R550）。
    "speedc206": lambda: __import__("bot.speedc206", fromlist=["SpeedC206"]).SpeedC206(),
    # C207：c135 + 爆头可达性值函数 V（加权主项，见 R550/R559）。
    "speedc207": lambda: __import__("bot.speedc207", fromlist=["SpeedC207"]).SpeedC207(),
    # C208：c152 + 可胡点上用爆头值函数 V 追加弃胡（见 R563）。
    "speedc208": lambda: __import__("bot.speedc208", fromlist=["SpeedC208"]).SpeedC208(),
    # C136：speedtugc 的单变量候选 —— 副露门控改为**质量感知**
    # （向听不变但吃/碰后"真进张"变多 ⇒ 也接受；实测这类占可副露窗口的 23%、77% 确实变好且平均 +14.9 张）
    "speedc136": lambda: __import__("bot.speedc136", fromlist=["SpeedC136"]).SpeedC136(),
    # C141：speedtugc 的单变量候选 —— 把**财飘**（爆头态弃白 = 链 +1 再 ×2）计进弃胡判据。
    # 现状缺失：_best_giveup 用**弃牌前**的 chain 估爆头番 ⇒ 弃白档被低估 2 倍
    # （真机语料：新增 57 个弃胡窗口/23,541 局 ≈ 0.19 次/房，全场 103 次财飘胡、我方 0 次）
    "speedc141": lambda: __import__("bot.speedc141", fromlist=["SpeedC141"]).SpeedC141(),
    # 注：**没有**"BC 模型 + c135"这一档 —— 两者都是**弃牌选择**机制（BC 直接接管弃牌，
    # c135 只在最小向听并列里改次序）⇒ 叠加时 c135 实际上被模型路径旁路、等于没加。
    # 采用 c073w4 时的正确臂是 speedc147（BC + 四条非弃牌机制）。
    # C150：**全机制束** = C146（明杠+自杠+吃碰+财飘）+ C135（真进张并列出牌）
    # 依据 R135 量级下调后重估：杠支线只有 +0.5~3 分/房，需要 c135 把束做大以提高可判定性。
    "speedc150": lambda: __import__("bot.speedc150", fromlist=["SpeedC150"]).SpeedC150(),
    "speedc151": lambda: __import__("bot.speedc151", fromlist=["SpeedC151"]).SpeedC151(),
    # registered by var/_prep_next_campaign.py at T-6h
    "speedvalue": lambda: __import__("bot.speedvalue", fromlist=["SpeedValue"]).SpeedValue(),
    # ★ R1332：**YouCaiBiKao=true 的保险孪生**（`bot/ycbk_twins.py`，原本只有类、**未注册**）。
    #   规则（见 tools/rules_guard.py）：若赛事 config 把 YouCaiBiKao 置 **true**，
    #   普通臂的白-平胡（占我方胡牌 64.4%）会被 **409** 拒 ⇒ 必须换带“合法胡闸门”的孪生臂。
    #   判定：`python -X utf8 tools/rules_guard.py --strategy <arm> --token-file <TOK>` 返回 **2 = 需换闸门臂**。
    #   它们**只在显式 `--strategy` 选中时才被用到** ⇒ 不影响任何现有臂与当前 A/B。
    "speedvalueycbk": lambda: __import__("bot.ycbk_twins", fromlist=["SpeedValueYCBK"]).SpeedValueYCBK(),
    "speedgangtakefixedycbk": lambda: __import__("bot.ycbk_twins", fromlist=["SpeedGangTakeFixedYCBK"]).SpeedGangTakeFixedYCBK(),
    "speedmeldmore0chiycbk": lambda: __import__("bot.ycbk_twins", fromlist=["SpeedMeldMore0ChiYCBK"]).SpeedMeldMore0ChiYCBK(),
    "speedmeldtol2chiycbk": lambda: __import__("bot.ycbk_twins", fromlist=["SpeedMeldTol2ChiYCBK"]).SpeedMeldTol2ChiYCBK(),
    # C2xx 弃胡 EV 修正（2026-09-23）：p_conv 随河长衰减 / 再叠失败负项。
    # 两个臂是**阶梯式单变量**：p 轴（vs speedvalue）→ loss 轴（vs ...riverp）。
    "speedgiveupriverp": lambda: __import__(
        "bot.speedgiveupriver", fromlist=["SpeedGiveupRiverP"]).SpeedGiveupRiverP(),
    "speedgiveupriver": lambda: __import__(
        "bot.speedgiveupriver", fromlist=["SpeedGiveupRiver"]).SpeedGiveupRiver(),
    # 役 3 杠束（单变量：c151 + 明杠接受 + 杠后弃牌 P0 修复）
    "speedgangtakec151fixed": lambda: __import__(
        "bot.speedgangtakec151fixed",
        fromlist=["SpeedGangTakeC151Fixed"]).SpeedGangTakeC151Fixed(),
    # 役 3 候选（据 §F2/今晚复算：听牌率 −6.44pp 是最大缺口；本臂修"副露后把增益扔掉"）
    "speedmeldpost": lambda: __import__(
        "bot.speedmeldpost", fromlist=["SpeedMeldPost"]).SpeedMeldPost(),
    "speedvaluepost": lambda: __import__(
        "bot.speedvaluepost", fromlist=["SpeedValuePost"]).SpeedValuePost(),
    # ★ R1264 叠加臂（顺序组合）：V 先进基线选择，BC 再按自己的 margin 覆盖。
    #    用途：**若役 3 采用 speedvaluebc**，役 4 的 V 轴必须挂在新基线上（否则是复合臂）。
    "speedvaluebcv": lambda: __import__(
        "bot.speedvaluebcv", fromlist=["SpeedValueBCV"]).SpeedValueBCV(),
    "speedvaluebc": lambda: __import__(
        "bot.speedvaluebc", fromlist=["SpeedValueBC"]).SpeedValueBC(),
    "speedc151bc": lambda: __import__(
        "bot.speedc151bc", fromlist=["SpeedC151BC"]).SpeedC151BC(),
    "speedvaluerank": lambda: __import__(
        "bot.speedvaluerank", fromlist=["SpeedValueRank"]).SpeedValueRank(),
    "speedvalueplain": lambda: __import__(
        "bot.speedvalueplain", fromlist=["SpeedValuePlain"]).SpeedValuePlain(),
    # ★ R1290：三层堆叠的**部署臂**（BC + 爆头 V + 学习副露 0.45）——**不做判词**，
    #    仅在"三条单轴都被判正"时作为正式赛最强配置参与 §V.44/§V.66 的选臂。
    "speedvaluebcvmeld": lambda: __import__(
        "bot.speedvaluebcvmeld", fromlist=["SpeedValueBCVMeld"]).SpeedValueBCVMeld(),
    # ★ R1411：剂量对齐的三层部署臂（BC + V + 学习副露）——
    #   若役 4 说副露激进档更好，最终臂就必须是“同剂量”的三层组合，而不是固定 0.45。
    "speedvaluebcvmeldp40": lambda: __import__(
        "bot.speedvaluebcvmeld", fromlist=["SpeedValueBCVMeld"]).SpeedValueBCVMeld(claim_p=0.40),
    "speedvaluebcvmeldp35": lambda: __import__(
        "bot.speedvaluebcvmeld", fromlist=["SpeedValueBCVMeld"]).SpeedValueBCVMeld(claim_p=0.35),
    # ★ R1278：BC 分支的役 4 候选 = 组合臂 + **对齐剂量**（claim_p=0.45，与 §V.35 的单轴剂量一致）
    #    为什么不是默认的 0.60：§V.35 已量到 0.60 只补 ~一半副露缺口（+10.5% vs 需要 ~+20%）。
    "speedvaluebcmeldp45": lambda: __import__(
        "bot.speedvaluebcmeld", fromlist=["SpeedValueBCMeld"]).SpeedValueBCMeld(claim_p=0.45),
    "speedvaluebcmeld": lambda: __import__(
        "bot.speedvaluebcmeld", fromlist=["SpeedValueBCMeld"]).SpeedValueBCMeld(),
    # ★ R1241：`bot/speedvalue.py` 里**早就写好**的 V 项消融/剂量类（此前**全部未注册**）
    "speedvaluenofan": lambda: __import__("bot.speedvalue", fromlist=["SpeedValueNoFan"]).SpeedValueNoFan(),
    "speedvaluenobai": lambda: __import__("bot.speedvalue", fromlist=["SpeedValueNoBai"]).SpeedValueNoBai(),
    "speedvaluenolive": lambda: __import__("bot.speedvalue", fromlist=["SpeedValueNoLive"]).SpeedValueNoLive(),
    "speedvaluefan2": lambda: __import__("bot.speedvalue", fromlist=["SpeedValueFan2"]).SpeedValueFan2(),
    "speedvalueflatuke": lambda: __import__("bot.speedvalue", fromlist=["SpeedValueFlatUkeire"]).SpeedValueFlatUkeire(),
    # ★ R1240 剂量档：BC 网只在"分数优势 > margin"时才改牌（margin 由 Δ分数分布定：p50/p75/p90）
    "speedvaluebcm093": lambda: __import__(
        "bot.speedvaluebc", fromlist=["SpeedValueBC"]).SpeedValueBC(margin=0.93),
    "speedvaluebcm167": lambda: __import__(
        "bot.speedvaluebc", fromlist=["SpeedValueBC"]).SpeedValueBC(margin=1.67),
    "speedvaluebcm238": lambda: __import__(
        "bot.speedvaluebc", fromlist=["SpeedValueBC"]).SpeedValueBC(margin=2.38),
    "speedvaluemeld": lambda: __import__(
        "bot.speedvaluemeld", fromlist=["SpeedValueMeld"]).SpeedValueMeld(),
    # ★ R1247 剂量档：`SpeedValueMeld` 的 `claim_p`（学习副露网的**加索取阈值**，越低越激进）
    #    动机：同房头对头实测我们 **副露/轮 少 ~17%**（0.297 vs 同桌 0.357，R1245/R1246）；
    #    默认 0.60 只补 +7.2pp 索取率（67.7%→74.9%），补不满 ⇒ 需要一支"刚好补上量差"的档。
    "speedvaluemeldp50": lambda: __import__(
        "bot.speedvaluemeld", fromlist=["SpeedValueMeld"]).SpeedValueMeld(claim_p=0.50),
    "speedvaluemeldp45": lambda: __import__(
        "bot.speedvaluemeld", fromlist=["SpeedValueMeld"]).SpeedValueMeld(claim_p=0.45),
    "speedvaluemeldp40": lambda: __import__(
        "bot.speedvaluemeld", fromlist=["SpeedValueMeld"]).SpeedValueMeld(claim_p=0.40),
    "speedvaluemeldp35": lambda: __import__(
        "bot.speedvaluemeld", fromlist=["SpeedValueMeld"]).SpeedValueMeld(claim_p=0.35),
    # ★ R1279：V 分支的役 4 候选 = V 基线 + 学习副露（对齐剂量 0.45）
    #    仅当役 3 判词为"BC 不采用、V 采用"时使用（re-basing 规则：必须挂在新基线 speedvaluebaotouv5 上）。
    "speedvaluebaotouvmeld": lambda: __import__(
        "bot.speedvaluebaotouvmeld", fromlist=["SpeedValueBaotouVMeld"]).SpeedValueBaotouVMeld(),
    # ★ R1275 前瞻搜索族（**独立机制**：不用学习网，用"下一摸宽度期望"打分）
    #     `speedlookahead_anytime` 修掉了父类"全局 deadline 一到整手返回 None ⇒ 静默回退"的缺陷
    #     （改成逐候选配额 + 基准优先 + 返回部分结果）。生产口径实测改动率 13.0% cold / 17.0% warm。
    #     ⚠ 延迟风险：父类全局 deadline 250ms/决策 ⇒ M=10 并发下必须过 `_m10_latency_gate` 才能排役。
    "speedlookaheadanytime": lambda: __import__(
        "bot.speedlookahead_anytime", fromlist=["SpeedLookaheadAnytime"]).SpeedLookaheadAnytime(),
    # ★ R1255 爆头可达性 V（加权主项）：现有四轴全打"听牌率"，而 §V.36 显示分差**一半在赢分大小**
    #    （爆头/胡 22.5% vs top32 28.7%）。§V.38 判死的是**手写启发式**版；这里用**拟合值函数**
    #    （baotou_v1.pt，局级 AUC 0.771），并把它移植到 speedvalue 之上以保证单变量可归因。
    "speedvaluebaotouv5": lambda: __import__(
        "bot.speedvaluebaotouv", fromlist=["SpeedValueBaotouV5"]).SpeedValueBaotouV5(),
    "speedvaluebaotouv10": lambda: __import__(
        "bot.speedvaluebaotouv", fromlist=["SpeedValueBaotouV10"]).SpeedValueBaotouV10(),
    "speedvaluebaotouv20": lambda: __import__(
        "bot.speedvaluebaotouv", fromlist=["SpeedValueBaotouV20"]).SpeedValueBaotouV20(),
    # ★ R1251 对子保持（线性剂量）：step 版（pairr8）实测只动 3.5% 决策 ⇒ 过窄；
    #    线性版按"第 3 个以上的每个对子"给分，只要对子数不同就改排序，作用面更宽。
    "speedvaluepairlin16": lambda: __import__(
        "bot.speedvaluepairlin", fromlist=["SpeedValuePairLin16"]).SpeedValuePairLin16(),
    "speedvaluepairlin32": lambda: __import__(
        "bot.speedvaluepairlin", fromlist=["SpeedValuePairLin32"]).SpeedValuePairLin32(),
    "speedvaluepairlin64": lambda: __import__(
        "bot.speedvaluepairlin", fromlist=["SpeedValuePairLin64"]).SpeedValuePairLin64(),
    # 役 5 对子剂量档（六档：惩罚 Pair2/4、奖励 PairR2/R4/R8；均派生自 SpeedValue）
    "speedvaluepair2": lambda: __import__(
        "bot.speedvaluepairdose", fromlist=["SpeedValuePair2"]).SpeedValuePair2(),
    "speedvaluepair4": lambda: __import__(
        "bot.speedvaluepairdose", fromlist=["SpeedValuePair4"]).SpeedValuePair4(),
    "speedvaluepairr2": lambda: __import__(
        "bot.speedvaluepairdose", fromlist=["SpeedValuePairR2"]).SpeedValuePairR2(),
    "speedvaluepairr4": lambda: __import__(
        "bot.speedvaluepairdose", fromlist=["SpeedValuePairR4"]).SpeedValuePairR4(),
    "speedvaluepairr8": lambda: __import__(
        "bot.speedvaluepairdose", fromlist=["SpeedValuePairR8"]).SpeedValuePairR8(),
    # C187：有硬时限的 c151（预算内精确、超时退回基线；面向 M>10 的安全候选）
    "speedc187": lambda: __import__("bot.speedc187", fromlist=["SpeedC187"]).SpeedC187(),
    "speedc152": lambda: __import__("bot.speedc152", fromlist=["SpeedC152"]).SpeedC152(),
    "speedc209": lambda: __import__("bot.speedc209", fromlist=["SpeedC209"]).SpeedC209(),
    "speedc210": lambda: __import__("bot.speedc210", fromlist=["SpeedC210"]).SpeedC210(),
    "speedc211": lambda: __import__("bot.speedc211", fromlist=["SpeedC211"]).SpeedC211(),
    "speedc212": lambda: __import__("bot.speedc212", fromlist=["SpeedC212"]).SpeedC212(),
    "speedc213": lambda: __import__("bot.speedc213", fromlist=["SpeedC213"]).SpeedC213(),
    "speedc214": lambda: __import__("bot.speedc214", fromlist=["SpeedC214"]).SpeedC214(),
    "speedc215": lambda: __import__("bot.speedc215", fromlist=["SpeedC215"]).SpeedC215(),
    "speedc216": lambda: __import__("bot.speedc216", fromlist=["SpeedC216"]).SpeedC216(),
    "speedc217": lambda: __import__("bot.speedc217", fromlist=["SpeedC217"]).SpeedC217(),
    "speedc218": lambda: __import__("bot.speedc218", fromlist=["SpeedC218"]).SpeedC218(),
    "speedc219": lambda: __import__("bot.speedc219", fromlist=["SpeedC219"]).SpeedC219(),
    "speedc220": lambda: __import__("bot.speedc220", fromlist=["SpeedC220"]).SpeedC220(),
    "speedc221": lambda: __import__("bot.speedc221", fromlist=["SpeedC221"]).SpeedC221(),
    # C154：**庄位条件化**（c151 的单变量）—— 做庄时不再弃胡换爆头（做闲 100% 保持 c151/C036）。
    # 依据：庄位下行不对称（对手自摸我们付 8m vs 做闲多付 1m）+ 连庄；§9.29 的"无庄位专用打法"是**分解结论**、非实验。
    "speedc154": lambda: __import__("bot.speedc154", fromlist=["SpeedC154"]).SpeedC154(),
    # C155：**庄位条件化的路线项**（c151 的单变量）—— 多对子惩罚只在**做庄**时生效；
    # 做闲退回 c150（保对子/七对/爆头那一路的价值）。依据：庄位下行不对称（做庄对手自摸付 8m）+ 连庄。
    "speedc155": lambda: __import__("bot.speedc155", fromlist=["SpeedC155"]).SpeedC155(),
    # C156：**c151 + 学习到的选择性副露**（单变量：只动副露门控）—— 在质量门控之上用
    # `var/c121_meld_net.pt`（141 维窗口特征）**补一部分索取**，且**绝不否决**任何基线索取。
    # 依据：§9.66 同房同巡分层（强者 74.5% 的局有副露 vs 我们 61.0%）+ c121 旧口径（我方 36.5% vs 教师 42.2%，松门控 57~60% 真机亏）。
    "speedc156": lambda: __import__("bot.speedc156", fromlist=["SpeedC156"]).SpeedC156(),
    # C156c70：同一候选的**保守档**（阈值 0.70）—— 若 c156（0.60）的副露率冲过强玩家区间，
    # 先用这一档；闸门与 c151 完全相同，只把"额外索取"的置信门槛调高。
    "speedc156c70": lambda: __import__("bot.speedc156", fromlist=["SpeedC156"]).SpeedC156(claim_p=0.70),
    # C158：**副露侧大束** = c151（质量门控）+ c156（学习补加 0.60）+ **末盘放宽**
    # （河牌≥40 且副露后同向听、等张退化 ≤8）—— 预测把"有副露局占比"从 61.2% 推到 ~68%（强者 74.5%）。
    "speedc158": lambda: __import__("bot.speedc158", fromlist=["SpeedC158"]).SpeedC158(),
    # C159：**分时段的压对数**（c151 的单变量）—— 多对子惩罚按牌河长度调度：
    # 前 3 巡权重 0（不压，退回 c150）、4~7 巡 1.0、8 巡后 1.5。
    # 依据：本役 c151 的拆对率 T1 **9.0%** vs 强者 **2.3%**（早期过猛）、T6/T8 低于强者（后期不足）。
    "speedc159": lambda: __import__("bot.speedc159", fromlist=["SpeedC159"]).SpeedC159(),
    # C159b：同一旋钮的**加力档**（中盘 1.5、末盘 2.5）—— 依据 §9.74 正确口径：
    # 我方逐巡拆对 T2~T6（1.0/1.5/2.3/3.4/4.9%）远低于强者（2.5/4.2/6.5/8.6/10.1%）。
    "speedc159b": lambda: __import__("bot.speedc159b", fromlist=["SpeedC159B"]).SpeedC159B(),    # C163：**组合臂** = c159（分时段压对数）+ c156（学习副露补加）。
    # MRO 显式验证：_pick_discard 取 c159、_want_claim 取 c156，C036/c150 链不旁路。
    "speedc163": lambda: __import__("bot.speedc163", fromlist=["SpeedC163"]).SpeedC163(),    # C164/C165/C166：**M=10 并发安全快版**（去掉 c135 的逐候选 real_ukeire，保留路线/副露机制）。
    "speedc164": lambda: __import__("bot.speedc164", fromlist=["SpeedC164"]).SpeedC164(),
    "speedc165": lambda: __import__("bot.speedc165", fromlist=["SpeedC165"]).SpeedC165(),
    "speedc166": lambda: __import__("bot.speedc166", fromlist=["SpeedC166"]).SpeedC166(),    # C167：有界真进张（c159 的精确评分，只对轻量筛出的 top-K 候选算 real_ukeire）。
    "speedc167": lambda: __import__("bot.speedc167", fromlist=["SpeedC167"]).SpeedC167(),    # C168：时间预算版有界真进张（并发高峰自动退回轻量评分）。
    "speedc168": lambda: __import__("bot.speedc168", fromlist=["SpeedC168"]).SpeedC168(),    # C169~C172：快版 + YouCaiBiKao 合法胡闸门（true 配置专用，继承 fast 路线/副露，不引入 c135）。
    "speedc169": lambda: __import__("bot.speedc169", fromlist=["SpeedC169"]).SpeedC169(),
    "speedc170": lambda: __import__("bot.speedc170", fromlist=["SpeedC170"]).SpeedC170(),
    "speedc171": lambda: __import__("bot.speedc171", fromlist=["SpeedC171"]).SpeedC171(),
    "speedc172": lambda: __import__("bot.speedc172", fromlist=["SpeedC172"]).SpeedC172(),    # C173~C176：把 c144 明/自杠 + c141 财飘修正加回 fast 基底；c176 为 true 配置终极版。
    "speedc173": lambda: __import__("bot.speedc173", fromlist=["SpeedC173"]).SpeedC173(),
    "speedc174": lambda: __import__("bot.speedc174", fromlist=["SpeedC174"]).SpeedC174(),
    "speedc175": lambda: __import__("bot.speedc175", fromlist=["SpeedC175"]).SpeedC175(),
    "speedc176": lambda: __import__("bot.speedc176", fromlist=["SpeedC176"]).SpeedC176(),    # C177~C179：fast c136 质量门控（轻量进张代理）+ 杠/财飘；c179 为 true 配置替代终极版。
    "speedc177": lambda: __import__("bot.speedc177", fromlist=["SpeedC177"]).SpeedC177(),
    "speedc178": lambda: __import__("bot.speedc178", fromlist=["SpeedC178"]).SpeedC178(),
    "speedc179": lambda: __import__("bot.speedc179", fromlist=["SpeedC179"]).SpeedC179(),    # C180/C181：终极组合（BC 弃牌 + c136 质量副露 + c165 学习副露 + c144/c141；c181 带合法闸门）。
    "speedc180": lambda: __import__("bot.speedc180", fromlist=["SpeedC180"]).SpeedC180(),
    "speedc181": lambda: __import__("bot.speedc181", fromlist=["SpeedC181"]).SpeedC181(),    # C183/C184：终极启发式束（c164 route + c165 学习副露 + c136 质量门控 + c144/c141；c184 带合法闸门）。
    "speedc183": lambda: __import__("bot.speedc183", fromlist=["SpeedC183"]).SpeedC183(),
    "speedc184": lambda: __import__("bot.speedc184", fromlist=["SpeedC184"]).SpeedC184(),
    # C185：**真版 true 候选** —— 谱系核对后 c151/c156 才是 c146(明杠+自杠+质量副露+财飘)+c135 的真身，
    # 而 real_ukeire 尾延迟修复后真版已过 M=10 ⇒ true 配置不再需要"代理的真身"。c185 = c156 + 闸门 + 转爆头。
    "speedc185": lambda: __import__("bot.speedc185", fromlist=["SpeedC185"]).SpeedC185(),
    # C186：c156 的学习副露阈值校准版（claim_p 0.60 -> 0.50）。真机窗口扫描：1.24x -> 1.33x，
    # 曲线在 <=0.45 饱和（1.34x）⇒ 该轴天然有界，估算副露/轮 1.077 -> 1.155（强者区间 1.09~1.32）。
    "speedc186": lambda: __import__("bot.speedc186", fromlist=["SpeedC186"]).SpeedC186(),
    # C188：安全版 c186 —— 学习副露额外覆盖 + 无白且真实进张变差时否决；含白保留爆头路线。
    "speedc188": lambda: __import__("bot.speedc188", fromlist=["SpeedC188"]).SpeedC188(),
    # C190：speedtugc + 学习副露（c121）+ 无白且真实进张变差时否决；不继承 c151 家族。
    "speedc190": lambda: __import__("bot.speedc190", fromlist=["SpeedC190"]).SpeedC190(),
    # C191：c190 的进取阈值档（claim_p=0.70，命中强者副露区间上界）。
    "speedc191": lambda: __import__("bot.speedc191", fromlist=["SpeedC191"]).SpeedC191(),
    # C193：speedtugc + 仅做庄时压对数路线；做闲严格回退 speedtugc。
    "speedc193": lambda: __import__("bot.speedc193", fromlist=["SpeedC193"]).SpeedC193(),
    # C194：中盘3+对子外科式拆对（真进张损失<=4），基座speedtugc。
    "speedc194": lambda: __import__("bot.speedc194", fromlist=["SpeedC194"]).SpeedC194(),
    # ★ `speedtugc_w50`：**与 speedtugc 完全相同的打法**，只是换名字 ——
    # 供"入席秒 ↔ 同桌强度"预登记实验（A=立即入席 / B=等到秒≥50）区分两臂用（STATUS §9.87）。
    "speedtugc_w50": lambda: __import__("bot.speedtugc", fromlist=["SpeedTUGC"]).SpeedTUGC(name="speedtugc_w50"),
    # ★ `speedtugc_w58`：与 speedtugc **完全相同的打法**，只是换名字 —— 供"入席秒 50 vs 58"的
    # **随机对照**实验区分两臂（配对臂必须不同名，否则 integrity 会把同一房判成多策略）。
    # 证据：入席秒自然实验 >=54 vs <=51 ⇒ 同桌强度 Δ=-50.2 (t=-2.56)、我方分/房 Δ=+30.7 (t=+0.67)；
    # 斜率 对手每弱 1 分 => 我方 +0.520 分/房 (t=-5.36) ⇒ 预测 +26.1 分/房。见 tools/pool_second_trend.py。
    "speedtugc_w58": lambda: __import__("bot.speedtugc", fromlist=["SpeedTUGC"]).SpeedTUGC(name="speedtugc_w58"),
    # C063 搜索型候选（同向听关键弃牌的配对 rollout；2026-09-12 在 sim 里被否、且从未注册）。
    # 2026-09-17 先补"能不能过正式赛 M=10 门禁"这一步——过不了就彻底关闭该方向。
    "speedsearch": lambda: __import__("bot.speedsearch", fromlist=["SpeedSearch"]).SpeedSearch(),
    # C159c：**早期反向档**（前 3 巡权重 −0.3 = 偏好保对子；中 1.0 / 末 1.5）。
    # 依据 §9.77 真机曲线：c151 的 T1 拆对率 9.0% 是强者 2.3% 的 ~4 倍；c159（早 0）只能退回基线 5.2%。
    "speedc159c": lambda: __import__("bot.speedc159c", fromlist=["SpeedC159C"]).SpeedC159C(),
    # ⚠ speedc160（保白副露）**已按预登记规则否掉**（脚印 0.75% < 2%、对强者副露覆盖率增量 +0.1pp），
    #    保留注册只为记录与复跑，**不占真机臂位**（同 c159c 的先例）。
    "speedc160": lambda: __import__("bot.speedc160", fromlist=["SpeedC160"]).SpeedC160(),
    # ⚠ speedc161（接第二/三摊）同样**已按离线预筛否掉**（覆盖率上限 +0.4pp），保留注册作记录。
    "speedc161": lambda: __import__("bot.speedc161", fromlist=["SpeedC161"]).SpeedC161(),
    # speedc162 = **保对子档**（c152 的反向候选；本役"方向测试"臂，见预登记 §11）
    "speedc162": lambda: __import__("bot.speedc162", fromlist=["SpeedC162"]).SpeedC162(),
    "speedc153": lambda: __import__("bot.speedc153", fromlist=["SpeedC153"]).SpeedC153(),
    # C148：**有财必拷响保险臂**（GOD_MELD=False + 胡牌合法性闸门）——
    # 仅当正式赛 config 里 YouCaiBiKao=true 时启用（见 docs/STATUS-20260916.md §4c-11）。
    "speedc148": lambda: __import__("bot.speedc148", fromlist=["SpeedC148"]).SpeedC148(),
    # C147：**条件组合臂** —— C073w4（BC 弃牌模型）+ C146 的四个机制钩子。
    # 仅在战役 #1 判定采用 c073w4 时使用（新基线 + 新机制一次到位）；否则用 speedc146。
    "speedc147": lambda: __import__("bot.speedc147", fromlist=["SpeedC147"]).SpeedC147(
        model_path="var/c073_orig_w4_net.pt", lo=0, hi=2),
    # C146：**全缺陷组合臂（最大束）** = C144 明杠 + C134 自杠 + C136 吃碰质量 + C141 财飘
    # 四个成分各自对应一条同房配对证实的缺陷；"最大束"是功率算术的结论（少臂×大束×长战役）。
    "speedc146": lambda: __import__("bot.speedc146", fromlist=["SpeedC146"]).SpeedC146(),
    # C145：**同房缺陷组合臂** = C144(明杠) + C136(吃碰质量) + C141(财飘)
    # 三个成分各自对应一条**同房配对证实**的缺陷（明杠 t=-11.7 / 吃 t=-7.5 / 财飘 t=-6.1）。
    "speedc145": lambda: __import__("bot.speedc145", fromlist=["SpeedC145"]).SpeedC145(),
    # C144：speedtugc 的单变量候选 —— **明杠门控**（第 4 张是死牌就杠）
    # 真机实测：明杠必然补牌（603/603）、晚盘不限杠（进度上限 1.00）；我方杠/轮 0.010 vs 全场 0.024-0.077。
    "speedc144": lambda: __import__("bot.speedc144", fromlist=["SpeedC144"]).SpeedC144(),
    # C143：**低延迟版组合臂** —— C136 + C141（不含 C135）：出牌路径与 speedtugc 相同，
    # 只在副露窗口加计算 ⇒ C142 若延迟不达标时用它顶上。
    "speedc143": lambda: __import__("bot.speedc143", fromlist=["SpeedC143"]).SpeedC143(),
    # C142：**组合臂**（爬山用）：C136（质量感知副露）+ C135（真进张出牌）+ C141（财飘弃胡）。
    # 三个机制各自独立且已被单独量化；组合的目的是把 +5~+10 的小效应叠加到可判定线以上。
    "speedc142": lambda: __import__("bot.speedc142", fromlist=["SpeedC142"]).SpeedC142(),
    # C134：speedtugc 的单变量候选 —— 开启自己回合的**暗杠/补杠**（本族原来完全没有该路径）
    "speedc134": lambda: __import__("bot.speedc134", fromlist=["SpeedC134"]).SpeedC134(),
    # C133：C132(进张) + 自杠 的组合（**只在 C132 已被采用后再测**，否则一次动两个变量）
    "speedc133": lambda: __import__("bot.speedc133", fromlist=["SpeedC133"]).SpeedC133(),
    # C122：c073-w4 弃牌网 + 副露门控放宽一档（单变量）。证据与回滚判据见
    # docs/iter/reports/field-audit-20260915.md §6；sim 不可单独定案。
    "speedc122": lambda: __import__("bot.speedc122", fromlist=["C122Policy"]).C122Policy(
        model_path="var/c073_orig_w4_net.pt"),
    "speedc073w4lo1": lambda: __import__("bot.speedc068", fromlist=["C068Policy"]).C068Policy(
        model_path="var/c073_orig_w4_net.pt", lo=1, hi=2),
    "speedc073w4u": lambda: __import__("bot.speedc068", fromlist=["C068Policy"]).C068Policy(
        model_path="var/c073_orig_w4_net.pt", lo=0, hi=2, cand_order="ukeire"),
    "speedc073w4m30": lambda: __import__("bot.speedc068", fromlist=["C068Policy"]).C068Policy(
        model_path="var/c073_orig_w4_net.pt", lo=0, hi=2, margin=0.30),
    "speedc073w4m10": lambda: __import__("bot.speedc068", fromlist=["C068Policy"]).C068Policy(
        model_path="var/c073_orig_w4_net.pt", lo=0, hi=2, margin=0.10),
    "speedc118m10": lambda: __import__("bot.speedc118", fromlist=["C118Policy"]).C118Policy(
        model_path="var/c073_orig_w4_net.pt", lo=0, hi=2, margin=0.10),
    "speedc121b": lambda: __import__("bot.speedc121", fromlist=["C121Policy"]).C121Policy(
        model_path="var/c073_orig_w4_net.pt", meld_path="var/c121_meld_net.pt", lo=0, hi=2, claim_p=0.70),
    "speedc068e": lambda: __import__("bot.speedc068e", fromlist=["C068ePolicy"]).C068ePolicy(
        lo=0, hi=2),
    "speedc068e2": lambda: __import__("bot.speedc068e", fromlist=["C068ePolicy"]).C068ePolicy(
        model_paths=["var/c068_bc_lo0_net.pt", "var/c073_orig_net.pt"], lo=0, hi=2),
    "speedc070": lambda: __import__("bot.speedc070", fromlist=["C070Policy"]).C070Policy(
        model_path="var/c068_bc_lo0_net.pt"),
    "speedtugh": lambda: __import__("bot.speedtugh", fromlist=["SpeedTUGH"]).SpeedTUGH(),
    "speedtugw": lambda: __import__("bot.speedtugw", fromlist=["SpeedTUGW"]).SpeedTUGW(),
    "speedtw": lambda: __import__("bot.speedtw", fromlist=["SpeedTW"]).SpeedTW(),
}


def main(argv=None):
    ensure_utf8()
    ap = argparse.ArgumentParser(description="杭州麻将竞技平台 AI Bot（v8 协议骨架）")
    ap.add_argument("token", nargs="?", default="", help="参赛令牌（报名令牌或全局令牌）")
    ap.add_argument("tid", nargs="?", default="", help="锦标赛 id（仅全局令牌自测需显式指定）")
    ap.add_argument("--server", default=server_from_env(), help="服务器地址")
    ap.add_argument("--smoke", action="store_true", help="免认证冒烟自检（不参赛）")
    ap.add_argument("--strategy", default="speedvalue",   # 2026-09-24：默认改为当前主力（旧默认 speedtm 已是弱臂）
                    help="策略名（%s）" % "/".join(sorted(set(STRATEGY_FACTORIES))))
    ap.add_argument("--log", default="", help="日志双写文件（多实例分析用）")
    ap.add_argument("--match", action="store_true",
                    help="自动匹配房模式：全局令牌 POST /api/match 建房入席后打一房")
    ap.add_argument("--record-replays", default="",
                    help="逐场事件流复盘落盘目录（启用后每场写 <gid>.jsonl，窗口赛后审计用）")
    ap.add_argument("--warmup-draws", type=int, default=0,
                    help="开赛前用 N 个真实历史 draw 局面做进程内预热（默认 0=关闭）")
    args = ap.parse_args(argv)

    if args.log:
        import bot.util as _u
        _u.LOG_FILE = open(args.log, "a", encoding="utf-8")
        log("日志双写: %s", args.log)

    if args.smoke:
        sys.exit(0 if run_smoke(args.server) else 1)

    token = args.token
    if not token:
        ap.error("缺少参赛令牌：python run_bot.py <token> [锦标赛id]；--smoke 模式免令牌")

    log("服务器: %s", args.server)
    log("策略: %s", args.strategy)
    if args.strategy not in STRATEGY_FACTORIES:
        raise SystemExit("未知策略: %s（可用 %s）" % (
            args.strategy, sorted(set(STRATEGY_FACTORIES))))
    strategy = STRATEGY_FACTORIES[args.strategy]()
    if args.warmup_draws:
        got = warmup_strategy(strategy, args.warmup_draws)
        log("预热完成: %d/%d 个真实 draw 局面", got, args.warmup_draws)

    client = Client(args.server, token)

    # --match 自动房：入席得到 room_id（kind=auto 的锦标赛）后走通用主循环
    if args.match:
        import time as _t_mod
        log("自动匹配房模式：请求入席（POST /api/match）…")
        try:
            m = client.match()
        except ApiError as e:
            # v29 功能开关：403 FEATURE_DISABLED 为永久条件，不做重试
            if e.status == 403 and "FEATURE_DISABLED" in (e.body or ""):
                raise SystemExit(
                    "自动匹配已被管理端关闭（403 FEATURE_DISABLED，永久条件）")
            raise
        room = m.get("room_id") or m.get("tournament_id") or ""
        if not room:
            raise SystemExit("match 未返回 room_id: %s" % (str(m)[:300]))
        tid = room
        scoped = False       # 全局令牌 + 显式 tid（me.tournament_id 恒空）
        cfg = m.get("config") or {}
        log("已入席自动房 room=%s M=%s Rounds=%s base=%s", room,
            cfg.get("M"), cfg.get("Rounds"), cfg.get("BaseScore"))
        me = client.me()
    else:
        # 1) 令牌发现锦标赛（报名令牌作用域直达；全局令牌用 argv tid 显式指定）
        me = client.me()
        tid = me.get("tournament_id") or args.tid
        scoped = bool(me.get("tournament_id"))
        if not tid:
            raise SystemExit(
                "令牌未绑定锦标赛：请用门户「报名」/「测试房间」派发的参赛令牌"
                "（自测全局令牌请带锦标赛 id：python run_bot.py <token> <锦标赛id>）")
    log("user_id=%s 锦标赛=%s（%s）" % (me.get("user_id"), tid,
                                        "报名令牌直达" if scoped else "全局令牌+显式 tid"))

    # 2) 进场前先确认版本没有 BREAKING 差异（指南推荐做法）
    _warn_if_version_mismatch(client)

    # 3) --match 且未显式指定录制目录：自动开启决策/事件录制（执行验证底座）
    record_dir = args.record_replays or None
    if args.match and not record_dir:
        import time as _tm
        import os as _os
        record_dir = _os.path.join("var", "replays",
                                   "match_%s" % _tm.strftime("%Y%m%d_%H%M%S"))
        log("--match 自动开启录制: %s", record_dir)

    # 4) 主循环（阻塞至终态）
    try:
        run_tournament(client, tid, strategy, scoped=scoped, record_dir=record_dir)
    except ApiError as e:
        log("主循环终止于 API 错误: %s %s", e.status, e.code or e.body[:200])
        sys.exit(2)
    except KeyboardInterrupt:
        log("人工中断")
        sys.exit(130)
    log("bot 退出（%s）", time.strftime("%Y-%m-%d %H:%M:%S"))
    return 0


def _warn_if_version_mismatch(client):
    """指南版本自检：仅告警提示人工核对，不阻断运行（非 BREAKING 差异可忽略）。"""
    try:
        meta = client.guide_version()
    except ApiError:
        log("（版本自检不可用，跳过）")
        return
    ver = meta.get("version")
    log("服务器接入指南版本: v%s（本 bot 按 v%s 开发）" % (ver, bot.GUIDE_VERSION_KNOWN))
    if isinstance(ver, int) and ver > bot.GUIDE_VERSION_KNOWN:
        brk = [c for c in meta.get("changes") or []
               if c.get("type") == "breaking" and c.get("version", 0) > bot.GUIDE_VERSION_KNOWN]
        for c in brk:
            log("⚠ BREAKING v%s（%s）: %s", c.get("version"), c.get("date"), c.get("summary"))
        if brk:
            log("⚠ 发现更新的 BREAKING 变更 —— 建议人工核对 bot/protocol 语义后升级")
        else:
            log("服务器有更新（无 BREAKING，兼容新增/放宽）——按需升级版本常量")
    elif isinstance(ver, int) and ver < bot.GUIDE_VERSION_KNOWN:
        log("⚠ 服务器版本低于本 bot 已知版本（可能指向了旧环境？）")


if __name__ == "__main__":
    sys.exit(main())









