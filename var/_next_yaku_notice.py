# -*- coding: utf-8 -*-
"""`var/_next_yaku_notice.py` —— **役 4 判词落地后的“下一步”提醒**（只读 + 产出可照拄命令，**不自己执行**）。

## 为什么

链上现在只有两个自动推进器：`AdoptWatch`（役 2）与 `AdoptPairWatch`（役 3→役 4）。
**役 4 的判词落地后没有任何计划任务去消费它** ⇒ 如果没人在场，`_ab_driver`
会**继续跑役 4 超过役盒**（白烧房位），且役 5 （**三层组合臂**）**永远不会起**。
而 §V.186 把“役 4→役 5”定性为**判断题**（不自动开），因为候选臂的剂量口径有一个**未定的选择**（`speedvaluebcvmeld`
还是**剂量对齐 p40**）—— 写死一个就是猜。所以本脚本**不做决定**，它只把“该决定了 + 每个分支的可照拄命令”摆出来。

## 判据（逐字对 §V.186）

- 役 4（副露）**未判正** ⇒ **不起役 5**，直接进 §V.66 选臂（★ R1560：此时第三个役位会**空置** 1.7–3.2 天 ⇒ 按 **§V.281** 另列一条
  **供人定**的选项：用同一槽位起 `speedvaluerank`；本脚本**只列出、不执行**）；
- 役 4 判正 **且 BC 与 V 都判正** ⇒ 起役 5：基线 = 役 4 的 2 层赢家，候选 = `speedvaluebcvmeld`
  （**或** 剂量对齐 `speedvaluebcvmeldp40`）；
- 役 4 判正但**只有单层** ⇒ 无 3 层组合可用 ⇒ 不起役 5，直接选臂；
- 额外提醒（§V.161 规则 4 的组合臂）：若役 4 判负但 **BC 与 V 都判正**，则 `speedvaluebcv`（不带副露）
  是一个**合法的组合臂选项**（已注册）——只列出供人判，不当默认。

## 红线

只读：不杀进程、不改 `bot/`、不改 `.ab_mode`、**不自己起役**。全部输入缺一不可 ⇒ 静默等待。

用法：
    python -X utf8 var/_next_yaku_notice.py --label 役4            # 真写提醒文件
    python -X utf8 var/_next_yaku_notice.py --label 役4 --dry-run  # 只打印
"""
from __future__ import annotations
import argparse
import io
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAIR_MARKER = os.path.join(ROOT, "var", ".adopted_pair_役3")
OUT = os.path.join(ROOT, "var", ".YAKU_NEXT_PENDING")
LOG = os.path.join(ROOT, "var", "_next_yaku_notice.log")
LAST = "★ 判定："   # ★ 判定：


def _read(path):
    try:
        return io.open(path, encoding="utf-8-sig", errors="replace").read()
    except Exception:
        return ""


def last_verdict_line(text):
    """判词里最后一条 `★ 判定：` 行（没有就返回 ""）。"""
    hit = ""
    for ln in (text or "").splitlines():
        if LAST in ln:
            hit = ln.split(LAST, 1)[1].strip()
    return hit


def is_adopt(line):
    return bool(line) and line.upper().startswith("ADOPT")


def verdict_label(yaku, cand):
    """与 `_register_campaign_watches.ps1` 的命名规则一致：非字母数字 → `_`。"""
    return str(yaku) + re.sub(r"[^A-Za-z0-9_]", "_", str(cand))


def parse_pair_marker(text):
    """`.adopted_pair_役3` 内容 ⇒ (row, base, cands)。"""
    row = base = cands = ""
    m = re.search(r"row=(\S+)", text or "")
    if m:
        row = m.group(1)
    m = re.search(r"base=(\S+)", text or "")
    if m:
        base = m.group(1)
    m = re.search(r"cands=(\S+)", text or "")
    if m:
        cands = m.group(1)
    return row, base, cands


