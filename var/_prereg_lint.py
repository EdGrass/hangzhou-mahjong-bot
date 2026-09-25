# -*- coding: utf-8 -*-
"""`var/_prereg_lint.py` —— **役次预登记格式体检**（只读，R1237）。

## 为什么

到 10/7 有 5+ 份预登记（役 3/4/5/6…）。判词当天"**预登记里没写清**"是最贵的错误（R1156 就吃过阈值没写的亏）。
本工具把"**每份预登记必须包含什么**"固化成检查项，并打一张横向对比表，便于一眼看出**谁的主端点/阈值不一致**。

必需项（缺一即 ❌）：
  ① 臂（类名/文件名）② 主端点 + 阈值 ③ 副端点 ④ **机制端点** ⑤ 护栏 ⑥ 事前预测
  ⑦ 判词分支（采用/不采用）⑧ 起役清单（含 `--bundles` 或 `_switch_campaign`）⑨ 风险

## 修订（2026-09-24 07:1x，R1243）

两个缺陷会让本工具在起役门禁上**误报红**、并**报错臂名**：

1. **旧方案的作废稿仍被计为 ❌**：同一役位历史上写过好几版（hybrid / 杠束 / 副露放宽），
   被后来证据否决后没有从目录消失 ⇒ 体检永远红 ⇒ 起役当天看到"❌ 有 3 份缺项"会犹豫。
   现在：文件头 14 行内出现 `[SUPERSEDED` / `已作废` / `SUPERSEDED` 即归入"已作废"一栏、**不计入失败**。
2. **"臂"列取的是文档里第一个反引号 `Speed\\w+`**：主/候选都写成反引号时会取到**基线**
   （例：`prereg-campaign3-speedvaluebc` 显示 `臂=SpeedValue`，真候选是 `speedvaluebc`）。
   现在：优先取 `bot.<module>`（**这是 `--candidate` 真正接受的策略名**），回退 `bot/*.py` 文件名匹配。

用法：
    python -X utf8 var/_prereg_lint.py
    python -X utf8 var/_prereg_lint.py --dir docs/iter/reports
"""
from __future__ import annotations
import argparse, glob, io, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECKS = [
    ("臂", [r"bot\.(speed\w+)", r"bot/\w+\.py", r"`(Speed\w+)`", r"`speed\w+`"]),
    ("主端点", [r"主.*和牌率/房", r"z\s*≥\s*1\.50"]),
    ("副端点", [r"番/房"]),
    ("机制端点", [r"机制", r"改动率|索取率|推进率"]),
    ("护栏", [r"护栏"]),
    ("事前预测", [r"事前预测|预测"]),
    ("判词分支", [r"B1|采用"]),
    ("起役清单", [r"ab_ctl|_switch_campaign|起役清单"]),
    ("风险", [r"风险"]),
]
SUPERSEDED_MARKS = ("[SUPERSEDED", "已作废", "SUPERSEDED")
HEAD_LINES = 14


def registered_arms():
    """`bot/*.py` 里存在的策略模块名（= `--candidate` 接受的策略名）。"""
    out = set()
    for p in glob.glob(os.path.join(ROOT, "bot", "*.py")):
        out.add(os.path.splitext(os.path.basename(p))[0])
    return out


def is_superseded(text):
    head = "\n".join(text.splitlines()[:HEAD_LINES])
    return any(m in head for m in SUPERSEDED_MARKS)


def arm_of(text, name, reg):
    """候选臂名：优先 `bot.<module>`（权威），再回退文件名里最长的已注册臂名。"""
    m = re.search(r"bot\.(speed\w+)\b", text)
    if m:
        return m.group(1)
    cands = [a for a in reg if a.startswith("speed") and a in name]
    if cands:
        return max(cands, key=len)
    m = re.search(r"`(Speed\w+)`", text)
    return m.group(1) if m else "?"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.join("docs", "iter", "reports"))
    ap.add_argument("--pattern", default="prereg-*.md")
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(ROOT, a.dir, a.pattern)))
    if not files:
        print("没找到预登记文件（%s/%s）" % (a.dir, a.pattern))
        return 2

    reg = registered_arms()
    print("=" * 104)
    print("预登记格式体检（%d 份）" % len(files))
    print("=" * 104)
    bad, dead = [], []
    for f in files:
        s = io.open(f, encoding="utf-8").read()
        name = os.path.basename(f)
        if is_superseded(s):
            dead.append(name)
            print("%-58s %s" % (name[:58], "— 已作废（跳过体检，不计入失败）"))
            continue
        miss = []
        for label, pats in CHECKS:
            if not any(re.search(p, s) for p in pats):
                miss.append(label)
        m_main = re.search(r"z\s*≥\s*([\d.]+)", s)
        m_rooms = re.search(r"≥\s*(\d+)\s*房", s)
        print("%-58s 主 z≥%-5s 房≥%-4s 臂=%-22s %s"
              % (name[:58], m_main.group(1) if m_main else "?",
                 m_rooms.group(1) if m_rooms else "?", arm_of(s, name, reg),
                 ("✅" if not miss else "❌ 缺：" + ",".join(miss))))
        if miss:
            bad.append((name, miss))

    print()
    if dead:
        print("— 已作废 %d 份（留档，不计入体检）：%s" % (len(dead), "、".join(dead)))
    if bad:
        print("❌ 有 %d 份**在用**预登记缺项：" % len(bad))
        for n, m in bad:
            print("   - %s：%s" % (n, "、".join(m)))
        return 2
    print("✅ 全部**在用**预登记包含必需项（臂 / 主端点+阈值 / 副端点 / 机制端点 / 护栏 / 事前预测 / 判词分支 / 起役清单 / 风险）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
