# -*- coding: utf-8 -*-
"""`var/_bsegment.py` \u2014\u2014 **\u5f79\u95f4\u5207\u6362 B \u6bb5\u7684\u4e00\u952e\u6267\u884c\u5668**\uff08\u9ed8\u8ba4\u53ea\u6253\u5370\uff1b`--go` \u624d\u52a8\u624b\uff09\u3002

\u4e3a\u4ec0\u4e48\uff1a\u00a7V.51 \u7684 B \u6bb5\u662f\u4e94\u6b65\u3001\u7ea6 25 \u79d2\u7a97\u53e3\u3001\u4e14 C \u6bb5\u8981\u628a B \u6bb5\u6253\u5370\u7684\u201c\u8d77\u5f79\u65f6\u95f4\u6233\u201d**\u9010\u5b57**\u6284\u8fdb\u770b\u62a4\u6ce8\u518c
\uff08\u6284\u9519 \u21d2 \u4e24\u5bf9\u770b\u62a4\u8bfb\u5230\u4e0d\u540c\u623f\u96c6\uff09\u3002\u672c\u811a\u672c\u628a\u4e94\u6b65\u4e32\u8054\u5e76**\u76f4\u63a5\u4ece\u8f93\u51fa\u91cc\u89e3\u6790\u65f6\u95f4\u6233**\uff1a

  1) `tools/ab_ctl.py stop`\uff08\u53ea\u505c\u9a71\u52a8\uff0c**\u7edd\u4e0d\u5f3a\u505c\u5728\u6253\u5bf9\u5c40**\uff09
  2) \u7b49 `run_bot`/`match_super`/`_ab_driver` \u81ea\u7136\u9000\u51fa\uff08\u6709\u754c\uff09
  3) `var/_apply_p0_404.py --go`\uff08v35 \u8865\u4e01\uff09
  4) `tools/preflight.py`\uff08\u671f\u671b READY\uff1b\u975e READY \u9700\u663e\u5f0f `--allow-not-ready`\uff09
  5) `var/_switch_campaign.py --baseline <B> --candidates <C> --bundles <B> --go` \u2192 \u89e3\u6790\u65f6\u95f4\u6233
  6) `var/_register_campaign3_watches.ps1 -Since <\u89e3\u6790\u5230\u7684\u65f6\u95f4\u6233> -Go`

**\u7ea2\u7ebf**\uff1a\u4e0d\u4f1a\u81ea\u5df1\u8d77\u5f79\uff08\u5fc5\u987b\u4eba\u5de5 `--go`\uff09\uff1b\u4e0d\u5f3a\u505c\u4efb\u4f55\u5728\u6253\u5bf9\u5c40\uff1b\u4e0d\u6539\u9884\u767b\u8bb0\u9608\u503c\u3002
"""
from __future__ import annotations
import _ps  # noqa: E402  （★ R1379）
import argparse, io, os, re, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AB = os.path.join(ROOT, "var", ".ab_mode")
LOG = os.path.join(ROOT, "var", "_bsegment.out")
TS_RE = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")


def switched_mark(label, var_dir=None):
    return os.path.join(var_dir or os.path.join(ROOT, "var"), ".bsegment_switched_%s" % label)


def parse_switched(text):
    """→ dict(ts, base, cands)。（纯函数，便于单测）"""
    out = {}
    # ★ R1542 实测教训：`ts` 是**含空格的日期时间**，用 `\S+` 会截断成 `2026-09-29`
    #   ⇒ 与 `.ab_mode.started` 永远不相等 ⇒ 整个幂等修复在生产里形同虚设（新测试当场报红）。
    m = re.search(r"ts=(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", text or "")
    if m:
        out["ts"] = m.group(1)
    for k in ("base", "cands"):
        m = re.search(k + r"=(\S+)", text or "")
        if m:
            out[k] = m.group(1)
    return out


def read_ab(path=None):
    """→ (started, arms, bundle)；读不出 ⇒ ("", [], "")"""
    try:
        import json
        with io.open(path or AB, encoding="utf-8-sig") as _fh:   # ★ 句柄必关
            d = json.loads(_fh.read())
        arms = [str(x) for x in (d.get("arms") or [d.get("a"), d.get("b")]) if x]
        return (str(d.get("started") or ""), arms,
                str(((d.get("bundles") or arms[:1]) or [""])[0] or ""))
    except Exception:
        return "", [], ""


