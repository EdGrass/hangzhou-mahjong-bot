# -*- coding: utf-8 -*-
"""`var/_adopt_pair.py` —— **双候选役**的采用裁决 + 自动起下一役（BC/V 专用）。

## 为什么

`var/_bsegment.py` 起役时只注册**判词看护**（役 3 = `HangzhouMajVerdictWatch3bc/3v`），
**不注册采用看护**；而现成的 `HangzhouMajAdoptWatch` 只盯 `--label 役2`。
⇒ 役 3 判词落地后**没有任何东西会起役 4**，整条链会**静默停摆**（本机核对过：这是真缺口）。
役 3 判词约 2.5 天后落地，停摆一天就吃掉 10/7 前的余量。

## 判什么（全部来自已生效的预登记，本脚本不新增口径）

1. **候选各自的判词**（`_verdict_<label><suffix>.txt`）：最后一条 `★ 判定：` 以 **ADOPT** 开头才算 Δ；
2. **强手房否决**（役 3 预登记 §7/§8）：对每个 Δ 跑 `var/_strong_veto.py`（两层：≥1 / ≥2 名 top32，
   阈值 z ≤ −2.0 = §7 的「< −2×SE合并」）：
   - **VETO ⇒ 该候选按"不采用"处理**（§7.2 / §8：不作为正式赛选臂、继续测下一轴）；
   - **OK / UNKNOWN ⇒ 采用**（§7.3 / §8：样本不足"只记录，不据此翻转"）；
   - 其它 rc（工具异常）⇒ **无法判定 ⇒ 原地不动**（fail-closed，绝不猜）；
3. **四格 → 役 4 形态**（役 3 读卡 §3，逐字照抄）：BC✓ ⇒ 走 A 行；BC✗ 且 V✓ ⇒ 走 B 行；都不是 ⇒ NONE 行。
4. **机制端点否决**（★ R1480 新接）：预登记 §2 把「决策改动率 / 索取率」定为**本役核心机制端点**，
   并在 §4 写死 **B3：机制不达标 ⇒ 本役作废**。`var/_mech_watch.py`（每 6h）按该端点定期重抽，
   不在带内就写 `var/.mech_warn`（**内容带臂名**）。但此前**没有任何脚本读它** ⇒ B3 形同不存在：
   机制坏了（例如模型没加载、臂退化成 no-op）时统计端点只会变成噪声，到盒仍会按破平被“采用”。
   现在：告警指向该臂 ⇒ **按 B3 不采用**；告警读不出 ⇒ **原地不动**（fail-closed）；告警早于本役起点 ⇒ 当陈旧，不计。

## 红线

- 两个候选的哨兵没齐 ⇒ **不动**；marker 已存在 ⇒ **幂等 no-op**；
- 任何读数缺失/异常 ⇒ **不动**（只记日志 + 落 marker 供人工看）；
- 真正干活只走现成 `var/_bsegment.py --go`（它自己：停驱动 → 等空档 → P0 → preflight → 切役 → 注册看护，
  任一步失败自己 return 2，**绝不强停对局**）；本脚本**不杀任何进程**。

用法：
    python -X utf8 var/_adopt_pair.py --dry-run      # 只打印裁决
    python -X utf8 var/_adopt_pair.py --go           # 真执行
"""
from __future__ import annotations
import argparse
import io
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "var", "_adopt_pair.log")
AB = os.path.join(ROOT, "var", ".ab_mode")
LAST = "★ 判定："  # ★ 判定：
MECH_WARN = os.path.join(ROOT, "var", ".mech_warn")
VREC = os.path.join(ROOT, "var", "_v_mech_readings.jsonl")
B2_OUT = os.path.join(ROOT, "var", ".B2_CANDIDATES")
CONFLICT_OUT = os.path.join(ROOT, "var", ".VERDICT_RULE_CONFLICT")
Z_MAIN_MIN = 1.50      # 主端点（所有役）
Z_SEC_GENERIC = 1.50   # `_gate2` 对副端点的**通用**阈值


