# -*- coding: utf-8 -*-
"""正式赛专用 keepalive：单实例、独立日志、官方复盘录制。

只负责拉起/重启 run_bot；不在 exit 0 后重启。默认读取
var/.token_1024_20260917，运行 --strategy speedtugc。

策略默认值 2026-09-15 更正：原为 speedc068lo0，但按**真机逐轮口径**（对榜单逐房校验 99.3%）
重算后，speedc068lo0 是 BC 组里最差的（7 房 / 净胜 -53.7 房 / 胡率 23.2%），
而 speedtugc 是真机证据最厚的一档（141 房 / +0.214 分每轮 / 净胜 +22.9 房 / 胡率 25.4%）。
详见 docs/iter/reports/field-audit-20260915.md §9.1。
"""
from __future__ import annotations
import argparse
import datetime as dt
import io
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import psutil


def _existing():
    out = []
    for p in psutil.process_iter(["pid", "cmdline", "exe"]):
        try:
            argv = p.info.get("cmdline") or []
            base = [os.path.basename(str(x).replace("\\", "/")).lower() for x in argv]
            # ★ 2026-09-17 加固（E002 红线）：原先只认 run_bot/keep_alive/official_keepalive，
            #   但测试房链路是 `_keeper` → `match_super` → `run_bot` ——
            #   **match_super 在"等房期"里合法地没有 run_bot 子进程**（尤其现在有 `--wait-until-second`
            #   会先睡最多 59 秒）。若此时手工拉起本脚本，旧守卫会放行，等那个 match_super 入房
            #   就变成同账号两个 run_bot = E002。
            #   正常路径下 `_switch_to_official.ps1` 会等 match_super 消失、watchdog 在官方模式下也不碰进程，
            #   所以这只是**把手工调用这条缝补上**；多拦一层只更保守，不会误伤。
            if any(k in base for k in ("run_bot.py", "keep_alive.py", "_official_keepalive.py",
                                       "match_super.py", "_keeper.py")):
                if p.info["pid"] != os.getpid():
                    out.append(p.info["pid"])
        except Exception:
            pass
    return out


def next_delay(failures, base=5, cap=120):
    """连续第 failures 次非零退出后应当等待的秒数（指数退避、封顶）。

    为什么**只退避不设上限停摆**：正式赛是一次性事件，宁可 2 分钟一次地一直重试，
    也不能因为一段网络抖动就永久退出（那等于放弃剩余所有局）。
    """
    try:
        n = max(0, int(failures))
    except Exception:
        n = 0
    k = max(0, n - 1)          # 第 1 次失败仍按 base 秒重试，之后翻倍
    return min(int(cap), int(base) * (2 ** min(k, 8)))


SPEC = os.path.join(ROOT, "var", ".official_spec.json")

# 这些策略的 M=10 冷启动尾延迟需要预热；speedtugc 等轻量策略不加。
HEAVY_WARMUP = {"speedc151", "speedc156", "speedc159", "speedc163",
                "speedc185", "speedc186", "speedc187",
                # 2026-09-18 补：c135 的**弃牌路径**用的正是 c151 同一条 real_ukeire
                # （历史冷启动 4/160 次 >3s 的记录属于这条路径）；c136/c146 的
                # **副露门控**也走 real_ukeire。不加会以冷缓存开赛。
                "speedc135", "speedc136", "speedc146",
                # 2026-09-19 补（★ 赛前风险）：c150/c152 及 c209~c215 全部继承 c135 的
                # `_best_discard_realukeire` 弃牌路径（c152 还额外走 c151 的路线加成），
                # 冷缓存下与 c135 同一条尾延迟风险。**当前生产策略 speedc211 在此列。**
                "speedc150", "speedc152", "speedc209", "speedc210", "speedc211",
                "speedc212", "speedc213", "speedc214", "speedc215",
                # ★ R1329（2026-09-24）：**补上我们自己的现役/排队臂**。原名单写于 09-18/19，
                #   当时还没有 `speedvalue` 系列。而 `bot/speedvalue.py:79` 在 `value_of` 里**每条候选都调 `real_ukeire`**，
                #   并额外调 `fan_calc`（`_max_fan`）⇒ 冷启动代价**只会比 c151 更重**（c151 正是因为测到
                #   4/160 次 >3s 才进名单）。不加 ⇒ 开赛第一几手以**冷缓存**跑。本集合只在拉起该策略时查询，多写无副作用。
                "speedvalue", "speedvalueplain", "speedvaluebc", "speedvaluebcv", "speedc151bc",
                "speedvaluebaotouv5", "speedvaluebaotouv10", "speedvaluebaotouv20",
                "speedvaluemeld", "speedvaluemeldp35", "speedvaluemeldp40",
                "speedvaluemeldp45", "speedvaluemeldp50",
                "speedvaluebcmeld", "speedvaluebcmeldp45", "speedvaluebaotouvmeld",
                "speedvaluebcvmeld", "speedvaluerank", "speedgangtakec151fixed",
                # ★ R1334：15:05 规则预检可能把臂换成 ycbk 孪生（§V.109）⇒ 它们也必须预热，
                #   否则“换闸门臂”这一手反而带来冷启动。
                "speedvalueycbk", "speedgangtakefixedycbk",
                "speedmeldmore0chiycbk", "speedmeldtol2chiycbk"}


