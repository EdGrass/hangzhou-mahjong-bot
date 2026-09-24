"""tools/preflight —— 开赛前一键体检（退出码 0=就绪）。

检查：① 服务器可达 & 指南版本（未知 BREAKING 报警）
      ② fan-calc 抽样与本地引擎判定一致（5 例确定性探针）
      ③ 本地测试/黄金集就绪
      ④ 正式赛 bot 是否在本机运行（ps 探测 run_bot.py）
用法：python tools/preflight.py
"""
from __future__ import annotations

import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import bot                                  # noqa: E402
from bot.api import ApiError, Client        # noqa: E402
from mahjong.hu import is_baotou, is_win    # noqa: E402
from bot.util import ensure_utf8, log       # noqa: E402

PROBES = [
    (["1w", "1w", "1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w", "东", "东"], "东"),
    (["1w", "1w", "2w", "2w", "3b", "3b", "4t", "4t", "5t", "5t", "东", "东", "南"], "白"),
    (["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w", "1b", "1b", "1b", "白"], "东"),
]

# v21 边界探针（2026-09-07 服务器修订，防静默漂移）：比较服务器响应与本地引擎的
# 全字段（hu/baotou/fan/detail）——4白听任意=爆头、白×4 无落单才计豪华组。
V21_PROBES = [
    # A: 3 刻 + 4 白 摸 1w → server: 豪华七对×1+4白板+爆头 fan=16
    (["1w", "1w", "1w", "2b", "2b", "2b", "3t", "3t", "3t", "白", "白", "白", "白"], "1w"),
    # B: 3 对+3 单+4 白 摸北 → server: 七对+4白板+爆头 fan=8
    (["1w", "1w", "5b", "5b", "9t", "9t", "东", "南", "中", "白", "白", "白", "白"], "北"),
    # D: 双实四张+3t+4 白 摸3t → server: 豪华七对×3+4白板+爆头 fan=64
    (["1w", "1w", "1w", "1w", "2b", "2b", "2b", "2b", "3t", "白", "白", "白", "白"], "3t"),
]