def log(msg):
    line = "%s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    print(line)


def last_verdict(text):
    hit = None
    for ln in (text or "").splitlines():
        if LAST in ln:
            hit = ln.split(LAST, 1)[1].strip()
    return hit or ""


def v_mech_last(arm, path=None):
    """最新一条该臂的 **V 机制读数** ⇒ (ok, why)。没记录 ⇒ (None, "无记录")。

    为什么：V 的机制是「爆头/胡 与 番/胡 都升」（campaign7 §2），它由
    `_mech_watch` 每 6h 写入 `var/_v_mech_readings.jsonl`。判 B2（机制成立、主端点未证实）
    必须读这个读数，而不能拿“没有 `.mech_warn`”当成“机制成立”。
    """
    pp = path or VREC
    last = None
    try:
        with io.open(pp, encoding="utf-8", errors="replace") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    d = json.loads(ln)
                except Exception:
                    continue
                if str(d.get("arm") or "") == arm:
                    last = d
    except Exception:
        return None, "读数文件读不到"
    if not last:
        return None, "无记录"
    return last.get("ok"), (last.get("why") or "")


def parse_gate2_zs(line):
    """从 `_gate2` 的 `★ 判定：` 行里取 **( 主 z, 副 z )**；取不到返回 (None, None)。

    行样（实测）：
      `ADOPT speedvalue（和牌率 z=+1.83、番 z=+1.77、护栏通过）`
      `UNDECIDED（和牌率 z=+1.24、番 z=+1.41）⇒ 继续攒房`
    """
    zm = re.search(r"和牌率\s*z=([+-]?[\d.]+)", line or "")
    zs = re.search(r"番\s*z=([+-]?[\d.]+)", line or "")
    return (float(zm.group(1)) if zm else None,
            float(zs.group(1)) if zs else None)


def v_rule_conflict(adopted, arm, z_main, z_sec):
    """★ R1487：**V 轴副端点的口径冲突**。

    campaign7 §2 对 V 的副端点写的是“副（**本役特有：必须为副**）、阈值 = **候选 > 基线**”
    —— **只看方向**；而 `_gate2` 对副端点用的是**通用** z ≥ 1.50。
    ⇒ 一旦落在“主 z ≥ 1.50、副方向为正但 **0 < 副 z < 1.50**”这一格，
    自动判词会说 UNDECIDED（到盒则 BOXED），而**预登记的 B1 其实已经满足** ⇒
    不能让机器惄惄把它当“不采用”。本函数只负责**识别冲突**，不自己改判——
    调用方应“**原地不动 + 落标记等人判**”。
    """
    if adopted:
        return False
    if "baotou" not in (arm or "").lower():
        return False
    if z_main is None or z_sec is None:
        return False
    return (z_main >= Z_MAIN_MIN) and (0.0 < z_sec < Z_SEC_GENERIC)


def is_b2(adopted, mstate, v_ok):
    """预登记的 **B2**：机制成立、主端点未证实 ⇒ **保留为正式赛备选臂**（不进自动候选池）。

    三个条件全中才算：① 判词已终态且**非 ADOPT**（adopted is False）；
    ② 足迹端点没报警（mstate == "ok"）；③ 若为 V 轴，它的真实机制读数必须是明确的 True。
    “读不出”/None 不算——**不猜**。
    """
    if adopted is not False:
        return False
    if mstate != "ok":
        return False
    return v_ok is True


