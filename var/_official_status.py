# -*- coding: utf-8 -*-
"""正式赛状态一览（开赛当天用）：锦标赛 status / 阶段 / 我的资格 / 阶段排名 / 活跃场次。

用法：python -X utf8 var/_official_status.py
"""
import io, argparse, json, os, ssl, sys, urllib.request, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# ★ R1314：原来这里写死 `TID = "t_65d538e905c5"`（**09-17 二测**）。自己的注释都写了
#   “默认仍是 09-17 二测…会让开赛当天的状态一览看的是**上一场**比赛”，但默认值一直没改。
#   现在：**从 `var/.official_spec.json` 自取**（`_switch_to_official.ps1` 会把当前赛事的
#   strategy/token_file/tournament_id 写进去）；取不到就**报错**，绝不沿用历史值。
#   可用环境变量 `HM_OFFICIAL_SPEC` 指向别的 spec（供测试）。
ME = "u_7a3fba48d70b"
SPEC = os.environ.get("HM_OFFICIAL_SPEC") or os.path.join(ROOT, "var", ".official_spec.json")


def _spec():
    try:
        return json.load(io.open(SPEC, encoding="utf-8-sig"))
    except Exception:
        return {}


def main(argv=None):
    # ★ 2026-09-17：赛事 id / 令牌文件改成可传参（默认仍是 09-17 二测）。
    #   原因同 `_switch_to_official.ps1`：一个月后的正式赛会换赛事与令牌，
    #   写死默认值会让开赛当天的"状态一览"看的是**上一场**比赛（误判资格/名次）。
    ap = argparse.ArgumentParser()
    ap.add_argument("--tid", default="", help="缺省时从 var/.official_spec.json 取")
    ap.add_argument("--token-file", default="", help="缺省时从 var/.official_spec.json 取")
    a = ap.parse_args(argv)
    sp = _spec()
    if not a.tid:
        a.tid = str(sp.get("tournament_id") or "")
    if not a.token_file:
        a.token_file = str(sp.get("token_file") or "")
    if not a.tid:
        print("❌ 未指定 --tid，且 %s 里没有 tournament_id"
              "（拒绝沿用历史默认值 t_65d538e905c5 = 09-17 二测）" % SPEC)
        return 2
    if not a.token_file:
        a.token_file = os.path.join(ROOT, "var", ".global_token")
    tok_path = a.token_file if os.path.isabs(a.token_file) else os.path.join(ROOT, a.token_file)
    if not os.path.exists(tok_path):
        print("❌ 令牌文件不存在：%s" % tok_path)
        return 2
    TID_ = a.tid
    tok = open(tok_path, encoding="utf-8").read().strip()
    ctx = ssl._create_unverified_context()
    base = "https://10.240.169.190:18080"

    def get(path):
        req = urllib.request.Request(base + path, headers={"Authorization": "Bearer " + tok})
        with urllib.request.urlopen(req, timeout=25, context=ctx) as r:
            return json.loads(r.read().decode("utf-8", "replace"))

    print("=" * 70)
    print("正式赛状态  %s  tid=%s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), TID_))
    try:
        t = get("/api/tournaments/%s" % TID_)
    except Exception as e:
        print("详情获取失败:", type(e).__name__, str(e)[:120]); return
    st = t.get("stage") if isinstance(t.get("stage"), dict) else {}
    print("status=%s  stage=%s(%s)  stage_status=%s  crashed=%s" % (
        t.get("status"), st.get("name"), st.get("no"), t.get("stage_status"), t.get("stage_crashed")))
    print("qualified=%s  qualify_role=%s" % (t.get("qualified"), t.get("qualify_role")))
    cfg = t.get("config") or {}
    print("config: M=%s Rounds=%s base=%s" % (cfg.get("M"), cfg.get("Rounds"), cfg.get("BaseScore")))
    rk = t.get("ranking") or []
    if rk:
        mine = [x for x in rk if x.get("user_id") == ME]
        print("阶段榜：共 %d 行；我方 %s" % (
            len(rk), json.dumps(mine[0], ensure_ascii=False) if mine else "未在榜内"))
        top = sorted(rk, key=lambda x: -(x.get("total_score") or 0))[:3]
        for x in top:
            print("   top: rank=%s score=%s pp=%s %s" % (
                x.get("rank"), x.get("total_score"), x.get("place_points"), (x.get("name") or "")[:14]))
    try:
        me = get("/api/me")
        ag = me.get("active_games") or []
        print("active_games: %d %s" % (len(ag), json.dumps(ag, ensure_ascii=False)[:200]))
    except Exception as e:
        print("me 获取失败:", str(e)[:100])
    print("=" * 70)


if __name__ == "__main__":
    sys.exit(main())