def decide(meld_ok, bc_ok, v_ok, base4, cand4):
    """纯函数（便于单测）。返回 (kind, why, cmds)。

    kind ∈ {"start", "combo_option", "no_yaku5", "wait"}
    """
    if not meld_ok:
        if bc_ok and v_ok:
            return ("combo_option",
                    "役 4（副露）未判正 ⇒ §V.186 不起役 5；但 BC 与 V 都判正 "
                    "⇒ §V.161 规则 4 的组合臂选项（不带副露）",
                    [("speedvalue", "speedvaluebcv")])
        return ("no_yaku5",
                "役 4（副露）未判正 ⇒ 按 §V.186 不起役 5，直接进 §V.66 选臂",
                [])
    if bc_ok and v_ok:
        return ("start",
                "役 4 判正 且 BC 与 V 都判正 ⇒ 按 §V.186 起役 5（三层组合）；"
                "基线 = 役 4 的 2 层赢家（%s）" % (cand4 or base4),
                [(cand4 or base4, "speedvaluebcvmeld"),
                 (cand4 or base4, "speedvaluebcvmeldp40")])
    return ("no_yaku5",
            "役 4 判正但 BC/V 只有单层 ⇒ 无 3 层组合可用 ⇒ 不起役 5",
            [])


def _say(logpath, msg):
    print(msg)
    try:
        with io.open(logpath, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="役4")
    ap.add_argument("--marker", default="")
    ap.add_argument("--var-dir", default=os.path.join(ROOT, "var"),
                    help="变量目录（单测用；默认仓库的 var/）")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    vd = a.var_dir
    pair_marker = os.path.join(vd, ".adopted_pair_役3")
    out = os.path.join(vd, ".YAKU_NEXT_PENDING")
    log = os.path.join(vd, "_next_yaku_notice.log")
    marker = a.marker or os.path.join(vd, ".next_yaku_notice_%s" % a.label)
    if os.path.exists(marker):
        return 0                                   # 已提醒过 ⇒ 幂等 no-op

    ptxt = _read(pair_marker)
    if not ptxt:
        return 0                                   # 役 4 还没起 ⇒ 不该提醒
    row, base4, cands4 = parse_pair_marker(ptxt)
    cand4 = (cands4.split(",") or [""])[0].strip()
    if not cand4:
        return 0

    vl = verdict_label(a.label, cand4)
    sent = os.path.join(vd, ".verdict_done_%s" % vl)
    if not os.path.exists(sent):
        return 0                                   # 役 4 判词还未决定性

    line4 = last_verdict_line(_read(os.path.join(vd, "_verdict_%s.txt" % vl)))
    meld_ok = is_adopt(line4)
    bc_ok = is_adopt(last_verdict_line(_read(os.path.join(vd, "_verdict_役3bc.txt"))))
    v_ok = is_adopt(last_verdict_line(_read(os.path.join(vd, "_verdict_役3v.txt"))))

    kind, why, cmds = decide(meld_ok, bc_ok, v_ok, base4, cand4)
    # ★ R1556：BOXED（到盛未决定性）**不是判负** —— 机器按“未判正”处理，
    #   而预登记下“主过 + 副同号”仍算通过（yaku4 读卡 §0 已写明三种形状的阈值差异）。
    _boxed4 = bool(line4) and line4.upper().startswith("BOXED")

    lines = [
        "== 役 4 判词已落地 —— “下一步”需要一个判断 ==",
        "口径（役 4 三种形状的副端点阈值不同）看 docs/iter/reports/yaku4-verdict-readcard.md §0；"
        "役 5 定臂口径看 yaku5-verdict-readcard.md。本提醒只给命令，不替你判。",
        "时间：%s" % time.strftime("%Y-%m-%d %H:%M:%S"),
        "役 4 判词（%s）：%s" % (vl, (line4 or "（空）")[:90]),
        "役 3 四格：row=%s  BC=%s  V=%s  （役 4 配置：base=%s cands=%s）"
        % (row or "?", bc_ok, v_ok, base4, cands4),
        "",
        "判据：%s" % why,
        # ★ R1554：把**判词读数命令**一并给出 —— 这一刻最容易只看一半证据。
        #   读卡 §0 说了副端点三种形状阈值不同、机制端点在 `_mech_watch` 里；`_verdict_digest` 把它们一次性跑完。
        "判词读数（主/副/护栏/机制 + 强手房两层 + 两半 Pareto）：",
        "  python -X utf8 var/_verdict_digest.py --since \"<役4 起点（见 var/.ab_mode.started）>\" "
        "--baseline %s --candidates %s --mechanism melds" % (base4, cands4),
        "",
    ]
    if _boxed4:
        lines += ["",
                  "★ 注意：役 4 判词是**到盛未决定性（BOXED）**，**不是判负** —— 按 yaku4-verdict-readcard.md §0 的三形状阈值**人工定性**"
                  "（A/B 行副端点只需‘同号’）；机器按“未判正”处理（**不进自动池**），"
                  "人若定性为通过 ⇒ 可按 §V.247 在 **10/5 提案**里改选。"]
    if kind == "start":
        lines.append("== 可照拄命令（二选一：§V.186 对剂量口径留了“或”）==")
        for b, c in cmds:
            # ★ R1531：役5 的基线已含副露层 ⇒ `--watch-mechanism` **必须是 none**（与 campaign8 §5 逐字一致）。
            #   写 melds 会让 `_gate2` 的**硬机制闸**拿“已存在的层”要求上升 ⇒ 可能把最终组合臂误判 REFUSE（R1515 同类）。
            lines.append('  python -X utf8 var/_bsegment.py --go --label 役5 --baseline %s --candidates %s --watch-mechanism none' % (b, c))
        lines.append("  （一个是无剂量的 3 层组合，一个是剂量对齐 p40；两者都已注册）")
    elif kind == "combo_option":
        lines.append("== 可选合法组合臂（不起役 5；供人判）==")
        for b, c in cmds:
            lines.append('  python -X utf8 var/_bsegment.py --go --label 役6 --baseline %s --candidates %s --watch-mechanism none' % (b, c))
        lines.append("  注：§V.186 说“不起役 5”，§V.161 规则 4 又说看不出差别时选组合臂 —— 两条口径冲突，**由人定**。")
    else:
        lines.append("⇒ **默认：**不需要起新役；等 **10/5 09:00 的 `HangzhouMajFinalPickProposal`** 出选臂提案即可。")
        # ★ R1560（§V.281）：这一分支会把**第三个役位空置 1.7–3.2 天**，而 10/7 的最终臂只能等于基线。
        #   另一条路早已预登记好（§V.42 的第 4 号臂、足迹 37.0%、`_campaign_ready` 全 ✅、
        #   `prereg-campaign5-speedvaluerank-20260924.md` 格式合格）—— 本脚本**只把它摆出来**，不替人拍。
        lines += [
            "",
            u"★ 待决（§V.281，**由人拍**；本脚本不起役）：上面那条默认路会把第三个役位**空置 1.7–3.2 天**，",
            u"  10/7 的最终臂就只能等于基线。§V.42 已把「同侧第二次下注」排为第 4 号臂（足迹 37.0%、打最大缺口）：",
            "  python -X utf8 var/_bsegment.py --go --label 役5 --baseline %s --candidates speedvaluerank --watch-mechanism draw" % (base4 or "speedvalue"),
            u"  （第二顺位 = `speedvalueplain`；两个都已注册、都有合格预登记）",
            u"  起役前需先接好 §V.281 列的 4 条线（机制读数相位 / 读卡形状确认 / 命令出口）。",
        ]
    # ★ R1483：把**机制端点的两个标记**一并附上 —— 它们会直接改写四格结果（B3），
    #   所以“该不该开下一役、开哪个”的决策包必须包含它们；否则读到提醒的人会以为四格是干净的。
    for _n, _t in ((".mech_warn", "机制端点告警（指向的臂按预登记 B3⇒不采用）"),
                   (".v_mech_unknown", "V 轴机制读数缺失（B1/B2/B3 在 V 那一半无法判）")):
        _p = os.path.join(vd, _n)
        if os.path.exists(_p):
            try:
                _body = io.open(_p, encoding="utf-8-sig", errors="replace").read().strip()
            except Exception as _e:
                _body = "(读不出: %s)" % str(_e)[:40]
            lines += ["", "⚠ %s —— %s" % (_n, _t), "  " + _body.replace("\n", "\n  ")]

    lines += ["", "（本文件由 `HangzhouMajNextYakuNotice` 每 10 分钟检查一次；只提醒，不自己起役。）"]

    body = "\n".join(lines) + "\n"
    if a.dry_run:
        print(body)
        print("（dry-run：未写文件、未写 marker）")
        return 0
    try:
        with io.open(out, "w", encoding="utf-8", newline="") as f:
            f.write(body)
        with io.open(marker, "w", encoding="utf-8") as f:
            f.write("%s kind=%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), kind))
    except Exception as e:
        _say(log, "!! 写提醒失败：%s" % str(e)[:80])
        return 1
    _say(log, "役 4 判词已落地 ⇒ kind=%s ⇒ 已写 %s"
         % (kind, os.path.basename(out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