def mech_state(arm, since, path=None):
    """★ R1480：预登记 B3（机制不达标 ⇒ 本役作废）在**采用路径上**的读数。

    返回 (state, why)，state ∈ {"ok", "fail", "unknown"}：
      · 无 `var/.mech_warn`                     ⇒ ok（机制正常）
      · 告警 mtime 早于本役起点 `since`   ⇒ ok（陈旧告警，不误伤）
      · 告警内容里出现本臂名               ⇒ fail（该臂机制不达标 ⇒ B3 不采用）
      · 告警读不出 / mtime 异常           ⇒ unknown（调用方必须原地不动）

    为什么只管**指向本臂**的告警：`_mech_watch` 一次可能检多个候选臂，告警行是
    `时间 + "臂名 足迹 …脱离预期"`（多条用 ； 拼）⇒ 按臂名匹配即可精确归因。
    """
    pp = path or MECH_WARN
    if not os.path.exists(pp):
        return "ok", "无机制告警"
    try:
        txt = io.open(pp, encoding="utf-8-sig", errors="replace").read().strip()
        mt = os.path.getmtime(pp)
    except Exception as e:
        return "unknown", "告警文件读不出（%s）" % str(e)[:40]
    if since:
        try:
            t0 = time.mktime(time.strptime(since, "%Y-%m-%d %H:%M:%S"))
            if mt + 1.0 < t0:
                return "ok", "告警早于本役起点（陈旧）"
        except Exception:
            pass
    if arm and arm in txt:
        return "fail", "机制端点告警：%s" % txt[:80]
    return "ok", "告警未指向本臂"


def is_adopt(line):
    return bool(re.match(r"ADOPT\s+[0-9A-Za-z_]+", (line or "").strip()))


def classify_candidate(verdict_line, veto_rc):
    """→ (adopted, reason)。adopted=None 表示**无法判定**（调用方必须原地不动）。

    veto_rc: 0=OK 2=UNKNOWN（都算采用）3=VETO（不采用）；其它 = 异常 ⇒ None。
    """
    if not is_adopt(verdict_line):
        return False, "判词非 ADOPT（%s）" % ((verdict_line or "（无）")[:28])
    if veto_rc == 3:
        return False, "强手房/决赛相似层显著劣 ⇒ 预登记不采用"
    if veto_rc in (0, 2):
        return True, "ADOPT 且未触发强手房否决（veto rc=%d）" % veto_rc
    return None, "强手房否决工具异常（rc=%s）⇒ 无法判定" % veto_rc


def pick_row(a_adopted, b_adopted):
    """四格 → 'a' / 'b' / 'none'（役 3 读卡 §3 逐字）。"""
    if a_adopted:
        return "a"
    if b_adopted:
        return "b"
    return "none"


def _read(path):
    try:
        with io.open(path, encoding="utf-8-sig", errors="replace") as f:
            return f.read()
    except Exception:
        return ""


def since_of():
    try:
        with io.open(AB, encoding="utf-8-sig") as f:
            return str(json.loads(f.read()).get("started") or "")
    except Exception:
        return ""


