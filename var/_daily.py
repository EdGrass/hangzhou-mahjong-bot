# -*- coding: utf-8 -*-
"""每日/当前状态一览（一屏）：策略表现、最近房、榜单、机制三项、系统健康。

用法：python -X utf8 var/_daily.py [天数=2]
"""
import io
import collections, datetime, json, os, statistics, ssl, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ME = "u_7a3fba48d70b"
CUR = None
try:
    import psutil
    CUR = [p for p in psutil.process_iter(["cmdline", "exe"]) if _is if False]
except Exception:
    pass


def rows():
    out = []
    for ln in open("var/auto_ranking.jsonl", encoding="utf-8"):
        ln = ln.strip()
        if not ln:
            continue
        d = json.loads(ln)
        if d.get("status") != "finished":
            continue
        rk = d.get("ranking") or []
        me = [r for r in rk if r.get("user_id") == ME]
        if not me or len(rk) < 4:
            continue
        others = [r for r in rk if r.get("user_id") != ME]
        om = sum(r.get("total_score") or 0 for r in others) / len(others)
        out.append(dict(ts=d["ts"][:16], day=d["ts"][:10], st=d.get("strategy"), room=d["room"],
                        sc=me[0]["total_score"], rank=me[0].get("rank") or 0,
                        net=me[0]["total_score"] - om))
    return out


def board():
    try:
        ctx = ssl._create_unverified_context()
        cookie = open("var/.portal_cookie", encoding="utf-8-sig").read().strip()
        req = urllib.request.Request("https://10.240.169.190:18080/portal/api/leaderboard?period=all",
                                     headers={"Cookie": cookie})
        d = json.loads(urllib.request.urlopen(req, timeout=20, context=ctx).read().decode("utf-8"))
        # ★ 2026-09-17 新增：顺手把这次榜单快照追加到 var/ladder_history.jsonl（榜单 = 累计分，
        #   没有时间序列就看不出"斜率"）。用 tools/ladder_snapshot 的同一 schema；同分钟去重。
        try:
            sys.path.insert(0, os.path.join(ROOT, "tools"))
            import ladder_snapshot as _ls
            rec = _ls.snapshot("all", d)
            _hist = _ls.load_history()
            if ("all", rec["ts"][:16]) not in {(r.get("period"), (r.get("ts") or "")[:16]) for r in _hist}:
                with io.open(_ls.OUT, "a", encoding="utf-8") as _f:
                    _f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception:
            pass
        return d.get("me") or {}
    except Exception as e:
        return {"error": str(e)[:80]}


