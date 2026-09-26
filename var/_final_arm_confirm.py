# -*- coding: utf-8 -*-
"""`var/_final_arm_confirm.py` —— **10/7 换臂前把 `.final_arm.txt` 补上**。

## 为什么要有它

10/7 09:00 的 `_switch_final.py` 是**故障关闭**的：`var/.final_arm.txt` 不在就拒绝执行
（宁可不换也不猜）。而 10/5 的 `_final_pick_proposal.py` 只出**提案**，把提案写成
`.final_arm.txt` 一直是**人工 echo** —— 这是整条链上最后一个、也是唯一一个"无人值守时会断"
的地方。用户 2026-09-25 指令「在七号换上你能搓出来的最屌的模型 准备最后的比赛」，
§V.160 已把裁决权下放，这里就把"没人来写"这个断点补上。

## 口径（写死：只叠已判正的层；§V.161/§V.165/§V.167）

- **baseline** = 已采用链的**尖端**：优先取 `var/.ab_mode` 的 `bundles[0]`（`_bsegment`
  每切一役都把采用的赢家写进 bundles）；A/B 已停（无 `.ab_mode`）时退到
  `var/_keeper_strategy.txt`（驱动正常退出时会把基线写回那里）。
- **candidates** = `.ab_mode` 的臂集去掉 baseline；无 `.ab_mode` 时取台账里出现过的全部臂。
  这只是"提名"，**能不能上由判词决定**。
- 某臂 **合格 iff**：在 `var/_verdict_<label>.txt` 里**提到它的那些文件中最新的一份**，
  其最后一条 `★ 判定：` 行以 `ADOPT` 开头。
  （"最新一份"这个限定是防"早期 ADOPT、后来 REFUSE"被陈旧结论顶掉。）
- 结论：**有合格 candidate ⇒ 取判词最新的那个（＝更深的层）；否则取 baseline**
  （不赌从未判正过的组合臂）。
- 臂名匹配走**整词**正则 —— 否则 `speedvaluebc` 会被 `speedvaluebcvmeld` 的判词命中。

## 红线

- **人工已写就不覆盖**（`.final_arm.txt` 存在且非空 ⇒ 直接 no-op 退出，绝不抢人工的裁决）；
- 落盘前用 `run_bot.STRATEGY_FACTORIES` 做**真实实例化**校验；未注册/不能实例化 ⇒ **拒绝写**
  并留 `var/.FINAL_ARM_UNRESOLVED`；
- 不碰任何进程、不改 `.ab_mode`、不改 `_keeper_strategy.txt`。

用法：
    python -X utf8 var/_final_arm_confirm.py --dry-run    # 只打印会写什么
    python -X utf8 var/_final_arm_confirm.py --go         # 真写
"""
from __future__ import annotations
import argparse
import glob
import io
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AB = os.path.join(ROOT, "var", ".ab_mode")
KEEPER_STRAT = os.path.join(ROOT, "var", "_keeper_strategy.txt")
LEDGER = os.path.join(ROOT, "var", "auto_ranking.jsonl")
FINAL_ARM = os.path.join(ROOT, "var", ".final_arm.txt")
OUT_TXT = os.path.join(ROOT, "var", "_final_arm_confirm.txt")
LOG = os.path.join(ROOT, "var", "_final_arm_confirm.log")
UNRESOLVED = os.path.join(ROOT, "var", ".FINAL_ARM_UNRESOLVED")
VERDICT_GLOB = os.path.join(ROOT, "var", "_verdict_*.txt")

LAST = "\u2605 \u5224\u5b9a\uff1a"  # ★ 判定：


def log(msg):
    line = "%s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    print(line)


def read_text(path):
    """读一个小文本文件（不存在/读失败 ⇒ ""），句柄必关。"""
    try:
        with io.open(path, encoding="utf-8-sig") as f:
            return f.read().strip()
    except Exception:
        return ""


def receipt_conclusion():
    """上回本脚本写的结论（从回执里解析「结论：」行）；解析不出 ⇒ ""。"""
    for ln in read_text(OUT_TXT).splitlines():
        if ln.startswith("结论："):
            return ln.split("结论：", 1)[1].strip()
    return ""


def mentions(text, arm):
    """整词匹配：`speedvaluebc` 不得命中 `speedvaluebcvmeld`。"""
    if not text or not arm:
        return False
    return re.search(r"(?<![0-9A-Za-z_])%s(?![0-9A-Za-z_])" % re.escape(arm), text) is not None


def last_verdict(text):
    """最后一条 `★ 判定：` 行的内容；没有则 None。"""
    hit = None
    for ln in (text or "").splitlines():
        if LAST in ln:
            hit = ln.split(LAST, 1)[1].strip()
    return hit


