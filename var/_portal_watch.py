# -*- coding: utf-8 -*-
"""`var/_portal_watch.py` \u2014\u2014 **\u95e8\u6237\u8d5b\u4e8b/\u516c\u544a\u53ea\u8bfb\u5feb\u7167\u5668**\uff08\u4e0d\u7528\u4ee4\u724c\uff0c\u53ea\u7528\u95e8\u6237 cookie\uff09\u3002

\u4e3a\u4ec0\u4e48\uff1a\u56db\u6d4b\uff08t_6266386bfd56\uff09\u662f**\u6211\u4eec\u5076\u7136\u67e5\u95e8\u6237\u624d\u53d1\u73b0\u7684**\uff08\u5f53\u65f6\u8ddd\u62a5\u540d\u622a\u6b62\u53ea\u5269 ~5h\uff09\u3002
\u8fd9\u4e2a\u5de5\u5177\u628a\u201c\u95e8\u6237\u770b\u5230\u4e86\u4ec0\u4e48\u201d**\u6309\u65f6\u95f4\u6233\u8bb0\u4e0b\u6765**\uff08\u8ffd\u52a0\u5f0f\u5386\u53f2\uff09\uff0c\u8fd9\u6837\uff1a
  * \u65b0\u8d5b\u4e8b\u4e00\u51fa\u73b0\u5c31\u80fd\u770b\u51fa\u201c\u5b83\u662f\u54ea\u4e00\u523b\u51fa\u73b0\u7684\u201d\uff1b
  * 10/10 \u6b63\u5f0f\u8d5b\u7684 tid \u4e00\u65e6\u4e0a\u7ebf\uff0c\u53ef\u7acb\u523b\u8dd1 `_format_fidelity.py`\u3002

\u53ea\u8bfb\uff1aGET /portal/api/tournaments \u4e0e /portal/api/announcements\u3002 **\u4e0d\u53d1 POST\u3001\u4e0d\u78b0\u5bf9\u5c40\u3001\u4e0d\u6539\u4efb\u4f55\u914d\u7f6e**\u3002

\u7528\u6cd5\uff1a
    python -X utf8 var/_portal_watch.py            # \u91c7\u4e00\u6b21\u5feb\u7167\u5e76\u8ffd\u52a0\u5230 var/_portal_history.jsonl
    python -X utf8 var/_portal_watch.py --show     # \u53ea\u6253\u5370\u5f53\u524d\u72b6\u6001\uff0c\u4e0d\u5199\u5386\u53f2
"""
from __future__ import annotations
import argparse, datetime as dt, io, json, os, ssl, sys, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://10.240.169.190:18080"
CK = os.path.join(ROOT, "var", ".portal_cookie")
HIST = os.path.join(ROOT, "var", "_portal_history.jsonl")


def _get(path, cookie):
    ctx = ssl._create_unverified_context()
    req = urllib.request.Request(BASE + path, headers={"Cookie": cookie} if cookie else {})
    try:
        with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
            return r.status, json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode("utf-8", "replace")[:200]}
    except Exception as e:
        return 0, {"error": "%s: %s" % (type(e).__name__, str(e)[:160])}


def f(x):
    return dt.datetime.fromtimestamp(int(x)).strftime("%Y-%m-%d %H:%M:%S") if x else "-"


def snapshot():
    ck = ""
    try:
        ck = io.open(CK, encoding="utf-8-sig").read().strip()
    except Exception:
        pass
    st_t, d_t = _get("/portal/api/tournaments", ck)
    ts = []
    if isinstance(d_t, list):
        ts = d_t
    elif isinstance(d_t, dict):
        ts = d_t.get("tournaments") or d_t.get("items") or []
    st_a, d_a = _get("/portal/api/announcements", ck)
    anns = (d_a or {}).get("announcements") if isinstance(d_a, dict) else []
    return {
        "ts": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tournaments_http": st_t,
        "tournaments": [{"id": t.get("id"), "name": t.get("name"), "status": t.get("status"),
                         "start_at": t.get("start_at"), "register_deadline": t.get("register_deadline"),
                         "registered": t.get("registered"), "my_registered": t.get("my_registered")}
                        for t in ts],
        "announcements_http": st_a,
        "announcement_ids": [a.get("id") for a in (anns or [])],
        "announcement_titles": [a.get("title") for a in (anns or [])],
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true", help="\u53ea\u6253\u5370\uff0c\u4e0d\u5199\u5386\u53f2")
    a = ap.parse_args(argv)
    s = snapshot()
    print("\u5feb\u7167 %s  \u8d5b\u4e8b %d \u4e2a\uff08HTTP %s\uff09\uff0c\u516c\u544a %d \u6761\uff08HTTP %s\uff09"
          % (s["ts"], len(s["tournaments"]), s["tournaments_http"],
             len(s["announcement_ids"]), s["announcements_http"]))
    for t in s["tournaments"]:
        print("  \u8d5b\u4e8b id=%s | %s | status=%s | \u5f00\u8d5b=%s | \u622a\u6b62=%s | \u5df2\u62a5\u540d=%s | \u6211\u5df2\u62a5\u540d=%s"
              % (t["id"], t["name"], t["status"], f(t["start_at"]), f(t["register_deadline"]),
                 t["registered"], t["my_registered"]))
    for i, (i2, t2) in enumerate(zip(s["announcement_ids"], s["announcement_titles"])):
        print("  \u516c\u544a %s | %s" % (i2, t2))
    if a.show:
        return 0
    prev = {}
    if os.path.exists(HIST):
        try:
            lines = io.open(HIST, encoding="utf-8").read().strip().splitlines()
            if lines:
                prev = json.loads(lines[-1])
        except Exception:
            prev = {}
    with io.open(HIST, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(s, ensure_ascii=False) + "\n")
    # \u53d8\u5316\u63d0\u9192\uff08\u4ec5\u5bf9\u6bd4\u201c\u8d5b\u4e8b\u96c6\u5408 / \u516c\u544a\u96c6\u5408\u201d\uff09
    old_t = {t["id"] for t in prev.get("tournaments", [])}
    new_t = {t["id"] for t in s["tournaments"]}
    old_a = set(prev.get("announcement_ids") or [])
    new_a = set(s["announcement_ids"])
    if prev and (new_t - old_t):
        print("\u2605 \u65b0\u8d5b\u4e8b\uff1a%s" % ", ".join(sorted(new_t - old_t)))
    if prev and (new_a - old_a):
        print("\u2605 \u65b0\u516c\u544a\uff1a%s" % ", ".join(sorted(new_a - old_a)))
    print("(\u5df2\u8ffd\u52a0\u5230 %s)" % os.path.relpath(HIST, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())