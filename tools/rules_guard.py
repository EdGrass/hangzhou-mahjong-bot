# -*- coding: utf-8 -*-
"""rules_guard —— 开赛前把 `YouCaiBiKao` 与"将要上场的策略"对一遍，**不一致就让流程失败**。

为什么需要（STATUS §4c-11 / §9.36）：
- 指南 §1.6：`M / Rounds / BaseScore / **YouCaiBiKao** / 各窗口秒数` **每场锦标赛可不同**，以 `/rules` 为准；
- 若正式赛 `YouCaiBiKao=true` 而我们跑的是**不含合法性闸门**的策略 ⇒ 我方历史胡牌的 **64.4%**（有白平胡）
  会被服务端 409 拒掉；反之若环境是 `false` 而跑 `speedc148/153`（含闸门）⇒ **主动拒掉合法平胡**，代价同样巨大；
- 现状是**人工步骤**（"发布后第一件事读 /rules"）⇒ 这里把它变成**一条命令 + 明确的退出码**，可以焊进开赛脚本。

用法：
    python -X utf8 tools/rules_guard.py                       # 只读 config + 给建议
    python -X utf8 tools/rules_guard.py --strategy speedtugc   # 校验"我要跑的策略"是否合规
    python -X utf8 tools/rules_guard.py --token-file var/.token_1024_20260917 --strategy speedtugc

退出码：0 = 一致；2 = **不一致**（不要开赛）；3 = 读不到 config（令牌/网络问题，需人工确认）。
"""
from __future__ import annotations
import argparse, io, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.api import Client, ApiError          # noqa: E402

# 需要 YouCaiBiKao=true 的策略（含"有财必拷响"合法性闸门）
NEEDS_YCBK = {"speedc148", "speedc153", "speedc169", "speedc170", "speedc171",
              "speedc172", "speedc176", "speedc181", "speedc184", "speedc185"}


def strategy_needs_ycbk(strategy):
    """动态读取策略实例的 YOU_CAI_BI_KAO；静态表作兜底/快速路径。"""
    if strategy in NEEDS_YCBK:
        return True
    try:
        from run_bot import STRATEGY_FACTORIES
        pol = STRATEGY_FACTORIES[strategy]()
        return bool(getattr(pol, "YOU_CAI_BI_KAO", False))
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--token-file", default=os.path.join(ROOT, "var", ".token_1024_20260917"))
    ap.add_argument("--server", default="https://10.240.169.190:18080")
    ap.add_argument("--strategy", default="")
    a = ap.parse_args()

    try:
        token = io.open(a.token_file, encoding="utf-8-sig").read().strip()
    except OSError as e:
        print("✗ 读不到令牌文件 %s：%s" % (a.token_file, e))
        return 3
    if not token:
        print("✗ 令牌文件为空：%s" % a.token_file)
        return 3

    cli = Client(a.server, token)
    try:
        res = cli.tournament_rules()
    except ApiError as e:
        print("✗ GET /api/tournaments/me/rules 失败：HTTP %s %s" % (e.status, (e.body or "")[:200]))
        print("  （全局令牌会返回 400 TOKEN_NOT_SCOPED ⇒ 必须用**该赛事的报名令牌**）")
        if a.strategy:
            print("⚠ 无法校验策略 %s 与 YouCaiBiKao 是否一致 —— 请人工确认后再开赛" % a.strategy)
        return 3
    except Exception as e:                                   # noqa: BLE001
        print("✗ 读规则异常：%r" % (e,))
        return 3

    cfg = (res or {}).get("config") if isinstance(res, dict) else None
    if not isinstance(cfg, dict):
        cfg = res if isinstance(res, dict) else {}
    ycbk = cfg.get("YouCaiBiKao")
    print("锦标赛 config：%s" % json.dumps(cfg, ensure_ascii=False)[:800])
    print("YouCaiBiKao = %s" % ycbk)

    if ycbk is None:
        print("⚠ config 里没有 YouCaiBiKao 字段 ⇒ 无法判定（人工确认）")
        return 3

    ycbk = bool(ycbk)
    need = ycbk is True
    if not a.strategy:
        # ★ R1532：旧建议只提 speedc148/153（旧保险臂）——照它跑等于丢掉十天优化。
        #   现在首选**同剂量孪生** `<arm>ycbk`（bot/ycbk_chain.py，13 根）。
        print("建议：%s" % ("用 `<arm>ycbk` 同剂量孪生（见 bot/ycbk_chain.py；兜底 speedc148 / speedc153）" if need
                          else "用不含闸门的策略（speedvalue 一族；本项目当前链就是）"))
        return 0

    has_gate = strategy_needs_ycbk(a.strategy)
    if need and not has_gate:
        print("✗ **不一致**：本场 YouCaiBiKao=true，但策略 %s 不含闸门 ⇒ 有白平胡会被 409 拒（历史占我方胡牌 64.4%%）" % a.strategy)
        print("  ⇒ **首选**把本策略换成同剂量孪生 `<arm>ycbk`（本项目已备 13 根，见 bot/ycbk_chain.py）：")
        print("     例：speedvaluebcmeldp45 ⇒ speedvaluebcmeldp45ycbk。孪生未注册时才退回 speedc148 / speedc153（旧保险臂）")
        return 2
    if (not need) and has_gate:
        print("✗ **不一致**：本场 YouCaiBiKao=false，但策略 %s 含闸门 ⇒ 会**主动拒掉合法平胡**" % a.strategy)
        print("  ⇒ 改跑不含闸门的策略（如 speedtugc 一族），再重跑本校验")
        return 2
    print("✓ 一致：YouCaiBiKao=%s 与策略 %s 匹配" % (ycbk, a.strategy))
    return 0


if __name__ == "__main__":
    sys.exit(main())