def main():
    R = rows()
    print("=" * 78)
    print("杭州麻将 bot 状态一览  %s" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    b = board()
    print("榜单: rank=%s rooms=%s firsts=%s score=%s" % (b.get("rank"), b.get("rooms"), b.get("firsts"), b.get("score")))
    print("-" * 78)
    by = collections.defaultdict(list)
    for r in R:
        by[(r["day"], r["st"])].append(r)
    print("%-12s %-13s %5s %10s %10s %9s %8s" % ("日期", "策略", "房数", "原始/房", "净胜/房", "正分率", "均名次"))
    for (day, st), v in sorted(by.items())[-6:]:
        sc = [x["sc"] for x in v]
        print("%-12s %-13s %5d %+10.1f %+10.1f %8.1f%% %8.2f" % (
            day, st, len(v), statistics.mean(sc), statistics.mean(x["net"] for x in v),
            100.0 * sum(1 for s in sc if s > 0) / len(sc), statistics.mean(x["rank"] for x in v)))
    print("-" * 78)
    print("最近 6 房：")
    for r in R[-6:]:
        print("  %s %-18s %-13s %+6d rank%d 净%+7.1f" % (r["ts"], r["room"], r["st"], r["sc"], r["rank"], r["net"]))
    print("-" * 78)
    # 进程与自愈
    try:
        import psutil
        names = collections.Counter()
        for p in psutil.process_iter(["exe", "name"]):
            try:
                exe = os.path.basename(p.info.get("exe") or p.info.get("name") or "").lower()
                if "python" not in exe:
                    continue
                cl = p.cmdline()
            except Exception:
                continue
            for a in cl[1:]:
                base = os.path.basename(str(a).replace("\\", "/")).lower()
                if base in ("_keeper.py", "_watchdog.py", "_ab_driver.py", "_official_keepalive.py", "match_super.py", "run_bot.py"):
                    names[base] += 1
        print("进程: " + ", ".join("%s×%d" % (k, v) for k, v in sorted(names.items())) or "无")
    except Exception as e:
        print("进程检查失败:", e)
    try:
        print("当前策略:", open("var/_keeper_strategy.txt", encoding="utf-8-sig").read().strip())
    except OSError:
        pass
    # ---- 进度快照 + 卡死告警（2026-09-16 新增；**只告警、不动手**）----
    #   为什么需要：watchdog 在 A/B 模式下把排批交给 _ab_driver 后只打一行就返回，
    #   而驱动本身**没有**"批次卡死"超时 ⇒ 若 run_bot 存活但不再产出（挂死），全链无人报警
    #   （这正是当年"37.6 小时空转"的形态）。这里用"最近盘面文件年龄"补上可见性。
    try:
        import glob as _g, time as _t
        ages = []
        for _pat in ("var/replays/auto_*/*.jsonl", "var/replays/auto_*/*.dec.jsonl",
                     "var/auto_ranking.jsonl"):
            for _f in _g.glob(_pat):
                try:
                    ages.append(_t.time() - os.path.getmtime(_f))
                except OSError:
                    pass
        if ages:
            age_min = min(ages) / 60.0
            bot_alive = False
            try:
                import psutil as _ps
                for _p in _ps.process_iter(["cmdline"]):
                    argv = _p.info.get("cmdline") or []
                    base = [os.path.basename(str(x).replace("\\", "/")).lower() for x in argv]
                    if "run_bot.py" in base or "match_super.py" in base:
                        bot_alive = True
                        break
            except Exception:
                pass
            warn = ("⚠ 疑卡死：进程在跑但最近盘面 %.0f 分钟没更新（房间上限 30 分钟）" % age_min) \
                if (bot_alive and age_min > 35) else ""
            print("进度: 最近盘面 %.1f 分钟前%s" % (age_min, ("   " + warn) if warn else ""))
    except Exception as e:
        print("进度检查失败:", e)
    # ---- 看门狗"卡死"判定的最后一条（A/B 模式下通常已停更，仅作历史参考）----
    try:
        _wlog = "var/_watchdog.out"
        if os.path.exists(_wlog):
            _lines = [ln for ln in io.open(_wlog, encoding="utf-8", errors="replace").read().splitlines()
                      if "状态=" in ln]
            if _lines:
                _last = _lines[-1]
                print("看门狗: " + _last[-120:] + ("   ⚠ 疑卡死（>20 分钟无房日志）" if "卡死" in _last else ""))
    except Exception:
        pass
    # ---- 本轮新增：监督链与哨兵 ----
    try:
        import subprocess as _sp
        ab = os.path.exists("var/.ab_mode")
        off = os.path.exists("var/.official_mode")
        print("哨兵: ab_mode=%s official_mode=%s%s"
              % (ab, off, "   ← 官方赛模式：测试房自愈已停用（赛后记得 var/_exit_official.py）" if off else ""))
    except Exception:
        pass
    try:
        import subprocess as _sp
        r = _sp.run([sys.executable, "-X", "utf8", "tools/rate_guard.py", "--status"],
                    capture_output=True, text=True, timeout=40)
        print("熔断器:", (r.stdout or "").strip().splitlines()[0] if (r.stdout or "").strip() else "(无输出)")
    except Exception as e:
        print("熔断器检查失败:", str(e)[:60])
    try:
        import subprocess as _sp
        r = _sp.run(["powershell", "-NoProfile", "-Command",
                     "$t=Get-ScheduledTask -TaskName 'HangzhouMajAutoHeal' -ErrorAction SilentlyContinue; "
                     "if($t){$i=Get-ScheduledTaskInfo -TaskName 'HangzhouMajAutoHeal'; "
                     "'{0} LastResult={1} Missed={2}' -f $t.State,$i.LastTaskResult,$i.NumberOfMissedRuns}"
                     "else{'MISSING'}"], capture_output=True, text=True, timeout=25)
        print("自愈链根节点:", (r.stdout or "").strip() or "MISSING")
    except Exception as e:
        print("自愈链根节点检查失败:", str(e)[:60])
    # ---- A/B（若在跑）----
    if os.path.exists("var/.ab_mode"):
        try:
            import subprocess as _sp
            r = _sp.run([sys.executable, "-X", "utf8", "tools/ab_readout.py"],
                        capture_output=True, text=True, timeout=90)
            for ln in (r.stdout or "").splitlines():
                if ln.strip() and not ln.startswith("提示"):
                    print(ln)
        except Exception as e:
            print("A/B 读数失败:", str(e)[:70])
    # ---- 正式赛 ----
    try:
        import ssl as _ssl, urllib.request as _u, json as _j
        _ctx = _ssl._create_unverified_context()
        _ck = open("var/.portal_cookie", encoding="utf-8-sig").read().strip()
        _rq = _u.Request("https://10.240.169.190:18080/portal/api/tournaments",
                         headers={"Cookie": _ck})
        _d = _j.loads(_u.urlopen(_rq, timeout=15, context=_ctx).read().decode())
        for _t in (_d.get("tournaments") or []):
            import datetime as _dt
            _left = (_dt.datetime.fromtimestamp(_t["start_at"]) - _dt.datetime.now()).total_seconds() / 3600.0
            print("正式赛: %s status=%s 已报名=%s 报名数=%s 距开赛 %.1f 小时"
                  % (_t.get("name"), _t.get("status"), _t.get("my_registered"),
                     _t.get("registered"), _left))
    except Exception as e:
        print("正式赛状态获取失败:", str(e)[:60])
    print("=" * 78)


if __name__ == "__main__":
    main()
