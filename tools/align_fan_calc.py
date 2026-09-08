"""fan-calc 真值对齐工具 v2：黄金集原位在线刷新 + v21 边界用例 + 全字段引擎对比。

历史：v1（2026-09-03）曾生成 testdata/fan_calc_golden.json（132 例，含结构化/
chain 变体/随机），于"激进精简"提交中被删除。服务器规则会热更（如 v21
2026-09-07 修订 4白板爆头/豪华组语义）——本地引擎与黄金集都可能过期，因此
本 v2 提供【原位刷新】（以服务器当前响应覆盖缓存 resp）与【引擎对比】
（hu/baotou/fan/detail 全字段），并附 v21 边界用例注入。

用法：
    python tools/align_fan_calc.py            # 离线：本地引擎 vs 黄金集对比
    python tools/align_fan_calc.py --refresh  # 在线：逐例重拉服务器响应后对比
    python tools/align_fan_calc.py --refresh --verify-only  # 只重拉不写盘（漂移侦察）
服务端 fan-calc 限速 10/s/IP：串行 + 0.12s 间隔；429 退避重试。
"""
from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from mahjong.fan import calc as fan_calc_local  # noqa: E402
from mahjong.hu import is_baotou, is_win        # noqa: E402

DEFAULT_OUT = os.path.join(ROOT, "testdata", "fan_calc_golden.json")
BASE = "https://10.240.169.190:18080"
CTX = ssl._create_unverified_context()
FIELDS = ("hu", "baotou", "fan", "detail")

# v21（2026-09-07）边界用例：4白板听任意=爆头（撤销旧裁）、白×4 仅无落单时计豪华组
# 形态与 2026-09-08 服务器实测对齐（fan-calc 输出见注释）。
V21_EDGE_CASES = [
    # A: 3 刻 + 4 白（摸任意皆胡；豪华组仅来自实体四张，白被补单消耗不组豪华）
    (["1w", "1w", "1w", "2b", "2b", "2b", "3t", "3t", "3t", "白", "白", "白", "白"],
     "1w", {"count": 0, "piao": 0}),     # server: 豪华七对×1+4白板+爆头 fan=16
    (["1w", "1w", "1w", "2b", "2b", "2b", "3t", "3t", "3t", "白", "白", "白", "白"],
     "1b", {"count": 0, "piao": 0}),     # server: 七对+4白板+爆头 fan=8
    # B: 3 对 + 3 单 + 4 白（白全部补单 → 无豪华；任意摸皆胡 = 爆头）
    (["1w", "1w", "5b", "5b", "9t", "9t", "东", "南", "中", "白", "白", "白", "白"],
     "北", {"count": 0, "piao": 0}),     # server: 七对+4白板+爆头 fan=8
    (["1w", "1w", "5b", "5b", "9t", "9t", "东", "南", "中", "白", "白", "白", "白"],
     "1w", {"count": 0, "piao": 0}),     # server: 同上 fan=8
    # C: 3 刻 + 3 白 + 单（链/飘叠加边界：手留 3 白 + piao1 = 4 → 4白板 ×2）
    (["1w", "1w", "1w", "2b", "2b", "2b", "3t", "3t", "3t", "白", "白", "白", "东"],
     "1w", {"count": 0, "piao": 0}),     # server: 豪华七对×1+爆头 fan=8
    (["1w", "1w", "1w", "2b", "2b", "2b", "3t", "3t", "3t", "白", "白", "白", "东"],
     "1w", {"count": 1, "piao": 1}),     # server: 豪华七对×1+财飘+4白板+爆头 fan=32
    (["1w", "1w", "1w", "2b", "2b", "2b", "3t", "3t", "3t", "白", "白", "白", "东"],
     "东", {"count": 1, "piao": 1}),     # server: 七对+财飘+4白板+爆头 fan=16
    # D: 双实四张 + 4 白：无落单时白×4 计豪华组；有落单时不组
    (["1w", "1w", "1w", "1w", "2b", "2b", "2b", "2b", "3t", "白", "白", "白", "白"],
     "3t", {"count": 0, "piao": 0}),     # server: 豪华七对×3+4白板+爆头 fan=64
    (["1w", "1w", "1w", "1w", "2b", "2b", "2b", "2b", "3t", "白", "白", "白", "白"],
     "东", {"count": 0, "piao": 0}),     # server: 豪华七对×2+4白板+爆头 fan=32
]


