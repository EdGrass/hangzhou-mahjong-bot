# -*- coding: utf-8 -*-
"""正式赛「到位确认」：POST /api/tournaments/{id}/ready（幂等）。

为什么必须显式做这一步：
- 指南 §2.6 / API 表：分桌实到 = **ready ∧ 开赛前 90s 内在线**（有已认证请求）。
- 仓库里**没有任何代码**会提交 ready（2026-09-15 全仓 grep `/ready` 无命中），
  报名只等于「纯意向」，不等于到位 —— 漏了这一步会在开赛时被剔出分桌。
- 幂等：重复调用返回 {"ready":true}，不建房间、不占额度、不影响在跑的自习房。

用法：
    python -X utf8 var/_ready_1024.py            # 提交并校验
    python -X utf8 var/_ready_1024.py --status    # 只读，不提交
"""
from __future__ import annotations
import argparse, json, os, ssl, sys, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# ★ R1315：原来 `TID = "t_65d538e905c5"`（**09-17 二测**）+ 二测令牌文件。
#   这是**开赛当天真正 POST /ready 的那个工具**：裸跑会把到位确认打到**已结束的二测**，
#   而正式赛那场反而没到位 ⇒ **开赛时被剔出分桌**（指南 §2.6）。
#   现在：缺省时 **从 `.official_spec.json` 自取**，再回退到“**门户当前唯一 registering 赛事**”；
#   都取不到就**报错 exit 2**，绝不沿用历史值。
ME = "u_7a3fba48d70b"
SPEC = os.path.join(ROOT, "var", ".official_spec.json")


def _spec():
    try:
        return json.load(open(SPEC, encoding="utf-8-sig"))
    except Exception:
        return {}


def _portal_registering_tid(server):
    """只读：从门户取“当前 registering”的赛事；恰好一个才采用。"""
    ck = open(os.path.join(ROOT, "var", ".portal_cookie"), encoding="utf-8-sig").read().strip()
    req = urllib.request.Request(server + "/portal/api/tournaments", headers={"Cookie": ck})
    with urllib.request.urlopen(req, timeout=20, context=ssl._create_unverified_context()) as r:
        d = json.loads(r.read().decode("utf-8", "replace"))
    ts = d if isinstance(d, list) else (d.get("tournaments") or [])
    reg = [t for t in ts if str(t.get("status")) == "registering" and t.get("id")]
    if len(reg) == 1:
        return str(reg[0]["id"]), str(reg[0].get("name") or "")
    if len(reg) > 1:
        raise RuntimeError("门户有多个 registering 赛事（%s），请显式传 --tid"
                           % ", ".join(str(t.get("id")) for t in reg))
    return "", ""


def _call(base, tok, path, method="GET"):
    req = urllib.request.Request(base + path, method=method,
                                 headers={"Authorization": "Bearer " + tok})
    ctx = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, timeout=25, context=ctx) as r:
            return r.status, json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            body = json.loads(body)
        except Exception:
            pass
        return e.code, body


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tid", default="", help="缺省：.official_spec.json → 门户唯一 registering 赛事")
    ap.add_argument("--token-file", default="", help="缺省：.official_spec.json → var/.global_token")
    ap.add_argument("--server", default="https://10.240.169.190:18080")
    ap.add_argument("--status", action="store_true", help="只读查询，不提交 ready")
    args = ap.parse_args(argv)

    _sp = _spec()
    _src = []
    _tid_src = ""
    if not args.tid:
        args.tid = str(_sp.get("tournament_id") or "")
        if args.tid:
            _tid_src = "spec"
            _src.append("tid←.official_spec.json")
    if not args.tid:
        try:
            _t, _n = _portal_registering_tid(args.server)
            if _t:
                args.tid = _t
                _tid_src = "portal"
                _src.append("tid←门户 registering赛事(%s)" % _n)
        except Exception as e:
            print("⚠ 门户查询失败：%s" % str(e)[:120])
    if not args.tid:
        print("❌ 无法确定 --tid（spec 无 tournament_id、门户也没有唯一 registering 赛事）"
              "（拒绝沿用历史默认值 t_65d538e905c5 = 09-17 二测）")
        return 2
    if not args.token_file:
        if _tid_src == "spec":
            args.token_file = str(_sp.get("token_file") or "")
        if not args.token_file:
            args.token_file = os.path.join(ROOT, "var", ".global_token")
            if _tid_src == "portal":
                print("⚠ tid 来自门户（当前 registering），令牌回退到 var/.global_token"
                      "（spec 里的令牌属于别场，已忽略；若需用赛事令牌请显式 --token-file）")
        _src.append("token←%s" % os.path.basename(args.token_file))
    if not os.path.isabs(args.token_file):
        args.token_file = os.path.join(ROOT, args.token_file)
    if not os.path.exists(args.token_file):
        print("❌ 令牌文件不存在：%s" % args.token_file)
        return 2
    print("目标：tid=%s  token_file=%s  (%s)"
          % (args.tid, os.path.relpath(args.token_file, ROOT), "；".join(_src) or "显式传参"))

    tok = open(args.token_file, encoding="utf-8").read().strip()
    if not tok:
        print("FAIL 令牌文件为空: %s" % args.token_file)
        return 2

    st, d = _call(args.server, tok, "/api/tournaments/%s" % args.tid)
    if st != 200:
        print("FAIL 赛事详情 HTTP %s %s" % (st, str(d)[:160]))
        return 2
    print("status=%s  registered=%s  ready=%s  my_games=%d"
          % (d.get("status"), d.get("registered_users"), d.get("ready_users"),
             len(d.get("my_games") or [])))
    if args.status:
        return 0
    if str(d.get("status")) != "registering":
        print("SKIP 非报名期（status=%s）——ready 只在开赛前提交" % d.get("status"))
        return 0
    st, r = _call(args.server, tok, "/api/tournaments/%s/ready" % args.tid, method="POST")
    if st != 200 or not (isinstance(r, dict) and r.get("ready")):
        print("FAIL POST /ready HTTP %s %s" % (st, str(r)[:200]))
        return 2
    st2, d2 = _call(args.server, tok, "/api/tournaments/%s" % args.tid)
    print("OK   ready=%s  (赛事 ready 人数 %s → %s)"
          % (r, d.get("ready_users"), (d2 or {}).get("ready_users")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
