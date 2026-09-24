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
              "注册看护(通用) pwsh -File var/_register_campaign_watches.ps1 -Label %s -Since <时戳> -Baseline %s -Candidates %s -Go" % (a.label, a.baseline, a.candidates)))
    if not a.go:
        print("\uff08dry-run\uff1a\u672a\u6267\u884c\uff1b\u52a0 --go \u624d\u771f\u8dd1\uff09")
        return 0
    fh = io.open(LOG, "a", encoding="utf-8")
    try:
        if os.path.exists(AB):
            rc, _ = run([py, "-X", "utf8", "tools/ab_ctl.py", "stop"], fh)
            if rc != 0:
                say("!! ab_ctl stop rc=%s \u21d2 \u505c\u6b62\uff08\u4e0d\u5f3a\u505c\uff09" % rc, fh); return 2
        t0 = time.time()
        while time.time() - t0 < a.wait_min * 60:
            alive = procs_alive()
            if not alive:
                break
            say("\u7b49\u5bf9\u5c40\u81ea\u7136\u7ed3\u675f\u4e2d\uff08\u8fd8\u5728\uff1a%s\uff09" % ",".join(sorted(set(alive))), fh)
            time.sleep(15)
        else:
            say("!! \u7b49 %d \u5206\u949f\u4ecd\u6709\u8fdb\u7a0b \u21d2 \u505c\u6b62\uff08\u7edd\u4e0d\u5f3a\u505c\uff09" % a.wait_min, fh); return 2
        say("\u7a7a\u6863\u5df2\u5230", fh)
        rc, _ = run([py, "-X", "utf8", "var/_apply_p0_404.py", "--go"], fh)
        if rc != 0:
            say("!! P0 \u8865\u4e01\u5931\u8d25 rc=%s \u21d2 \u505c\u6b62" % rc, fh); return 2
        rc, out = run([py, "-X", "utf8", "tools/preflight.py"], fh)
        if rc != 0 and not a.allow_not_ready:
            say("!! preflight \u975e READY \u21d2 \u505c\u6b62\uff08\u82e5\u5df2\u786e\u8ba4\u539f\u56e0\u65e0\u5bb3\uff0c\u52a0 --allow-not-ready\uff09", fh); return 2
        rc, out = run([py, "-X", "utf8", "var/_switch_campaign.py", "--baseline", a.baseline,
                       "--candidates", a.candidates, "--bundles", a.baseline, "--go"], fh)
        if rc != 0:
            say("!! \u5207\u5f79\u5931\u8d25 rc=%s \u21d2 \u505c\u6b62" % rc, fh); return 2
        # ★ 必须只看“起役时间戳”那一行：整体 search 会先匹配到“台账残留”列里的旧时间戳（实测发现）。
        m = None
        for _l in out.splitlines():
            if "起役时间戳" in _l:
                m = TS_RE.search(_l)
                if m:
                    break
        if not m:
            say("!! \u672a\u80fd\u4ece\u5207\u5f79\u8f93\u51fa\u89e3\u6790\u51fa\u8d77\u5f79\u65f6\u95f4\u6233 \u21d2 \u8bf7\u624b\u5de5\u6ce8\u518c\u770b\u62a4", fh); return 2
        ts = m.group(1)
        say("\u89e3\u6790\u5230\u8d77\u5f79\u65f6\u95f4\u6233\uff1a%s" % ts, fh)
        shell = _ps.exe()
        _legacy = a.label in ("役3", "3", "")
        rc, _ = (run([shell, "-NoProfile", "-File", "var/_register_campaign3_watches.ps1", "-Since", ts, "-Go"], fh)
                       if _legacy else
                       run([shell, "-NoProfile", "-File", "var/_register_campaign_watches.ps1",
                            "-Label", a.label, "-Since", ts, "-Baseline", a.baseline,
                            "-Candidates", a.candidates, "-Go"], fh))
        if rc != 0:
            say("!! \u770b\u62a4\u6ce8\u518c rc=%s \u21d2 \u8bf7\u624b\u5de5\u91cd\u8dd1\uff08\u5f79\u5df2\u5207\uff09" % rc, fh); return 2
        say("\u2605 B \u6bb5\u5b8c\u6210\uff08\u8d77\u5f79\u65f6\u95f4\u6233 %s\uff09" % ts, fh)
        return 0
    finally:
        fh.close()


if __name__ == "__main__":
    sys.exit(main())