def run_veto(since, baseline, arm):
    cmd = [sys.executable, "-X", "utf8", os.path.join(ROOT, "var", "_strong_veto.py"),
           "--since", since, "--baseline", baseline, "--candidate", arm]
    try:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=900)
    except Exception as e:
        return None, "无法运行强手房否决：%s" % str(e)[:60]
    tail = [x for x in (p.stdout or "").strip().splitlines() if x.strip()][-3:]
    return p.returncode, " ｜ ".join(tail)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="役3")
    ap.add_argument("--baseline", default="speedvalue", help="本役基线（喂给强手房否决做对照）")
    ap.add_argument("--suffix-a", default="bc")
    ap.add_argument("--arm-a", default="speedvaluebc")
    ap.add_argument("--suffix-b", default="v")
    ap.add_argument("--arm-b", default="speedvaluebaotouv5")
    ap.add_argument("--since", default="")
    ap.add_argument("--next", default="役4")
    ap.add_argument("--row-a-base", default="speedvaluebc")
    ap.add_argument("--row-a-cands", default="speedvaluebcmeldp45")
    ap.add_argument("--row-b-base", default="speedvaluebaotouv5")
    ap.add_argument("--row-b-cands", default="speedvaluebaotouvmeld")
    ap.add_argument("--row-none-base", default="speedvalue")
    ap.add_argument("--row-none-cands", default="speedvaluemeldp45")
    ap.add_argument("--watch-mechanism", default="melds")
    ap.add_argument("--bsegment", default="var/_bsegment.py")
    ap.add_argument("--marker", default="")
    ap.add_argument("--timeout-min", type=int, default=60)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--go", action="store_true")
    a = ap.parse_args(argv)

    marker = a.marker or os.path.join(ROOT, "var", ".adopted_pair_%s" % a.label)
    if os.path.exists(marker):
        log("已裁决过（%s 存在）⇒ no-op" % os.path.basename(marker))
        return 0

    since = a.since or since_of()
    rows, undecided = [], False
    b2 = []            # ★ R1486：机制成立、主端点未证实 ⇒ 预登记的 B2（保留为备选臂）
    for suf, arm in ((a.suffix_a, a.arm_a), (a.suffix_b, a.arm_b)):
        sent = os.path.join(ROOT, "var", ".verdict_done_%s%s" % (a.label, suf))
        if not os.path.exists(sent):
            log("%s：判词未决定性（缺 %s）⇒ 不动" % (arm, os.path.basename(sent)))
            return 0
        line = last_verdict(_read(os.path.join(ROOT, "var", "_verdict_%s%s.txt" % (a.label, suf))))
        rc, info = (None, "（非 ADOPT，未跑否决）")
        if is_adopt(line):
            if not since:
                rc, info = None, "拿不到本役起点（.ab_mode.started）"
            else:
                rc, info = run_veto(since, a.baseline, arm)
        adopted, why = classify_candidate(line, rc)
        mstate, mwhy = mech_state(arm, since)
        if mstate == "unknown":
            log("%s：机制告警读数异常（%s）⇒ 原地不动（fail-closed）" % (arm, mwhy))
            return 2
        if mstate == "fail" and adopted is True:
            adopted, why = False, "机制端点不达标 ⇒ 预登记 B3 本役作废（%s）" % mwhy
        _zm, _zs = parse_gate2_zs(line)
        if v_rule_conflict(adopted is True, arm, _zm, _zs):
            _msg = (u"\u5f79 3 \u526f\u7aef\u70b9\u53e3\u5f84\u51b2\u7a81\uff1a%s \u4e3b z=%s \u2265 1.50\u3001\u526f z=%s \u5728 (0,1.50) \u21d2 "
                    u"_gate2 \u901a\u7528\u53e3\u5f84\u5224\u201c\u672a\u51b3\u201d\uff0c"
                    u"\u4f46 campaign7 \u00a72 \u5bf9 V \u7684\u526f\u7aef\u70b9\u53ea\u8981\u2018\u5019\u9009 > \u57fa\u7ebf\u2019 \u21d2 **\u9884\u767b\u8bb0 B1 \u5df2\u6ee1\u8db3**") % (arm, _zm, _zs)
            try:
                with io.open(CONFLICT_OUT, "w", encoding="utf-8", newline="") as f:
                    f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), _msg))
                    f.write("  \u5224\u8bcd\u884c\uff1a%s\n" % (line or "(\u7a7a)"))
                    f.write("  \u8bf7\u4eba\u6309 campaign7 \u00a72/\u00a74 \u4e0e yaku3-verdict-readcard.md \u5b9a\u6027\uff08\u4e0d\u81ea\u52a8\u91c7\u7528\uff09\u3002\n")
            except Exception as _e:
                log("!! \u5199\u53e3\u5f84\u51b2\u7a81\u6807\u8bb0\u5931\u8d25\uff1a%s" % str(_e)[:40])
            log("!! " + _msg + " \u21d2 \u539f\u5730\u4e0d\u52a8\uff08\u5df2\u843d %s\uff09" % os.path.basename(CONFLICT_OUT))
            return 2
        if os.path.exists(CONFLICT_OUT):
            try:
                os.remove(CONFLICT_OUT)
            except Exception:
                pass

        log("%s：判词=「%s」｜%s｜机制=%s（%s）｜%s"
            % (arm, line[:40], why, mstate, mwhy, info))
        if adopted is None:
            undecided = True
        rows.append((arm, adopted))
        # ★ R1486：预登记的 B2 分支（例：campaign7 §4）要求把“机制成立、主端点未证实”的臂
        #   **记录下来并保留为正式赛备选臂**（与 §V.66 选臂口径并行比较）。
        #   之前这个分支**没有任何落盘** ⇒ 10/5 选臂时根本看不到它。
        #   只对“已终态判负（adopted is False）”记；判不出（None）不猜。
        if adopted is False:
            _v_ok, _v_why = (True, "")
            if "baotou" in arm.lower():
                _v_ok, _v_why = v_mech_last(arm)
            if is_b2(adopted, mstate, _v_ok):
                b2.append((arm, "机制成立、主端点未证实（判词：%s）" % (line[:48] or "（空）")))
    if b2:
        try:
            with io.open(B2_OUT, "w", encoding="utf-8", newline="") as f:
                f.write("%s 役三层 B2 备选臂（预登记：机制成立、主端点未证实）\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
                for _a, _w in b2:
                    f.write("  %s —— %s\n" % (_a, _w))
                f.write("注：他们**没有**通过预登记判词 ⇒ 按 §V.161 规则 1 **不进自动候选池**；\n"
                        "但预登记要求把它们保留为正式赛备选，与 §V.66/§V.29 口径**并行比较**（由人判）。\n")
            log("★ B2 备选臂已落盘 %s：%s" % (os.path.basename(B2_OUT), "、".join(a for a, _ in b2)))
        except Exception as _e:
            log("!! 写 B2 备选臂失败：%s" % str(_e)[:60])
    elif os.path.exists(B2_OUT):
        try:
            os.remove(B2_OUT)
        except Exception:
            pass

    if undecided:
        log("!! 有候选无法判定 ⇒ 原地不动（需人工看上面几行）")
        return 2

    row = pick_row(rows[0][1], rows[1][1])
    base, cands = {
        "a": (a.row_a_base, a.row_a_cands),
        "b": (a.row_b_base, a.row_b_cands),
        "none": (a.row_none_base, a.row_none_cands),
    }[row]
    log("四格裁决：BC=%s / V=%s ⇒ 走 %s 行 ⇒ 役 4 = %s + %s"
        % (rows[0][1], rows[1][1], row.upper(), base, cands))

    cmd = [sys.executable, "-X", "utf8", os.path.join(ROOT, a.bsegment), "--go",
           "--label", a.next, "--baseline", base, "--candidates", cands,
           "--watch-mechanism", a.watch_mechanism]
    if a.dry_run or not a.go:
        log("(dry-run) 将起下一役：%s" % " ".join(cmd))
        print("（未加 --go：只打印，不执行）")
        return 0
    log("起下一役：%s" % " ".join(cmd))
    try:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=a.timeout_min * 60)
    except subprocess.TimeoutExpired:
        log("!! B 段超时（%d 分钟）⇒ 人工检查（不对任何进程下手）" % a.timeout_min)
        return 2
    tail = "\n".join((p.stdout or "").strip().splitlines()[-6:])
    log("B 段 rc=%s：\n%s" % (p.returncode, tail))
    if p.returncode != 0:
        return p.returncode
    try:
        with io.open(marker, "w", encoding="utf-8") as f:
            f.write("%s row=%s base=%s cands=%s\n"
                    % (time.strftime("%Y-%m-%d %H:%M:%S"), row, base, cands))
    except Exception as e:
        log("⚠ 写 marker 失败：%s" % str(e)[:60])
    log("★ 已起 %s（基线 %s，候选 %s）" % (a.next, base, cands))
    return 0


if __name__ == "__main__":
    sys.exit(main())