def already_switched(label, mark_path=None, ab_path=None):
    """★ R1542：**本役是否已经切过** ⇒ (done, ts, why)。

    为什么需要：`_adopt_pair` 每 10 分钟重试一次。若第 4 步
    `_switch_campaign` **成功**、而紧接着的**看护注册**失败，旧实现下一次重试会
    **重跑整个 B 段** ⇒ 用**新的起役时间戳再切一次役** ⇒ 已打的房全部作废，
    而且**每 10 分钟无限重切**（永远攒不满 80 房 ⇒ 判词到不了 ⇒ 链与排期一起毁）。

    现在：切役成功后立刻落 `.bsegment_switched_<label>`；重试时若它与当前
    `.ab_mode` **一致**（ts 相等，或 ts 未记但臂集/基线一致）⇒ 只**重试注册**，跳过 1–4。
    """
    mp = mark_path or switched_mark(label)
    if not os.path.exists(mp):
        return False, "", "无切役标记"
    try:
        d = parse_switched(io.open(mp, encoding="utf-8-sig", errors="replace").read())
    except Exception:
        return False, "", "切役标记读不出"
    started, arms, bundle = read_ab(ab_path)
    if not started:
        return False, "", "无 .ab_mode"
    ts = d.get("ts") or ""
    if ts and ts == started:
        return True, ts, "标记 ts 与 .ab_mode.started 一致"
    if not ts and arms:
        base = d.get("base") or ""
        want = set([base] + [c.strip() for c in (d.get("cands") or "").split(",") if c.strip()])
        if base and want == set(arms) and bundle == base:
            return True, started, "臂集/基线一致（标记未记 ts）"
    return False, "", "标记与当前 .ab_mode 不一致（=新的役）"


def say(msg, fh=None):
    line = "%s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line, flush=True)
    if fh:
        fh.write(line + "\n")
        fh.flush()


def run(cmd, fh, timeout=2400):
    say("$ " + " ".join(cmd), fh)
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    out = (p.stdout or "") + (p.stderr or "")
    for l in out.strip().splitlines()[-12:]:
        say("  | " + l, fh)
    return p.returncode, out


