"""CLI 入口：运行 bot 或免认证冒烟自检。

用法：
    python run_bot.py --smoke [--server URL]            免认证冒烟（版本自检 + fan-calc）
    python run_bot.py <参赛令牌> [锦标赛id] [--server URL]   完整协议循环

- 报名令牌（门户「报名」/「测试房间」派发）：自动发现锦标赛，无需锦标赛 id；
- 全局令牌（POST /api/users 自测注册所得）：必须显式带锦标赛 id。
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
from bot.util import ensure_utf8, log, server_from_env

# 实盘可用策略（均含财神/爆头/窗口语义；默认 heuristicA 稳健版）
STRATEGY_FACTORIES = {}


def _reg(name):
    def deco(fn):
        STRATEGY_FACTORIES[name] = fn
        return fn
    return deco


@_reg("naive")
def _naive():
    from bot.strategy import NaiveStrategy
    return NaiveStrategy()


@_reg("heuristicA")
def _heuristic():
    from bot.heuristic import HeuristicA
    return HeuristicA()


@_reg("heuristicA2")
def _heuristic2():
    from bot.heuristic2 import HeuristicA2
    return HeuristicA2()


@_reg("speedA")
def _speed():
    from bot.speed import SpeedA
    return SpeedA()


def main(argv=None):
    ensure_utf8()
    ap = argparse.ArgumentParser(description="杭州麻将竞技平台 AI Bot（v8 协议骨架）")
    ap.add_argument("token", nargs="?", default="", help="参赛令牌（报名令牌或全局令牌）")
    ap.add_argument("tid", nargs="?", default="", help="锦标赛 id（仅全局令牌自测需显式指定）")
    ap.add_argument("--server", default=server_from_env(), help="服务器地址")
    ap.add_argument("--smoke", action="store_true", help="免认证冒烟自检（不参赛）")
    ap.add_argument("--strategy", default="heuristicA",
                    help="策略名（%s）" % "/".join(sorted(STRATEGY_FACTORIES)))
    args = ap.parse_args(argv)

    if args.smoke:
        sys.exit(0 if run_smoke(args.server) else 1)

    token = args.token
    if not token:
        ap.error("缺少参赛令牌：python run_bot.py <token> [锦标赛id]；--smoke 模式免令牌")

    log("服务器: %s", args.server)
    log("策略: %s", args.strategy)
    if args.strategy not in STRATEGY_FACTORIES:
        raise SystemExit("未知策略: %s（可用 %s）" % (
            args.strategy, sorted(STRATEGY_FACTORIES)))
    strategy = STRATEGY_FACTORIES[args.strategy]()

    client = Client(args.server, token)

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

    # 3) 主循环（阻塞至终态）
    try:
        run_tournament(client, tid, strategy, scoped=scoped)
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
        for c in meta.get("changes") or []:
            if c.get("type") == "breaking" and c.get("version", 0) > bot.GUIDE_VERSION_KNOWN:
                log("⚠ BREAKING v%s（%s）: %s", c.get("version"), c.get("date"), c.get("summary"))
        log("⚠ 发现更新的 BREAKING 变更 —— 建议人工核对 bot/protocol 语义后升级")
    elif isinstance(ver, int) and ver < bot.GUIDE_VERSION_KNOWN:
        log("⚠ 服务器版本低于本 bot 已知版本（可能指向了旧环境？）")


if __name__ == "__main__":
    sys.exit(main())