def load_verdicts(paths=None):
    out = []
    for p in sorted(paths if paths is not None else glob.glob(VERDICT_GLOB)):
        base = os.path.basename(p)
        if base.startswith("_verdict_watch") or ".bak" in base:
            continue
        # ★ R1567：`_verdict_digest_*.txt` 是**摘要报告**，不是判词 —— 而它同一命名空间 +比判词更新 +
        #   正文里提到所有臂，会把别人的 ADOPT 算到本臂头上（实测假阳性，见下方 arm_adopted）。
        if base.startswith("_verdict_digest"):
            continue
        try:
            with io.open(p, encoding="utf-8-sig", errors="replace") as f:
                txt = f.read()
        except Exception:
            continue
        try:
            mt = os.path.getmtime(p)
        except Exception:
            mt = 0.0
        out.append({"path": p, "name": base, "text": txt, "mtime": mt,
                    "last": last_verdict(txt)})
    return out


def about_arm(text, arm):
    """这份判词**是不是关于这个臂**的 —— 认 `_gate2` 头行里的 `vs <arm>（候选）`（逐字）。

    ★ R1567（高危修正）：旧实现用 `mentions(text, arm)`（“文件里**提到过**这个臂”）+“末条以 ADOPT 开头”，
    **不核对 ADOPT 点名的是谁** ⇒ 两种真实误判：
      · **假阳性**：一份提到多臂的文件（尤其是 `_verdict_digest_*` 报告，正是读卡要求人在判词当天跑的那条）
        会把**别的臂的 ADOPT** 记到本臂头上 ⇒ 10/7 可能装上**从未判正的臂**（踩 §V.161 A.1 红线）；
      · **假阴性**：报告的末条恰好是 UNDECIDED 时，会把**真判正**的层遮蔽掉 ⇒ 最终臂退回基线。
    现在：只有“这份判词头行点名的**候选**就是它”才算数；认不出头行 ⇒ 不算（fail-closed，宁可退基线）。
    """
    if not text or not arm:
        return False
    if not mentions(text, arm):        # 先要求文件里确实整词出现过它
        return False
    m = re.search(r"vs\s+([0-9A-Za-z_]+)\s*（候选）", text)
    return bool(m) and m.group(1) == arm


def arm_adopted(arm, verdicts):
    """该臂**最新**一份（**关于它的**）判词若判 ADOPT ⇒ 返回那份判词，否则 None。"""
    hits = [v for v in verdicts if about_arm(v["text"], arm)]
    if not hits:
        return None
    hits.sort(key=lambda v: (v["mtime"], v["name"]), reverse=True)
    v = hits[0]
    if (v["last"] or "").upper().startswith("ADOPT"):
        return v
    return None


def decide(baseline, candidates, verdicts):
    """纯函数。-> (arm, eligible, chosen_verdict)；eligible = [(arm, verdict), ...] 按判词新到旧。"""
    elig = []
    for c in candidates:
        if not c or c == baseline:
            continue
        v = arm_adopted(c, verdicts)
        if v:
            elig.append((c, v))
    elig.sort(key=lambda x: (x[1]["mtime"], x[1]["name"]), reverse=True)
    if elig:
        return elig[0][0], elig, elig[0][1]
    return baseline, elig, None


def read_ab(path=None):
    """-> (baseline, candidates)；无 `.ab_mode` ⇒ (None, [])。"""
    try:
        with io.open(path or AB, encoding="utf-8-sig") as f:
            cfg = json.loads(f.read())
    except Exception:
        return None, []
    if isinstance(cfg.get("arms"), list):
        allarms = [str(x) for x in cfg["arms"]]
    else:
        allarms = [str(x) for x in (cfg.get("a"), cfg.get("b")) if x]
    bundles = cfg.get("bundles") or []
    baseline = str(bundles[0]) if bundles else (allarms[0] if allarms else None)
    return baseline, [x for x in allarms if x != baseline]


def ledger_arms(path=None):
    arms = []
    seen = set()
    try:
        for ln in io.open(path or LEDGER, encoding="utf-8", errors="ignore"):
            ln = ln.strip()
            if not ln:
                continue
            try:
                a = json.loads(ln).get("strategy")
            except Exception:
                continue
            if a and a not in seen:
                seen.add(a)
                arms.append(a)
    except Exception:
        pass
    return arms