def procs_alive():
    try:
        import psutil
    except Exception:
        return []
    names = ("run_bot.py", "match_super.py", "_ab_driver.py")
    out = []
    for p in psutil.process_iter(["cmdline", "exe"]):
        try:
            if "python" not in os.path.basename(p.info.get("exe") or "").lower():
                continue
            for a in (p.info.get("cmdline") or [])[1:]:
                if os.path.basename(str(a).replace("\\", "/")) in names:
                    out.append(os.path.basename(str(a))); break
        except Exception:
            pass
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true", help="\u771f\u6267\u884c\uff08\u9ed8\u8ba4\u53ea\u6253\u5370\uff09")
    ap.add_argument("--baseline", default="speedvalue")
    ap.add_argument("--candidates", default="speedvaluebc,speedvaluebaotouv5")
    ap.add_argument("--wait-min", type=int, default=25)
    ap.add_argument("--allow-not-ready", action="store_true")
    ap.add_argument("--watch-mechanism", default="none",
                    help="通用注册器用的机制口径（役 4 副露轴用 melds）")
    ap.add_argument("--label", default="役3",
                    help="役标签：默认 役3 → 原来的 _register_campaign3_watches.ps1（今晚路径不变）；其他标签 → 通用注册器")
    a = ap.parse_args(argv)
    py = sys.executable
    steps = [
        ("1) \u505c A/B \u9a71\u52a8", [py, "-X", "utf8", "tools/ab_ctl.py", "stop"]),
        ("2) P0 \u8865\u4e01", [py, "-X", "utf8", "var/_apply_p0_404.py", "--go"]),
        ("3) preflight", [py, "-X", "utf8", "tools/preflight.py"]),
        ("4) \u5207\u5f79", [py, "-X", "utf8", "var/_switch_campaign.py", "--baseline", a.baseline,
                         "--candidates", a.candidates, "--bundles", a.baseline, "--go"]),
    ]
    print("=== B \u6bb5\uff08%s\uff09===" % ("\u771f\u6267\u884c" if a.go else "dry-run"))
    for name, cmd in steps:
        print("  %-16s %s" % (name, " ".join(cmd)))
    print("  5) " + ("注册两对看护   pwsh -File var/_register_campaign3_watches.ps1 -Since <上一步输出的时间戳> -Go" if a.label in ("役3", "3", "") else
              "注册看护(通用) pwsh -File var/_register_campaign_watches.ps1 -Label %s -Since <时戳> -Baseline %s -Candidates %s -Mechanism %s -Go" % (a.label, a.baseline, a.candidates, a.watch_mechanism)))
    print("  注（R1542）：若 `var/.bsegment_switched_%s` 与当前 `.ab_mode` 一致（ts 或臂集），"
          "说明**本役已经切过** ⇒ 只重试第 5 步注册，跳过 1–4（避免用新时戳重切、把已打的房作废）。" % a.label)
    if not a.go:
        print("\uff08dry-run\uff1a\u672a\u6267\u884c\uff1b\u52a0 --go \u624d\u771f\u8dd1\uff09")
        return 0
    fh = io.open(LOG, "a", encoding="utf-8")
    try:
        done, prev_ts, why = already_switched(a.label)
        if done:
            ts = prev_ts
            say("★ 本役已经切过（%s）⇒ 跳过步骤 1–4，只重试看护注册" % why, fh)
        else:
            if os.path.exists(AB):
                rc, _ = run([py, "-X", "utf8", "tools/ab_ctl.py", "stop"], fh)
                if rc != 0:
                    say("!! ab_ctl stop rc=%s ⇒ 停止（不强停）" % rc, fh); return 2
            t0 = time.time()
            while time.time() - t0 < a.wait_min * 60:
                alive = procs_alive()
                if not alive:
                    break
                say("等对局自然结束中（还在：%s）" % ",".join(sorted(set(alive))), fh)
                time.sleep(15)
            else:
                say("!! 等 %d 分钟仍有进程 ⇒ 停止（绝不强停）" % a.wait_min, fh); return 2
            say("空档已到", fh)
            rc, _ = run([py, "-X", "utf8", "var/_apply_p0_404.py", "--go"], fh)
            if rc != 0:
                say("!! P0 补丁失败 rc=%s ⇒ 停止" % rc, fh); return 2
            rc, out = run([py, "-X", "utf8", "tools/preflight.py"], fh)
            if rc != 0 and not a.allow_not_ready:
                say("!! preflight 非 READY ⇒ 停止（若已确认原因无害，加 --allow-not-ready）", fh); return 2
            rc, out = run([py, "-X", "utf8", "var/_switch_campaign.py", "--baseline", a.baseline,
                           "--candidates", a.candidates, "--bundles", a.baseline, "--go"], fh)
            if rc != 0:
                say("!! 切役失败 rc=%s ⇒ 停止" % rc, fh); return 2
            # ★ 必须只看“起役时间戳”那一行：整体 search 会先匹配到“台账残留”列里的旧时间戳（实测发现）。
            m = None
            for _l in out.splitlines():
                if "起役时间戳" in _l:
                    m = TS_RE.search(_l)
                    if m:
                        break
            ts = m.group(1) if m else read_ab()[0]      # ★ R1542：兜底取 .ab_mode.started
            if not ts:
                say("!! 未能解析起役时间戳（.ab_mode.started 也读不到）⇒ 请手工注册看护", fh); return 2
            say("起役时间戳：%s%s" % (ts, "" if m else "（来自 .ab_mode.started 兜底）"), fh)
            # ★ R1542：**先落“已切役”标记、再注册看护** ——
            #   若注册失败而下次重试，必须能认出“这一役已经切过”而**不要重切**。
            try:
                with io.open(switched_mark(a.label), "w", encoding="utf-8") as _mf:
                    _mf.write("ts=%s base=%s cands=%s\n" % (ts, a.baseline, a.candidates))
            except Exception as _e:
                say("!! 写切役标记失败：%s（下次重试可能重切，请人工留意）" % str(_e)[:60], fh)
        shell = _ps.exe()
        _legacy = a.label in ("役3", "3", "")
        rc, _ = (run([shell, "-NoProfile", "-File", "var/_register_campaign3_watches.ps1", "-Since", ts, "-Go"], fh)
                       if _legacy else
                       run([shell, "-NoProfile", "-File", "var/_register_campaign_watches.ps1",
                            "-Label", a.label, "-Since", ts, "-Baseline", a.baseline,
                            "-Candidates", a.candidates, "-Mechanism", a.watch_mechanism, "-Go"], fh))
        if rc != 0:
            say("!! 看护注册 rc=%s ⇒ 人工重跑（役已切；**下次重试会跳过切役、只补注册**）" % rc, fh); return 2
        say("★ B 段完成（起役时间戳 %s）" % ts, fh)
        return 0
    finally:
        fh.close()


if __name__ == "__main__":
    sys.exit(main())