def _fetch_one(payload):
    req = urllib.request.Request(
        BASE + "/portal/api/tools/fan-calc",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=15, context=CTX) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.status == 429:
                time.sleep(1.5)
                continue
            return {"error": "[%d] %s" % (e.code, e.read().decode("utf-8", "replace")[:200])}
    return {"error": "429 persistent"}


def refresh(path, verify_only):
    with open(path, encoding="utf-8") as f:
        records = json.load(f)
    known = set()
    for r in records:
        known.add((tuple(r["hand"]), r["draw"],
                   json.dumps(r.get("chain") or {"count": 0, "piao": 0}, sort_keys=True)))
    added = 0
    for hand, draw, chain in V21_EDGE_CASES:
        key = (tuple(hand), draw, json.dumps(chain, sort_keys=True))
        if key not in known:
            records.append({"hand": hand, "draw": draw, "chain": chain, "resp": {}})
            known.add(key)
            added += 1
    print("黄金集 %d 例（新增 v21 边界 %d）原位刷新 → %s" % (
        len(records), added, path))
    out = []
    for i, r in enumerate(records):
        payload = {"hand": r["hand"], "draw": r["draw"],
                   "chain": r.get("chain") or {"count": 0, "piao": 0}, "base": 1}
        resp = _fetch_one(payload)
        if "error" in resp:
            print("  例 %d 拉取失败: %s" % (i, resp["error"]), flush=True)
        out.append({"hand": r["hand"], "draw": r["draw"],
                    "chain": r.get("chain") or {"count": 0, "piao": 0},
                    "resp": resp})
        if (i + 1) % 10 == 0:
            print("  fetched %d/%d" % (i + 1, len(records)), flush=True)
        time.sleep(0.12)
    if not verify_only:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
    return out


def compare(records):
    """本地引擎 vs 黄金集（hu/baotou/fan/detail 全字段）。返回不一致数。"""
    n_ok = n_diff = 0
    diffs = []
    for r in records:
        resp = r.get("resp") or {}
        if "error" in resp:
            continue
        hand, draw = r["hand"], r["draw"]
        chain = r.get("chain") or {"count": 0, "piao": 0}
        if not resp.get("hu"):
            continue
        srv = {k: resp.get(k) for k in FIELDS}
        mine = fan_calc_local(hand, draw, chain)
        my = {k: mine.get(k) for k in FIELDS}
        if my != srv:
            n_diff += 1
            if len(diffs) < 8:
                diffs.append({"hand": hand, "draw": draw, "chain": chain,
                              "mine": my, "server": srv})
        else:
            n_ok += 1
    print("引擎 vs 黄金集（hu 例，全字段）：一致 %d，不一致 %d" % (n_ok, n_diff))
    for d in diffs:
        print("  DIFF:", json.dumps(d, ensure_ascii=False))
    return n_diff


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--refresh", action="store_true", help="在线原位刷新黄金集")
    ap.add_argument("--verify-only", action="store_true",
                    help="只重拉对比不写盘（漂移侦察）")
    args = ap.parse_args()
    if not os.path.exists(args.out):
        raise SystemExit("黄金集缺失: %s" % args.out)
    if args.refresh or args.verify_only:
        records = refresh(args.out, args.verify_only)
    else:
        with open(args.out, encoding="utf-8") as f:
            records = json.load(f)
        print("复用缓存 %s（%d 例）" % (args.out, len(records)))
    sys.exit(1 if compare(records) else 0)


if __name__ == "__main__":
    main()