def arm_ok(name):
    """真实实例化校验（与 `_switch_final.arm_ok` 同口径）。"""
    sys.path.insert(0, ROOT)
    try:
        from run_bot import STRATEGY_FACTORIES as F
    except Exception as e:
        return False, "无法导入 run_bot（%s）" % str(e)[:60]
    if name not in F:
        return False, "未注册到 run_bot.py"
    try:
        F[name]()
    except Exception as e:
        return False, "实例化失败（%s: %s）" % (type(e).__name__, str(e)[:60])
    return True, "ok"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true", help="真写（默认只 dry-run）")
    ap.add_argument("--dry-run", action="store_true", help="与默认同义，取明确语义")
    ap.add_argument("--out", default=FINAL_ARM, help="目标文件（测试用）")
    ap.add_argument("--verdicts", nargs="*", default=None, help="判词文件（测试用；默认全扫）")
    ap.add_argument("--ab", default=AB, help=".ab_mode 路径（测试用）")
    ap.add_argument("--keeper", default=KEEPER_STRAT, help="_keeper_strategy.txt 路径（测试用）")
    ap.add_argument("--ledger", default=LEDGER, help="台账路径（测试用）")
    ap.add_argument("--refresh", action="store_true",
                    help="重算：只在「更深的已判正层」出现时升级**本脚本自己写过**的臂；人工裁决一律不动")
    a = ap.parse_args(argv)

    # 0) 目标文件已在位
    cur = read_text(a.out)
    if cur and not a.refresh:
        log("人工/既有裁决已在位（%s = %s）⇒ no-op，不覆盖" % (os.path.basename(a.out), cur))
        return 0
    if cur:
        # --refresh：只有「本脚本自己写过」的臂才允许升级；人工/外来裁决一律尊重
        if receipt_conclusion() != cur:
            log("目标文件非本脚本所写（%s）⇒ refresh 也不覆盖" % cur)
            return 0
        log("refresh：目标文件为本脚本所写（%s）⇒ 允许出现更深已判正层时升级" % cur)

    baseline, candidates = read_ab(a.ab)
    src = ".ab_mode.bundles[0]"
    if not baseline:
        try:
            baseline = io.open(a.keeper, encoding="utf-8-sig").read().strip()
            src = "_keeper_strategy.txt"
        except Exception:
            baseline = ""
    if not baseline:
        msg = "既无 .ab_mode 也无可用 _keeper_strategy.txt ⇒ 推不出基线"
        log("!! " + msg)
        _write_unresolved(msg, a)
        return 2
    if not candidates:
        # A/B 已停：把台账里出现过的臂全部提名（合格与否仍由判词把关）
        candidates = [x for x in ledger_arms(a.ledger) if x != baseline]
        src += " + 台账提名"

    verdicts = load_verdicts(a.verdicts)
    arm, elig, chosen = decide(baseline, candidates, verdicts)
    log("基线=%s（来源 %s）｜提名 %s｜判词文件 %d 份" % (baseline, src, candidates, len(verdicts)))
    for c, v in elig:
        log("  合格层：%s（依据 %s，%s）" % (c, v["name"], (v["last"] or "")[:60]))

    ok, why = arm_ok(arm)
    lines = [
        "===== 最终臂确认 %s =====" % time.strftime("%Y-%m-%d %H:%M:%S"),
        "基线：%s（来源 %s）" % (baseline, src),
        "提名：%s" % ", ".join(candidates),
        "合格（已判正）层：%s" % (", ".join("%s<-%s" % (c, v["name"]) for c, v in elig) or "（无）"),
        "结论：%s" % arm,
        "理由：%s" % ("取判词最新的已判正层（%s）" % chosen["name"] if chosen else "无已判正的新层 ⇒ 保持基线"),
        "实例化校验：%s（%s）" % ("通过" if ok else "失败", why),
    ]
    text = "\n".join(lines) + "\n"

    if not ok:
        log("!! 结论臂 %s 未通过实例化校验（%s）⇒ 拒绝写" % (arm, why))
        _write_unresolved("结论臂 %s 不可实例化：%s" % (arm, why), a)
        print(text)
        return 2

    try:
        with io.open(OUT_TXT, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    except Exception:
        pass

    if a.refresh:
        if cur == arm:
            log("refresh：结论未变（%s）⇒ no-op" % arm)
            return 0
        if arm == baseline:
            # 重算只回到基线 ⇒ 绝不把已经换上的更深层降级掉（refresh 只做"升级"）
            log("refresh：重算只得到基线（%s）⇒ 不降级，保持 %s" % (baseline, cur))
            return 0

    if not a.go or a.dry_run:
        print(text)
        log("(dry-run) 将写入 %s = %s" % (os.path.basename(a.out), arm))
        return 0

    with io.open(a.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(arm + "\n")
    try:
        if os.path.exists(UNRESOLVED):
            os.remove(UNRESOLVED)
    except Exception:
        pass
    log("★ 已写入 %s = %s" % (os.path.basename(a.out), arm))
    print(text)
    return 0


def _write_unresolved(reason, a):
    try:
        with io.open(UNRESOLVED, "w", encoding="utf-8", newline="\n") as f:
            f.write("%s | %s | out=%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), reason,
                                            os.path.basename(getattr(a, "out", FINAL_ARM))))
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())