def main():
    ensure_utf8()
    ok = True
    client = Client("https://10.240.169.190:18080")

    # 1) 服务器 + 指南版本
    try:
        meta = client.guide_version()
        ver = meta.get("version")
        log("服务器指南 v%s（本 bot v%s）", ver, bot.GUIDE_VERSION_KNOWN)
        if not isinstance(ver, int) or ver < bot.GUIDE_VERSION_KNOWN:
            ok = False
            log("✗ 版本异常：请人工核对")
        elif ver > bot.GUIDE_VERSION_KNOWN:
            brk = [c["summary"] for c in (meta.get("changes") or [])
                   if c.get("type") == "breaking" and c.get("version", 0) > bot.GUIDE_VERSION_KNOWN]
            if brk:
                ok = False
                for b in brk:
                    log("✗ 未知 BREAKING: %s", b)
            else:
                log("⚠ 服务器有更新但无 BREAKING（可运行，建议核对）")
        else:
            log("✓ 版本一致")
    except ApiError as e:
        ok = False
        log("✗ 服务器不可达: %s %s", e.status, e.code or e.body[:100])

    # 2) fan-calc 抽样一致（判定 + v21 边界全字段对拍）
    try:
        bad = 0
        for hand, draw in PROBES:
            r = client.fan_calc({"hand": hand, "draw": draw,
                                 "chain": {"count": 0, "piao": 0}, "base": 1})
            mine_hu = is_win(hand + [draw])
            if bool(r.get("hu")) != mine_hu:
                bad += 1
        from mahjong.fan import calc as local_calc
        for hand, draw in V21_PROBES:
            r = client.fan_calc({"hand": hand, "draw": draw,
                                 "chain": {"count": 0, "piao": 0}, "base": 1})
            mine = local_calc(hand, draw)
            srv = (bool(r.get("hu")), bool(r.get("baotou")), r.get("fan"),
                   r.get("detail"))
            my = (mine["hu"], mine["baotou"], mine["fan"], mine["detail"])
            if srv != my:
                bad += 1
                log("✗ v21 边界漂移: hand=%s draw=%s server=%s mine=%s",
                    hand, draw, srv, my)
        if bad:
            ok = False
            log("✗ fan-calc 抽样 %d/%d 不一致", bad,
                len(PROBES) + len(V21_PROBES))
        else:
            log("✓ fan-calc 抽样 %d 例全部一致（含 %d 例 v21 边界）",
                len(PROBES) + len(V21_PROBES), len(V21_PROBES))
    except ApiError as e:
        ok = False
        log("✗ fan-calc 调用失败: %s %s", e.status, e.code or e.body[:100])

    # 3) 本地单测快速子集（引擎相关）
    r = subprocess.run([sys.executable, "-m", "unittest",
                        "tests.test_hu", "tests.test_fan_golden",
                        "tests.test_shanten_exact"],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        ok = False
        log("✗ 引擎单测未通过")
    else:
        log("✓ 引擎单测通过")

    # 4) bot 进程探测（本机）
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             # 注意：keeper/watchdog 与 run_bot 常以 **pythonw.exe** 启动，
             # 只筛 python.exe 会漏报（2026-09-15 实测：bot 正在跑却报「无 run_bot」）。
             "Get-CimInstance Win32_Process | "
             "Where-Object { $_.Name -match '^pythonw?\\.exe$' -and "
             "$_.CommandLine -match 'run_bot\\.py' } | "
             "Measure-Object | Select-Object -ExpandProperty Count"],
            capture_output=True, text=True, timeout=20)
        n = int((out.stdout or "0").strip() or 0)
        if n > 0:
            log("✓ 检测到 %d 个 run_bot 进程", n)
        else:
            log("⚠ 本机无 run_bot 进程（若由看门狗/其他机器托管可忽略）")
    except Exception:
        log("⚠ 进程探测不可用（跳过）")

    # 5) 决策延迟体检（30 分钟房间上限 ⇒ 决策变慢会少打局数）
    #    取最近一局 dec 记录，按窗口比较 p99：碰/吃窗口 1s、弃牌窗口 3s。
    try:
        import glob as _glob, json as _json

        # 只体检「即将上生产的那一档策略」的最近一房 —— 否则一个已淘汰候选留下的慢文件
        # 会把 preflight 永久钉在 NOT READY，而 _switch_to_official.ps1 见到非 READY 会 throw
        # ⇒ 正式赛当天会被一条无关的旧记录挡住切换。（2026-09-15 实测：speedc130 淘汰后
        #   最新 dec 文件仍是它的，p99=8009ms、12 条超窗口，而 speedtugc 是 0 条。）
        _want = ""
        try:
            _want = io.open(os.path.join(ROOT, "var", "_keeper_strategy.txt"),
                            encoding="utf-8").read().strip()
        except Exception:
            _want = ""
        _room2s = {}
        try:
            for _ln in io.open(os.path.join(ROOT, "var", "auto_ranking.jsonl"), encoding="utf-8"):
                _ln = _ln.strip()
                if not _ln:
                    continue
                _r = _json.loads(_ln)
                if _r.get("room"):
                    _room2s[_r["room"]] = _r.get("strategy") or ""
        except Exception:
            _room2s = {}
        _cands = []
        for _d in _glob.glob(os.path.join(ROOT, "var", "replays", "auto_*")):
            _fs2 = _glob.glob(os.path.join(_d, "*.dec.jsonl"))
            if not _fs2:
                continue
            _newest = max(_fs2, key=os.path.getmtime)
            _rid = None
            try:
                for _ln in io.open(_newest, encoding="utf-8"):
                    if _ln.strip():
                        _rid = (_json.loads(_ln).get("g") or "").split("_r")[0]
                        break
            except Exception:
                _rid = None
            _cands.append((max(os.path.getmtime(f) for f in _fs2), _newest, _room2s.get(_rid, "")))
        _fs = []
        if _cands:
            _cands.sort()
            _pick = [c for c in _cands if _want and c[2] == _want]
            _fs = [(_pick[-1] if _pick else _cands[-1])[1]]
            log("  延迟体检对象：%s（策略 %s）" % (os.path.basename(os.path.dirname(_fs[0])),
                                              (_pick[-1] if _pick else _cands[-1])[2] or "?"))
        if _fs:
            _v = []
            for _ln in io.open(_fs[-1], encoding="utf-8"):
                _ln = _ln.strip()
                if not _ln:
                    continue
                try:
                    _r = _json.loads(_ln)
                except Exception:
                    continue
                _ms = _r.get("ms")
                if isinstance(_ms, (int, float)):
                    _v.append((float(_ms), str(_r.get("p"))))
            if _v:
                _v.sort()
                _n = len(_v)
                _p99 = _v[min(_n - 1, int(_n * 0.99))][0]
                _over = sum(1 for _m, _ph in _v
                            if (_ph.startswith("response_") and _m > 1000) or (_ph == "draw" and _m > 3000))
                if _over:
                    ok = False
                    log("✗ 决策超窗口 %d 条（p99=%.0fms，窗口 1s/3s）——会丢机会且拖长房间", _over, _p99)
                elif _p99 > 500:
                    log("⚠ 决策 p99=%.0fms 偏高（预算 1s/3s；房间有 30min 上限，变慢会少打局数）", _p99)
                else:
                    log("✓ 决策延迟健康（p99=%.0fms，超窗口 0 条；窗口 1s/3s）", _p99)
    except Exception as e:
        log("⚠ 延迟体检不可用（跳过）：%s", str(e)[:60])

    # 6) 自愈链根节点：计划任务 HangzhouMajAutoHeal（整条监管链的根）
    #    它一旦被禁用/失败，watchdog/keeper/official keepalive 全都失去兜底
    #    （历史上 keeper 无人管曾造成 37.6 小时空转）。
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "$t=Get-ScheduledTask -TaskName 'HangzhouMajAutoHeal' -ErrorAction SilentlyContinue; "
             "if($t){$i=Get-ScheduledTaskInfo -TaskName 'HangzhouMajAutoHeal'; "
             "'{0}|{1}|{2}' -f $t.State,$i.LastTaskResult,$i.NumberOfMissedRuns}else{'MISSING'}"],
            capture_output=True, text=True, timeout=25)
        v = (out.stdout or "").strip()
        if v == "MISSING" or not v:
            log("⚠ 未找到计划任务 HangzhouMajAutoHeal（自愈链根节点缺失，建议重建）")
        else:
            state, res, missed = (v.split("|") + ["", "", ""])[:3]
            if str(state).strip().lower() == "ready" and str(res).strip() == "0":
                log("✓ 自愈链根节点就绪（计划任务 Ready，LastTaskResult=0，Missed=%s）", str(missed).strip())
            else:
                log("⚠ 自愈链根节点异常（State=%s LastTaskResult=%s Missed=%s）——"
                    "watchdog/keeper/official keepalive 将失去兜底", state, res, missed)
    except Exception as e:
        log("⚠ 计划任务体检不可用（跳过）：%s", str(e)[:60])

    log("体检结果: %s" % ("READY" if ok else "NOT READY"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
