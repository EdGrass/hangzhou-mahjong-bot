# -*- coding: utf-8 -*-
"""生成**固定版门禁语料**（`var/smoke_corpus_v1.jsonl`）—— 一次性工具，产物才是权威。

动机（R873/R874）：`var/_concurrency_bench.py` 原来按 **mtime 取最近 80 个文件**，
每跑一房语料就整体位移 ⇒ 同一个臂在不同时刻跑出的 p95/max **不可比**，
而它正是决定候选能否上臂的 **M=10 延迟门禁**（c135d 的风险全在尾部）。
⇒ 把语料钉成**版本化文件**：同一份文件、同一批局面，跨天跨臂都可复现。

语料构成（**四类混合**，覆盖正式赛会遇到的决策形态）：
  - `draw`      ：摸牌后弃牌（常规），含早/中/晚局（river 长度分散）
  - `late`      ：river>=30 的晚局弃牌（向听计算最重的形态）
  - `live`      ：**手牌本来就能吃/碰**的 window 局面（副露路径 —— 历史上延迟爆的就是这条）
  - `claim`     ：**当时真的副露了**的 window 局面（副露决策的实际分支）
抽样方式：**均匀等距**（不是随机）⇒ 不需要 seed，任何人重跑同一语料得到同一子集。

用法：
    python -X utf8 tools/make_smoke_corpus.py --rooms 60 --out var/smoke_corpus_v1.jsonl
"""
from __future__ import annotations
import argparse, glob, hashlib, io, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from arm_smoke import can_act   # noqa: E402


def pick(pool, k):
    """\u5747\u5300\u7b49\u8ddd\u53d6 k \u4e2a\uff08\u4e0d\u968f\u673a\uff09\u3002"""
    n = len(pool)
    if n <= k:
        return list(pool)
    return [pool[i * n // k] for i in range(k)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rooms", type=int, default=60)
    ap.add_argument("--draw", type=int, default=200)
    ap.add_argument("--late", type=int, default=80)
    ap.add_argument("--live", type=int, default=240)
    ap.add_argument("--claim", type=int, default=80)
    ap.add_argument("--out", default="var/smoke_corpus_v1.jsonl")
    a = ap.parse_args()

    dirs = sorted(glob.glob(os.path.join(ROOT, "var", "replays", "auto_*")))[-a.rooms:]
    draw, late, live, claim = [], [], [], []
    for dd in dirs:
        for f in sorted(glob.glob(os.path.join(dd, "*_t0.dec.jsonl"))):
            for ln in io.open(f, encoding="utf-8"):
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    r = json.loads(ln)
                except Exception:
                    continue
                p = str(r.get("p") or "")
                if p == "draw" and r.get("d") and len(r.get("h") or []) == 14:
                    draw.append(r)
                    if len(r.get("r") or []) >= 30:
                        late.append(r)
                elif p.startswith("response_") and r.get("o"):
                    if can_act(r):
                        live.append(r)
                    if (r.get("a") or {}).get("action") not in (None, "", "pass"):
                        claim.append(r)

    sel = []
    for pool, k, name in ((draw, a.draw, "draw"), (late, a.late, "late"),
                          (live, a.live, "live"), (claim, a.claim, "claim")):
        got = pick(pool, k)
        print("%-6s pool=%6d -> picked %4d" % (name, len(pool), len(got)))
        sel.extend(got)

    # \u53bb\u91cd\uff08\u540c\u4e00\u6761\u8bb0\u5f55\u53ef\u80fd\u540c\u65f6\u5165 draw/late\uff09
    seen = set()
    uniq = []
    for r in sel:
        key = json.dumps(r, sort_keys=True, ensure_ascii=False)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)

    out = a.out if os.path.isabs(a.out) else os.path.join(ROOT, a.out)
    with io.open(out, "w", encoding="utf-8", newline="\n") as fh:
        for r in uniq:
            fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    h = hashlib.sha256()
    with io.open(out, "rb") as fh:
        h.update(fh.read())
    print("wrote %d records -> %s" % (len(uniq), out))
    print("sha256 = %s" % h.hexdigest()[:16])


if __name__ == "__main__":
    raise SystemExit(main())