def warmup_for_strategy(strategy):
    return 50 if str(strategy) in HEAVY_WARMUP else 0


def build_run_bot_cmd(strategy, token, server, logp, recp):
    cmd = [sys.executable, "-X", "utf8", "run_bot.py", token,
           "--strategy", strategy, "--server", server,
           "--log", logp, "--record-replays", recp]
    w = warmup_for_strategy(strategy)
    if w:
        cmd += ["--warmup-draws", str(w)]
    return cmd


def write_spec(strategy, token_file, server):
    """★ 2026-09-16 新增：把本次官方赛的参数落盘。

    为什么必须：`var/_ensure_all.py` 在**官方赛期间**如果发现 keepalive 不在（例如整机重启），
    会自己把它拉起来 —— 而旧实现**不带任何参数**，于是回落到默认值
    （`--strategy speedtugc`、`--token-file var/.token_1024_20260917`）。
    对"一个月后的正式赛"来说，那意味着**用错策略 + 用过期令牌**（静默不参赛）。
    """
    try:
        with io.open(SPEC, "w", encoding="utf-8") as f:
            f.write(json.dumps({"strategy": strategy, "token_file": token_file,
                                "server": server, "ts": time.strftime("%Y-%m-%d %H:%M:%S")},
                               ensure_ascii=False))
    except Exception as e:
        # 本模块没有 log()（只往 stdout 打），这里必须用 sys.stderr 自保，否则异常会吞掉真正的失败原因
        sys.stderr.write("⚠ 写 .official_spec.json 失败：%r（自愈重启会回落到默认参数）\n" % (e,))
        sys.stderr.flush()


def main(argv=None):
    ap = argparse.ArgumentParser()
    # ★ R1307：旧默认是 09-17 二测的（speedtugc + .token_1024_20260917）。
    #   `_ensure_all.py` 在"缺 .official_spec.json" 时会**不带参数**拉本脚本
    #   ⇒ 就会用**错的臂 + 过期令牌**参加正式赛（静默不参赛/报错）。
    #   现在：策略默认取 `var/_keeper_strategy.txt`；令牌默认取 `var/.global_token`；
    #   两者都取不到就**直接报错**（宁可不起，也不用历史值）。
    ap.add_argument("--token-file", default="")
    ap.add_argument("--strategy", default="")
    ap.add_argument("--server", default="https://10.240.169.190:18080")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    if not args.strategy:
        try:
            args.strategy = io.open(os.path.join(ROOT, "var", "_keeper_strategy.txt"),
                                    encoding="utf-8-sig").read().strip()
        except Exception:
            args.strategy = ""
        if not args.strategy:
            raise SystemExit("未指定 --strategy 且读不到 var/_keeper_strategy.txt"
                             "（禁止沿用历史默认值 speedtugc）")
    if not args.token_file:
        cand = os.path.join(ROOT, "var", ".global_token")
        if os.path.exists(cand):
            args.token_file = cand
        else:
            raise SystemExit("未指定 --token-file 且找不到 var/.global_token"
                             "（禁止沿用历史默认值 .token_1024_20260917）")
    token = open(args.token_file, encoding="utf-8").read().strip()
    if not token:
        raise SystemExit("empty token file")
    other = _existing()
    if other:
        # 这里拦的是**任何** run_bot/keepalive 进程（含测试房/自习房那条链）——
        # 同账号并发会撞 E002（第二个 /api/match 返回同一房），所以必须是空的。
        # 正确顺序：先 tools/ab_ctl.py stop 或停 keeper → 等当前对局自然结束 → 再起本脚本。
        raise SystemExit(
            "检测到其它 bot 进程 %s（run_bot/keepalive/_official_keepalive）——"
            "正式赛要求同账号独占：先停测试房 keeper 与 A/B，等当前对局自然结束后重试。" % other)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    logp = os.path.join(ROOT, "logs", "official_1024_%s.log" % stamp)
    recp = os.path.join(ROOT, "var", "replays", "official_1024_%s" % stamp)
    cmd = build_run_bot_cmd(args.strategy, token, args.server, logp, recp)
    write_spec(args.strategy, args.token_file, args.server)
    if args.dry_run:
        print("dry-run:", " ".join(cmd[:4]), "... strategy=%s log=%s replay=%s" %
              (args.strategy, logp, recp))
        return 0
    out = open(os.path.join(ROOT, "var", "_official_1024.out"), "a", encoding="utf-8")
    failures = 0
    while True:
        print("%s start bot strategy=%s warmup=%d log=%s replay=%s" %
              (dt.datetime.now(), args.strategy, warmup_for_strategy(args.strategy), logp, recp),
              file=out, flush=True)
        p = subprocess.Popen(cmd, cwd=ROOT, stdout=out, stderr=subprocess.STDOUT)
        code = p.wait()
        print("%s bot exit code=%s" % (dt.datetime.now(), code), file=out, flush=True)
        if code == 0:
            return 0
        failures += 1
        d = next_delay(failures)
        print("%s 重启前退避 %ds（连续失败 %d 次）"
              % (dt.datetime.now(), d, failures), file=out, flush=True)
        time.sleep(d)


if __name__ == "__main__":
    main()