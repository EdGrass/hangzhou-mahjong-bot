# -*- coding: utf-8 -*-
"""Read-only consolidated A/B gate report.

Runs the complete pre-registered readout chain once and writes one timestamped
report. It never starts/stops games or edits bot files.
"""
from __future__ import annotations

import argparse
import datetime
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable


def run(cmd, out):
    out.write("\n$ " + " ".join(cmd) + "\n")
    p = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, text=True,
                       encoding="utf-8", errors="replace")
    out.write(p.stdout or "")
    out.write("\n[exit=%d]\n" % p.returncode)
    return p.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", required=True,
                    help='start time, e.g. "2026-09-20 14:54:07"')
    ap.add_argument("--candidate", required=True,
                    help="adoption candidate name, e.g. speedc151")
    a = ap.parse_args()
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(ROOT, "var", "gate_report_%s.txt" % stamp)
    codes = {}
    with open(path, "w", encoding="utf-8", newline="\n") as out:
        out.write("A/B GATE REPORT  %s\n" % datetime.datetime.now().isoformat(timespec="seconds"))
        out.write("since=%s candidate=%s\n" % (a.since, a.candidate))
        codes["readout"] = run([PY, "-X", "utf8", "tools/ab_readout.py",
                                "--since", a.since], out)
        codes["first_rate"] = run([PY, "-X", "utf8", "var/_first_rate_readout.py",
                                   "--since", a.since], out)
        codes["power"] = run([PY, "-X", "utf8", "var/_power_two_endpoints.py",
                              "--since", a.since], out)
        codes["integrity"] = run([PY, "-X", "utf8", "var/_camp_integrity.py",
                                  "--since", a.since], out)
        codes["breaker"] = run([PY, "-X", "utf8", "var/_breaker_watch.py",
                                "--since", a.since], out)
        codes["adopt_provisional"] = run([PY, "-X", "utf8", "tools/ab_adopt.py",
                                             a.candidate, "--provisional", "--dry-run"], out)
        codes["adopt_noninf"] = run([PY, "-X", "utf8", "tools/ab_adopt.py",
                                        a.candidate, "--noninf", "--dry-run"], out)
        codes["adopt_frozen"] = run([PY, "-X", "utf8", "tools/ab_adopt.py",
                                        a.candidate, "--dry-run"], out)
        out.write("\nSUMMARY %s\n" % codes)
    print("gate report saved: %s" % path)
    print("exit codes: %s" % codes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
