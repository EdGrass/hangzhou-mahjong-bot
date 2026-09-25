# -*- coding: utf-8 -*-
"""`var/_arm_path_audit.py` —— **"臂的预期路径真的跑了吗"批量审计**（只读，R1229）。

## 为什么（R1228 的教训）

我造的**组合臂** `speedvaluebcmeld` 第一版漏了 `self.stats` ⇒ `_bc_pick` 抛异常 ⇒ 被上层兜底成 `_best_discard`
⇒ **臂看起来在跑，其实跑的是另一条策略**（足迹 16% → 31%）。这类"**静默变形**"只有靠
"**行为足迹 + 内部计数器**"才能抓到，光看"能实例化、有单测"是抓不到的。

本工具把这件事**一条命令化**：对每个臂在**同一批真实局面**上跑，报：
- **与基线的分歧率**（draw 层按 tile 不同、window 层按 action 不同）；
- **内部计数器**（`stats`：used/changed/fallback —— BC/ranker 系）与"模型是否加载"；
- **红旗**：① 臂有模型/排序器却 **0 分歧**（疑似静默兜底）② `fallback > 0`（路径被异常吃掉）③ action 差异 > 0（draw 层不该有）。

用法：
    python -X utf8 var/_arm_path_audit.py --arms speedvaluebc,speedc151bc,speedvaluemeld,speedvaluerank,speedvalueplain,speedvaluebcmeld
    python -X utf8 var/_arm_path_audit.py --arms speedvaluemeld,speedvaluebcmeld --phase window --files 120
"""
from __future__ import annotations
import argparse, collections, glob, io, json, os, random, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "tools"))
from offline_replay import to_view, draws       # noqa: E402


def sample_records(n_files, seed=0):
    files = sorted(glob.glob(os.path.join(ROOT, "var", "replays", "auto_*", "*.dec.jsonl")))
    random.seed(seed)
    files = random.sample(files, min(n_files, len(files))) if files else []
    recs = list(draws(files))
    return recs


def counters_of(p):
    out = {}
    for attr in ("stats",):
        c = getattr(p, attr, None)
        if isinstance(c, collections.Counter):
            out.update({k: int(v) for k, v in c.items()})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", required=True, help="逗号分隔的臂名")
    ap.add_argument("--baseline", default="speedvalue")
    ap.add_argument("--files", type=int, default=120, help="抽多少个 dec 文件")
    ap.add_argument("--phase", default="draw", choices=["draw", "window"])
    ap.add_argument("--limit", type=int, default=3000, help="最多评估多少个决策")
    ap.add_argument("--allow-zero", default="",
                    help="允许在该阶段 0 分歧的臂（逗号分隔）——如只会动索取层的 speedvaluemeld 在 draw 层")
    a = ap.parse_args()

    from run_bot import STRATEGY_FACTORIES as F
    if a.baseline not in F:
        print("基线未注册：%s" % a.baseline)
        return 2
    base = F[a.baseline]()
    arms = [x.strip() for x in a.arms.split(",") if x.strip()]
    allow_zero = {x.strip() for x in a.allow_zero.split(",") if x.strip()}

    if a.phase == "draw":
        recs = sample_records(a.files)[:a.limit]
        views = [to_view(r) for r in recs]
    else:
        # ★ window 阶段不能复用 `draws()`（那个函数只产出 phase=draw 的记录 ⇒ 会得到 0 个局面）；
        #   这里直接读 dec 文件，只取 response_peng / response_chi。
        files = sorted(glob.glob(os.path.join(ROOT, "var", "replays", "auto_*", "*.dec.jsonl")))
        random.seed(0)
        files = random.sample(files, min(a.files, len(files))) if files else []
        views = []
        for f in files:
            for ln in io.open(f, encoding="utf-8", errors="ignore"):
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    r = json.loads(ln)
                except Exception:
                    continue
                if (r.get("p") or "") in ("response_peng", "response_chi"):
                    views.append(to_view(r))
                if len(views) >= a.limit:
                    break
            if len(views) >= a.limit:
                break

    print("=" * 96)
    print("臂路径审计（phase=%s，基线=%s，局面 %d 个）" % (a.phase, a.baseline, len(views)))
    print("=" * 96)
    print("%-20s %9s %9s %9s %s" % ("臂", "分歧率", "action差", "异常", "内部计数器/红旗"))
    bad = []
    # 基线自身先跑一遍（缓存结果，避免每臂重复）
    bres = []
    for v in views:
        try:
            d = base.decide(v) or {}
        except Exception:
            d = {}
        bres.append((d.get("action"), str(d.get("tile") or "")))

    for name in arms:
        if name not in F:
            print("%-20s %9s" % (name, "未注册"))
            bad.append("%s 未注册" % name)
            continue
        try:
            p = F[name]()
        except Exception as e:
            print("%-20s %9s" % (name, "实例化失败"))
            bad.append("%s 实例化失败：%s" % (name, e))
            continue
        has_model = any(getattr(p, at, None) is not None for at in ("model", "ranker", "_mnet"))
        ndiff = nact = nerr = 0
        for v, (ba, bt) in zip(views, bres):
            try:
                d = p.decide(v) or {}
            except Exception:
                nerr += 1
                continue
            da, dt = d.get("action"), str(d.get("tile") or "")
            if da != ba:
                nact += 1
            elif dt != bt:
                ndiff += 1
        n = max(1, len(views))
        rate = 100.0 * (ndiff + nact) / n
        cnt = counters_of(p)
        flags = []
        notes = []
        # ★ R1514：**副露层臂在 draw 层 0 分歧是预期**（它们只在**索取层**动作）——
        #   原判据会把它们误报成“有模型却 0 分歧（疑似静默兜底）”，而预登记的“起役命令”第 1 条正是 draw 层审计
        #   ⇒ 有人照命令跑就会看到“❌ 红旗”，可能因此**拒绝起役**。R1514 实测：三根副露层候选 draw 层 0.0%、
        #   window 层 0.5% / 3 个 action 变化 ⇒ 层是活的。故：draw 层 + 副露层臂 ⇒ **只给提示，不计红旗**；其余不变。
        _meld_layer = "meld" in name.lower()
        if has_model and rate == 0.0 and name not in allow_zero and not (a.phase == "draw" and _meld_layer):
            flags.append("⚠ 有模型却 0 分歧（疑似静默兜底）")
        if a.phase == "draw" and _meld_layer and rate == 0.0:
            notes.append("ⓘ 副露层臂：draw 层 0 分歧属预期 ⇒ 请用 --phase window 复查索取层")
        if cnt.get("fallback"):
            flags.append("⚠ fallback=%d（路径被异常吃掉）" % cnt["fallback"])
        if a.phase == "draw" and nact:
            flags.append("⚠ draw 层出现 action 差异 %d" % nact)
        if nerr:
            flags.append("⚠ 异常 %d" % nerr)
        info = (" ".join("%s=%d" % (k, v) for k, v in sorted(cnt.items())) or "-")
        print("%-20s %8.1f%% %9d %9d %s %s" % (name, rate, nact, nerr, info, " ".join(flags + notes)))
        if flags:
            bad.append("%s：%s" % (name, "；".join(flags)))
    print()
    if bad:
        print("❌ 有 %d 个臂存在红旗：" % len(bad))
        for b in bad:
            print("   - " + b)
        return 2
    print("✅ 全部臂的行为路径看起来正常（无兜底/无异常；0 分歧的副露层臂已注明“请用 --phase window 复查”）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
