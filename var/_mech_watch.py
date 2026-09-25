# -*- coding: utf-8 -*-
"""`var/_mech_watch.py` —— \u5f79\u4e2d**\u673a\u5236\u7aef\u70b9\u5b88\u62a4**\uff1a\u6bcf N \u5c0f\u65f6\u628a\u5f53\u524d\u5f79\u5019\u9009\u81c2\u7684\u79bb\u7ebf\u8db3\u8ff9\u91cd\u62bd\u4e00\u6b21\u3002

## \u4e3a\u4ec0\u4e48\uff08\u9884\u767b\u8bb0\u8981\u6c42\uff0c\u4e0d\u662f\u6211\u52a0\u7684\uff09

`prereg-campaign3-speedvaluebc-20260924.md` \u7b2c 2 \u8282\u628a\u300c**\u51b3\u7b56\u6539\u52a8\u7387 \u2208 [10%, 20%] \u4e14 action \u5dee\u5f02 = 0**\u300d\u5b9a\u4e3a\u672c\u5f79**\u6838\u5fc3\u673a\u5236\u7aef\u70b9**\uff0c
\u5e76\u8981\u6c42\u201c\u6bcf 20 \u623f\u590d\u8dd1\u4e00\u6b21 `tools/offline_replay`\uff08\u62bd\u6837\u5373\u53ef\uff09\u201d\u3002\u4eba\u5de5\u6570\u623f\u5bb9\u6613\u5fd8 \u21d2 \u672c\u811a\u672c\u628a\u5b83\u53d8\u6210\u65f6\u95f4\u9a71\u52a8\u7684\u5b9a\u671f\u91cd\u62bd\u4e0e\u81ea\u52a8\u5224\u8bfb\u3002

## \u884c\u4e3a

1. \u8bfb `var/.ab_mode`\uff1b**\u65e0\u5f79\u5728\u8dd1\u5c31\u76f4\u63a5\u9000\u51fa**\uff08\u7edd\u5bf9 no-op\uff09\uff1b
2. \u5bf9\u6bcf\u4e2a\u5019\u9009\u81c2\u9009\u76f8\u4f4d\u5e76\u8dd1\u79bb\u7ebf\u91cd\u62bd\uff08\u5168\u7a0b `--lowprio`\uff0c\u9075\u5b88 \u00a79.30/\u00a79.47 \u7eaa\u5f8b\uff09\uff1a
   * \u542b `meld` \u21d2 `--phase window`\uff08\u671f\u671b\u7d22\u53d6\u7387\u4e0a\u5347\uff09\uff1b
   * \u542b `bc` / `baotou` \u21d2 `--phase draw`\uff08\u671f\u671b tile \u6539\u52a8\u7387 \u2208 [10,20]%\u3001action \u5dee\u5f02 = 0\uff09\uff1b
   * 含 `baotou` **另外**跑一次 `_seat_h2h --by-arm`（R1481）：预登记 campaign7 §2 把 V 的机制定义为
     **爆头/胡 上升 且 番/胡 上升**（“本轴的全部理由就是赢得大”）。足迹只是必要条件，**直接量机制**才对得上 §2。
     不满足 ⇒ 归入 warns（⇒ `var/.mech_warn` ⇒ `_adopt_pair` 按 B3 不采用）；读数另行落 `var/_v_mech_readings.jsonl`。
   * \u5176\u4ed6 \u21d2 \u53ea\u8bb0\u5f55\uff08\u4e0d\u5224\uff09\u3002
3. \u7ed3\u679c\u8ffd\u52a0\u5230 `var/_mech_watch.log`\uff1b\u4e0d\u5728\u9884\u671f\u5e26\u5185 \u21d2 \u5199 `var/.mech_warn`\uff08\u5e26\u539f\u56e0\uff09\uff0c\u6b63\u5e38 \u21d2 \u5220\u5b83\u3002

\u7ea2\u7ebf\uff1a\u53ea\u8bfb\u8bed\u6599/\u53ea\u5199\u81ea\u5df1\u7684\u65e5\u5fd7\u4e0e\u6807\u8bb0\uff1b\u4e0d\u78b0\u5f79\u3001\u4e0d\u78b0 `bot/`\u3001\u4e0d\u6740\u8fdb\u7a0b\u3002

\u7528\u6cd5\uff1a
    python -X utf8 var/_mech_watch.py            # \u6309 .ab_mode \u81ea\u52a8\u5224\u5f53\u524d\u5f79
    python -X utf8 var/_mech_watch.py --files 200 --dry-run
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
AB = os.path.join(ROOT, "var", ".ab_mode")
LOG = os.path.join(ROOT, "var", "_mech_watch.log")
WARN = os.path.join(ROOT, "var", ".mech_warn")
SEAT_H2H = os.path.join(ROOT, "var", "_seat_h2h.py")
LOWPRIO = os.path.join(ROOT, "var", "_lowprio_run.py")
VREC = os.path.join(ROOT, "var", "_v_mech_readings.jsonl")
UNK = os.path.join(ROOT, "var", ".v_mech_unknown")


def log(msg):
    line = "%s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    try:
        with io.open(os.environ.get("HM_MECH_LOG", LOG), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    print(line)


def phases_for(arm):
    """臂名 → 需检相位列表（R1430）。

    单层臂返回一个；**组合臂（例 `speedvaluebcvmeld`）两个都检**：
    含 `meld` ⇒ window（索取率）；含 `bc`/`baotou` ⇒ draw（出牌改动率）。
    """
    a = arm.lower()
    ph = []
    if "meld" in a:
        ph.append("window")
    if "bc" in a or "baotou" in a:
        ph.append("draw")
    return ph


def arms_of(cfg):
    """★ R1481：**N 臂支持**（与 `_ab_driver.arms_of` 同口径）。

    旧实现只读 `cfg["a"]/cfg["b"]`（两臂时代的格式）。而役 3 是**三臂**，`.ab_mode` 是
    `{"arms": [...]}` ⇒ `arms=[None, None]` ⇒ `cands=[]` ⇒ **本脚本静默 no-op**（实测：`_mech_watch --dry-run`
    汇报“役内无候选臂（arms=[None, None]）”）。后果：**机制端点守护根本没在跑** ⇒
    `var/.mech_warn` 永远不写 ⇒ 上一轮接上的 B3 守卫（R1480）在实践里**永远不会触发**。
    """
    if isinstance(cfg.get("arms"), list) and len(cfg["arms"]) >= 2:
        return [str(x) for x in cfg["arms"]]
    return [x for x in (cfg.get("a"), cfg.get("b")) if x]


def has_v_layer(name):
    """★ R1515：V 层检测 —— V 有**两种形态**，**不能只看名字**：

      ① 继承 `SpeedValueBaotouV5`（名字含 `baotou`）；
      ② 重写 `value_of()` 加 `W_TILES × W_UKEIRE × baotou_value`（名字如 `speedvaluebcv` / **`speedvaluebcvmeld`**）。

    两者**共享剂量开关 `W_TILES`**（实测：V 臂=5.0；非 V 臂无该属性）⇒ 用它判定。
    为什么必须抽中 `speedvaluebcvmeld`：**役 5 的候选就是它** ——
    按名字找 V 会让**最终组合臂的 V 机制根本没人验**（而役 5 新增的层正好就是 V）。
    """
    if "baotou" in (name or "").lower():
        return True
    try:
        sys.path.insert(0, ROOT)
        from run_bot import STRATEGY_FACTORIES as F
        if name not in F:
            return False
        return float(getattr(F[name](), "W_TILES", 0) or 0) > 0.0
    except Exception:
        return False


def parse_h2h(text):
    """`_seat_h2h.py --by-arm` 的表 ⇒ {(arm, side): {"hu":..,"fan":..,"baotou":..}}。

    行样（实测）：
        speedvalue 我方               局    111 | 胡/轮 25.11% | 番/胡 1.29 | 分/轮   +0.03 | ... | 爆头/胡  24.4% ...
    只认“臂名 + 我方/另三家”后缀；对不上的行直接丢掉（宁可缺读数，不拼一个假的）。
    """
    out = {}
    for ln in (text or "").splitlines():
        if "|" not in ln or "爆头/胡" not in ln or "胡/轮" not in ln:
            continue
        head = ln.split("|", 1)[0].strip()
        m = re.match(r"^(.*?)\s*局\s+\d+\s*$", head)
        if not m:
            continue
        label = m.group(1).strip()
        if label.endswith("我方"):
            arm, side = label[:-2].strip(), "我方"
        elif label.endswith("另三家"):
            arm, side = label[:-3].strip(), "另三家"
        else:
            continue
        if not arm:
            continue

        def num(pat):
            mm = re.search(pat, ln)
            return float(mm.group(1)) if mm else None

        _mr = re.search(r"局\s+(\d+)", ln)
        out[(arm, side)] = {
            "rounds": int(_mr.group(1)) if _mr else None,
            "hu": num(r"胡/轮\s+([\d.]+)%"),
            "fan": num(r"番/胡\s+([\d.]+)"),
            "baotou": num(r"爆头/胡\s+([\d.]+)%"),
        }
    return out


V_MECH_MIN_ROUNDS = 320   # ★ R1481：约 40 房（实测 8 局/房）以下不判，免得把噪声当成 B3


def _hu_rate_se(pct, n):
    """胡率（%）的二项 SE（%）。★ R1517：供 V 的预登记护栏“胡率不得低于基线 1σ”用。"""
    try:
        n = int(n or 0)
        p = max(0.0, min(100.0, float(pct))) / 100.0
    except Exception:
        return None
    if n <= 0:
        return None
    return 100.0 * (p * (1.0 - p) / float(n)) ** 0.5


def judge_v_mech(base, cand, min_rounds=None):
    """campaign7 §2 的 V 机制判据：**爆头/胡 上升 且 番/胡 上升**。

    返回 (ok, why)；ok ∈ {True, False, None}（None = 读数缺失，调用方不得据此翻转）。
    为什么两项都要：该轴的全部理由就是“赢得大”——只升爆头不升番/胡，说明只是把命中换成了爆头标签，并没把牌打大。
    """
    if not base or not cand:
        return None, "读数缺失（base=%s cand=%s）" % (bool(base), bool(cand))
    if None in (base.get("baotou"), base.get("fan"), cand.get("baotou"), cand.get("fan")):
        return None, "读数缺夹"
    _mr = V_MECH_MIN_ROUNDS if min_rounds is None else int(min_rounds)
    if (base.get("rounds") or 0) < _mr or (cand.get("rounds") or 0) < _mr:
        return None, "样本不足（局 %s vs %s < %d）⇒ 不判" % (
            base.get("rounds"), cand.get("rounds"), _mr)
    up_b = cand["baotou"] > base["baotou"]
    up_f = cand["fan"] > base["fan"]
    why = "爆头/胡 %.1f%%→%.1f%%、番/胡 %.2f→%.2f" % (
        base["baotou"], cand["baotou"], base["fan"], cand["fan"])
    # ★ R1517：**预登记护栏必须有人执行** —— `yaku3-verdict-readcard.md` 写着
    #   V 臂“胡率不得低于基线 1σ”，而 R1517 全仓搜证发现**任何代码都没执行它**
    #   ⇒ 不补的话，V 可以“爆头/番都上升、但胡率明显塌”而被采用。这里按字面执行：
    #   Δhu ≥ −1×SE_合并（二项 SE 合并）。读数缺失 ⇒ 不判（None），不猜。
    se_b = _hu_rate_se(base.get("hu"), base.get("rounds"))
    se_c = _hu_rate_se(cand.get("hu"), cand.get("rounds"))
    if se_b is None or se_c is None:
        return None, why + "；**护栏读数缺失**（胡率/局数）⇒ 不判"
    d_hu = float(cand["hu"]) - float(base["hu"])
    se_d = (se_b ** 2 + se_c ** 2) ** 0.5
    guard_ok = d_hu >= -1.0 * se_d
    why += "；胡率 %+.1fpp（1σ=%.1fpp）%s" % (
        d_hu, se_d, "" if guard_ok else " ⇐ 护栏未过")
    return (bool(up_b and up_f and guard_ok)), why


def unk_action(v_cands, states):
    """`var/.v_mech_unknown` 的处置：`"write"` / `"clear"`。

    ★ R1484：旧实现只在“V 读数为 None”时**写**、只在“当前役没有 V 候选”时**删**
    ⇒ 早期因样本不足写下的标记，**读数齐了也不会消** ⇒ 看护会一直报“V 机制无法判”（陈旧标记误导）。
    现在：有任一 V 候选判不出 ⇒ write；全部判出了（含判不达标）或没有 V 候选 ⇒ clear。
    """
    if not v_cands:
        return "clear"
    if any(x is None for x in states):
        return "write"
    return "clear"


def append_v_record(rec, path=None):
    """V 机制读数落盘（JSONL）—— B1/B2 都需要它作为“机制是否成立”的可查记录。"""
    try:
        with io.open(path or VREC, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", type=int, default=200)
    ap.add_argument("--ab-file", default=AB, help="默认 var/.ab_mode；测试可指向临时文件")
    ap.add_argument("--log-file", default=LOG)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if not os.path.exists(a.ab_file):
        print("\u65e0 .ab_mode \u21d2 \u65e0\u5f79\u5728\u8dd1\uff0cno-op")
        return 0
    try:
        cfg = json.loads(io.open(a.ab_file, encoding="utf-8-sig").read())
    except Exception as e:
        log("!! \u8bfb .ab_mode \u5931\u8d25\uff1a%s" % str(e)[:60])
        return 1
    _arms0 = arms_of(cfg)
    baseline = (cfg.get("bundles") or _arms0 or [cfg.get("a")])[0]
    arms = _arms0
    cands = [x for x in arms if x and x != baseline]
    if not cands:
        log("\u5f79\u5185\u65e0\u5019\u9009\u81c2\uff08arms=%s, baseline=%s\uff09\u21d2 no-op" % (arms, baseline))
        return 0

    warns = []
    _states = []       # ★ R1484：V 候选的判定列表（供 unk_action 用；必须在循环外初始化）
    pairs = [(c, p) for c in cands for p in (phases_for(c) or [""])]
    for cand, ph in pairs:
        if not ph:
            log("  %s \u21d2 \u65e0\u9884\u8bbe\u671f\u671b\uff0c\u53ea\u8bb0\u5f55" % cand)
            continue
        cmd = [sys.executable, "-X", "utf8", os.path.join(ROOT, "tools", "offline_replay.py"),
               "--base", baseline, "--cand", cand, "--phase", ph,
               "--files", str(a.files), "--lowprio"]
        if a.dry_run:
            log("  [dry-run] %s" % " ".join(cmd[1:]))
            continue
        t0 = time.time()
        try:
            p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=1800)
        except subprocess.TimeoutExpired:
            log("!! %s \u91cd\u62bd\u8d85\u65f6" % cand)
            warns.append("%s \u91cd\u62bd\u8d85\u65f6" % cand)
            continue
        out = p.stdout or ""
        if ph == "draw":
            m = re.search(r"tile \u4e0d\u540c \d+ \(([\d.]+)%\)\s+action \u4e0d\u540c \d+ \(([\d.]+)%\)", out)
            if not m:
                log("!! %s draw \u8f93\u51fa\u672a\u8bc6\u522b\uff08rc=%s\uff09" % (cand, p.returncode))
                continue
            tile_pct, act_pct = float(m.group(1)), float(m.group(2))
            # ★ R1430：只在“出牌层是**新加**的”时才拉 10–20% 带；若基线已含 bc
            #   （如役 5：`speedvaluebc` → `speedvaluebcvmeld`），这是**边际**足迹，只记录不判。
            _layer_new = ("bc" in cand.lower() or "baotou" in cand.lower()) and not (
                "bc" in baseline.lower() or "baotou" in baseline.lower())
            ok = (10.0 <= tile_pct <= 20.0 and act_pct == 0.0) if _layer_new else (act_pct == 0.0)
            _exp = "\u9884\u671f 10\u201320% / action=0" if _layer_new else "\u8fb9\u9645\u8db3\u8ff9\uff08\u57fa\u7ebf\u5df2\u542b\u540c\u5c42\uff09\uff1a\u53ea\u8981 action=0"
            log("  %s draw\uff1atile \u6539\u52a8 %.1f%%\u3001action %.1f%% \u21d2 %s\uff08%s\uff09\uff08%.0fs\uff09"
                % (cand, tile_pct, act_pct, "PASS" if ok else "WARN", _exp, time.time() - t0))
            if not ok:
                warns.append("%s draw \u8db3\u8ff9 %.1f%%/action %.1f%% \u8131\u79bb\u9884\u671f" % (cand, tile_pct, act_pct))
        else:
            m = re.search(r"\u7d22\u53d6\u7387\(\u6536\u526f\u9732/\u53ef\u7d22\u53d6\):\s+\u57fa\u7ebf ([\d.]+)%\s+\u5019\u9009 ([\d.]+)%", out)
            m2 = re.search(r"\u4ec5\u57fa\u7ebf\u6536 (\d+)", out)
            if not m:
                log("!! %s window \u8f93\u51fa\u672a\u8bc6\u522b\uff08rc=%s\uff09" % (cand, p.returncode))
                continue
            b, c = float(m.group(1)), float(m.group(2))
            base_only = int(m2.group(1)) if m2 else -1
            _layer_new_w = "meld" in cand.lower() and "meld" not in baseline.lower()
            ok = ((c >= b + 3.0) and base_only == 0) if _layer_new_w else (base_only == 0)
            log("  %s window\uff1a\u7d22\u53d6\u7387 %.1f%% \u2192 %.1f%%\uff08\u4ec5\u57fa\u7ebf\u6536 %d\uff09\u21d2 %s\uff08\u9884\u671f \u2265+3pp \u4e14\u53ea\u52a0\u4e0d\u51cf\uff09\uff08%.0fs\uff09"
                % (cand, b, c, base_only, "PASS" if ok else "WARN", time.time() - t0))
            if not ok:
                warns.append("%s window \u7d22\u53d6\u7387 %.1f%%\u2192%.1f%%\uff08\u4ec5\u57fa\u7ebf\u6536 %d\uff09" % (cand, b, c, base_only))

    # ★ R1481：V 轴的**机制读数** —— campaign7 §2 把机制定义为
    #   「爆头/胡 上升 **且** 番/胡 上升」（足迹只是必要条件），
    #   而它只能用 `_seat_h2h --by-arm` 量。不满足 ⇒ 归入 warns（⇒ `.mech_warn`
    #   ⇒ `_adopt_pair` 按 B3 不采用）；读数缺失 ⇒ 另写 `.v_mech_unknown`（**响亮但不阻塞**）。
    v_cands = [c for c in cands if has_v_layer(c)]   # ★ R1515：按 W_TILES 判（抽中 bcvmeld）
    if v_cands and not a.dry_run:
        _since = cfg.get("started") or ""
        cmd = [sys.executable, "-X", "utf8", LOWPRIO, "--",
               sys.executable, "-X", "utf8", SEAT_H2H,
               "--since", _since, "--by-arm", "--top", "32"]
        rows = {}
        try:
            p3 = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=1800)
            rows = parse_h2h(p3.stdout or "")
            if not rows:
                # ★ R1509：**读数缺失不能被吞掉** —— 必须留下可诊断证据。
                #   实测：00:37 那次写了 `.v_mech_unknown`（“读数缺失（base=False cand=False）”），
                #   而日志里**没有 rc / stderr / 行数** ⇒ 无法判断是崩了还是解析不上（而超时是会记的）。
                log("!! V 机制读数（_seat_h2h）解析为空：rc=%s stdout=%d 字 stderr=%s"
                    % (getattr(p3, "returncode", "?"), len(p3.stdout or ""),
                       ((p3.stderr or "").strip().replace("\n", " ")[:200]) or "（空）"))
        except subprocess.TimeoutExpired:
            log("!! V 机制读数（_seat_h2h）超时（>1800s）")
        except Exception as e:
            log("!! V 机制读数（_seat_h2h）异常：%s" % str(e)[:120])
        base_row = rows.get((baseline, "我方"))
        for cand in v_cands:
            ok, why = judge_v_mech(base_row, rows.get((cand, "我方")))
            tag = {True: "PASS", False: "WARN", None: "UNKNOWN"}[ok]
            log("  %s 机制（爆头/胡、番/胡）：%s ⇒ %s" % (cand, why, tag))
            append_v_record({"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "arm": cand,
                             "baseline": baseline, "ok": ok, "why": why,
                             "base": base_row, "cand": rows.get((cand, "我方"))})
            _states.append(ok)
            if ok is False:
                warns.append("%s 机制不达标（%s）" % (cand, why))
            elif ok is None:
                try:
                    with io.open(UNK, "w", encoding="utf-8") as f:
                        f.write("%s %s 机制读数缺失：%s\n"
                                % (time.strftime("%Y-%m-%d %H:%M:%S"), cand, why))
                except Exception:
                    pass
    # ★ R1484：标记的写/删**统一按 unk_action()** —— 读数齐了就必须清掉陈旧标记。
    _act = unk_action(v_cands, _states)
    try:
        if _act == "write":
            _miss = [c for c, st in zip(v_cands, _states) if st is None]
            with io.open(UNK, "w", encoding="utf-8") as f:
                f.write("%s V 轴机制读数缺失（候选 %s）\n"
                        % (time.strftime("%Y-%m-%d %H:%M:%S"), ",".join(_miss)))
        elif os.path.exists(UNK):
            os.remove(UNK)
    except Exception as _e:
        log("!! .v_mech_unknown 处置失败：%s" % str(_e)[:40])

    # ★ R1431：顺带跑一次「提交延迟 + 失效动作」审计（预登记的 "超窗 = 0" 护栏），只记不判（避免历史尾部造噪）
    if not a.dry_run:
        try:
            cfg2 = json.loads(io.open(a.ab_file, encoding="utf-8-sig").read())
            since2 = cfg2.get("started") or ""
        except Exception:
            since2 = ""
        cmd2 = [sys.executable, "-X", "utf8", os.path.join(ROOT, "var", "_submit_latency_audit.py")] + \
               (["--since", since2] if since2 else [])
        try:
            p2 = subprocess.run(cmd2, cwd=ROOT, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=600)
            lines2 = [l.strip() for l in (p2.stdout or "").splitlines() if l.strip()]
            key = [l for l in lines2 if ("提交" in l or "p99" in l or "真损失" in l or ">=1000" in l or "≥1000" in l or "≥2000" in l)]
            for l in key[-8:]:
                log("  [lat] " + l)
        except Exception as e:
            log("  [lat] 审计跳过：%s" % str(e)[:60])

    if a.dry_run:
        return 0
    try:
        if warns:
            with io.open(os.environ.get("HM_MECH_WARN", WARN), "w", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S") + " " + "\uff1b".join(warns) + "\n")
            log("\u26a0 \u673a\u5236\u7aef\u70b9\u544a\u8b66\uff1a" + "\uff1b".join(warns))
        else:
            _w = os.environ.get("HM_MECH_WARN", WARN)
            if os.path.exists(_w):
                os.remove(_w)
            log("\u673a\u5236\u7aef\u70b9\u6b63\u5e38\uff08\u5f79 %s vs %s\uff09" % (",".join(cands), baseline))
    except Exception as e:
        log("\u26a0 \u6807\u8bb0\u5199\u5165\u5931\u8d25\uff1a%s" % str(e)[:60])
    return 0


if __name__ == "__main__":
    sys.exit(main())