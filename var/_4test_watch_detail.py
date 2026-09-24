# -*- coding: utf-8 -*-
"""`var/_4test_watch_detail.py` —— 四测期间每隔 10 分钟把**赛事详情**快照成一行 JSON。

## 为什么（2026-09-24 实测，不是推测）

门户**只保留当前 1 场赛事**，而且**赛事视角的数据会在赛后消失**：

* 三测（`t_069a55e84b26`）现在 `GET /api/tournaments/<tid>` → **404**，门户赛事列表里也已消失；
* 但**单场复盘还在**：`GET /portal/api/games/t_069a55e84b26_s2_b20_t0/events` → **200（298 KB）**。

⇒ 结论：**对局数据留得住，赛事视角的数据（`ranking` 全榜、`my_games` gid 清单、stage/qualified）留不住**。
四测（16:00–19:00）是唯一窗口；不抓，赛后连“我们 vs 全部 ~96 人”的名次分布都无法重建，
而 `my_games` 正是赛后补拉复盘要用的 **gid 清单**（详情 404 后就再也列不出来）。

## 做什么

1 个 GET `/api/tournaments/<tid>`，把 status/stage/qualified/**ranking 全榜**/**my_games** 追加一行到
`var/4test_detail.jsonl`；**只在“变化签名”变了才追加**（`--force` 可强制），末尾带一行摘要方便人看。

红线：只读 + 追加；不杀进程、不改 `bot/`、不碰在途 A/B。网络失败只打印不抛（观察者不制造红噪声）。
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://10.240.169.190:18080"
ME_UID = "u_7a3fba48d70b"   # 2026-09-24 实测 GET /api/me（四测令牌）返回的 user_id


def fetch(tid, tok):
    req = urllib.request.Request(BASE + "/api/tournaments/" + tid,
                                 headers={"Authorization": "Bearer " + tok})
    ctx = ssl._create_unverified_context()
    with urllib.request.urlopen(req, timeout=25, context=ctx) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def signature(d):
    rank = [(x.get("rank"), x.get("user_id"), x.get("total_score"), x.get("games_played"))
            for x in (d.get("ranking") or []) if isinstance(x, dict)]
    canon = json.dumps({"s": d.get("status"), "st": d.get("stage"), "ss": d.get("stage_status"),
                        "q": d.get("qualified"), "qr": d.get("qualify_role"),
                        "sc": d.get("stage_crashed"), "g": d.get("my_games") or [],
                        "r": rank}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(canon.encode("utf-8")).hexdigest()[:16]


def last_sig(path):
    try:
        with io.open(path, encoding="utf-8") as fh:
            lines = [x for x in fh if x.strip()]
        if not lines:
            return None
        return json.loads(lines[-1]).get("sig")
    except Exception:
        return None


def report(path):
    """把 `4test_detail.jsonl` 读成人看的报告：时间线 + 我方名次 + 分数分布。"""
    if not os.path.exists(path):
        print("台账不存在：%s" % path)
        return 2
    recs = []
    with io.open(path, encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln:
                continue
            try:
                recs.append(json.loads(ln))
            except Exception:
                pass
    if not recs:
        print("台账为空：%s" % path)
        return 2
    print("快照 %d 条：%s" % (len(recs), path))
    print("%-19s %-12s %-10s %-10s %6s %6s %8s %8s" %
          ("ts", "status", "stage", "qualified", "榜数", "我局", "我rank", "我分"))
    for r in recs:
        st = r.get("stage")
        stn = st.get("name") if isinstance(st, dict) else st
        me = r.get("me") or {}
        print("%-19s %-12s %-10s %-10s %6s %6s %8s %8s" %
              (r.get("ts"), r.get("status"), stn or "-", r.get("qualified"),
               r.get("n_ranking"), r.get("n_my_games"),
               me.get("rank"), me.get("total_score")))
    last = recs[-1]
    rank = last.get("ranking") or []
    me = last.get("me") or {}
    if rank:
        scores = [x.get("total_score") for x in rank if isinstance(x.get("total_score"), (int, float))]
        pos = sum(1 for x in scores if x > 0)
        neg = sum(1 for x in scores if x < 0)
        print("\n最后快照名次分布：榜上 %d 人；正分 %d 人，负分 %d 人，零分 %d 人" %
              (len(rank), pos, neg, len(scores) - pos - neg))
        if scores:
            print("分数：max=%s  min=%s  中位=%s" %
                  (max(scores), min(scores), sorted(scores)[len(scores) // 2]))
        if me.get("rank"):
            print("我方：rank %s / %d（前 %.1f%%） total_score=%s place_points=%s god_count=%s games_played=%s" %
                  (me.get("rank"), len(rank), 100.0 * me["rank"] / max(1, len(rank)),
                   me.get("total_score"), me.get("place_points"), me.get("god_count"), me.get("games_played")))
        print("\n前 5 名：")
        for x in rank[:5]:
            print("  #%s  score=%-6s place=%-5s god=%-4s games=%-4s %s" %
                  (x.get("rank"), x.get("total_score"), x.get("place_points"),
                   x.get("god_count"), x.get("games_played"), x.get("user_id")))
    else:
        print("\n（最后快照里 ranking 为空 —— 开赛前属正常）")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tid", default="")
    ap.add_argument("--token-file", default="")
    ap.add_argument("--report", action="store_true",
                    help="不联网：把本地台账读成“名次/分数演变 + 分布”报告")
    ap.add_argument("--out", default=os.path.join(ROOT, "var", "4test_detail.jsonl"))
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    if a.report:
        return report(a.out)
    if not a.tid or not a.token_file:
        print("需要 --tid 与 --token-file（或用 --report 读本地台账）")
        return 2
    try:
        tok = io.open(a.token_file, encoding="utf-8-sig").read().strip()
    except Exception as e:
        print("\u26a0 \u8bfb\u4e0d\u5230\u4ee4\u724c\u6587\u4ef6 %s\uff08%s\uff09" % (a.token_file, str(e)[:80]))
        return 0
    try:
        d = fetch(a.tid, tok)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:80]
        print("\u26a0 \u8be6\u60c5 HTTP %s\uff08%s\uff09\u21d2 \u4e0d\u6539\u53f0\u8d26" % (e.code, body))
        return 0
    except Exception as e:
        print("\u26a0 \u8be6\u60c5\u62c9\u53d6\u5931\u8d25 %s\uff08%s\uff09\u21d2 \u4e0d\u6539\u53f0\u8d26" % (type(e).__name__, str(e)[:80]))
        return 0

    ranking = [x for x in (d.get("ranking") or []) if isinstance(x, dict)]
    my_games = d.get("my_games") or []
    sig = signature(d)
    me = next((x for x in ranking if x.get("user_id") == ME_UID), None)
    summary = ("status=%s stage=%s qualified=%s 榜=%d 我方局数=%d 我:rank=%s score=%s games=%s"
               % (d.get("status"), (d.get("stage") or {}).get("name") if isinstance(d.get("stage"), dict) else d.get("stage"),
                  d.get("qualified"), len(ranking), len(my_games),
                  (me or {}).get("rank"), (me or {}).get("total_score"), (me or {}).get("games_played")))
    if not a.force and os.path.exists(a.out) and last_sig(a.out) == sig:
        print("\u65e0\u53d8\u5316 \u21d2 \u4e0d\u8ffd\u52a0\uff1a" + summary)
        return 0
    rec = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "tid": a.tid, "sig": sig,
           "status": d.get("status"), "stage": d.get("stage"), "stage_status": d.get("stage_status"),
           "qualified": d.get("qualified"), "qualify_role": d.get("qualify_role"),
           "stage_crashed": d.get("stage_crashed"),
           "n_ranking": len(ranking), "ranking": ranking,
           "n_my_games": len(my_games), "my_games": my_games, "me": me}
    d_dir = os.path.dirname(a.out)
    if d_dir and not os.path.isdir(d_dir):
        os.makedirs(d_dir, exist_ok=True)
    with io.open(a.out, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    try:
        where = os.path.relpath(a.out, ROOT)
    except Exception:
        where = a.out
    print("\u5df2\u8ffd\u52a0\u2192 %s\uff1a%s" % (where, summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())