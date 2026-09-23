"""ab_baotou_probe.py —— 在**自家真实决策**上比两臂的「爆头形可达性」（本地 `.dec.jsonl`，零延迟）。

回答：候选（如 c151 压对数）是否真的让"可胡时能给出爆头形弃牌"的比例上升？
这是 §9.25 定位的瓶颈（造形能力），也是比"对数签名"更靠近任务的机制端点。

用法：python -X utf8 tools/ab_baotou_probe.py
"""
from __future__ import annotations
import collections, glob, json, math, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from mahjong.hu import is_baotou, is_win     # noqa: E402


def main():
    since = None; arms = None
    ab = os.path.join(ROOT, 'var', '.ab_mode')
    if os.path.exists(ab):
        try:
            cfg = json.loads(open(ab, encoding='utf-8').read())
            since = cfg.get('started'); arms = {cfg.get('a'), cfg.get('b')}
        except Exception:
            pass
    rmap = {}
    for ln in open(os.path.join(ROOT, 'var', 'auto_ranking.jsonl'), encoding='utf-8'):
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
        except Exception:
            continue
        if d.get('room'):
            rmap[d['room']] = (d.get('strategy') or '?', d.get('ts') or '')

    S = collections.defaultdict(lambda: [0] * 8)
    # 0 决策, 1 可胡, 2 有爆头形, 3 实际弃胡, 4 实际胡, 5 对数和(可胡时), 6 白数和(可胡时), 7 爆头形白>0
    for f in glob.glob(os.path.join(ROOT, 'var', 'replays', 'auto_*', '*.dec.jsonl')):
        base = os.path.basename(f)
        room = base.split('_r')[0]
        info = rmap.get(room)
        if not info:
            continue
        stg, ts = info
        if since and ts < since:
            continue
        if arms and stg not in arms:
            continue
        try:
            for ln in open(f, encoding='utf-8'):
                ln = ln.strip()
                if not ln:
                    continue
                o = json.loads(ln)
                if o.get('p') != 'draw':
                    continue
                h = o.get('h') or []
                d = o.get('d')
                m = o.get('m') or []
                e = len(m)
                g = sum(1 for x in m if isinstance(x, dict) and x.get('type') == 'gang')
                a = S[stg]; a[0] += 1
                if not d or len(h) != 14 - 3 * e:
                    continue
                try:
                    if not is_win(list(h), exposed_melds=e, gangs=g):
                        continue
                except Exception:
                    continue
                a[1] += 1
                cnt = collections.Counter(h)
                a[5] += sum(1 for v in cnt.values() if v >= 2)
                a[6] += cnt.get('白', 0)
                has = False
                for dd in sorted(set(h)):
                    aft = list(h); aft.remove(dd)
                    try:
                        if is_baotou(aft, allow_qidui=(e == g == 0), exposed_melds=e, gangs=g):
                            has = True; break
                    except Exception:
                        pass
                if has:
                    a[2] += 1
                    if cnt.get('白', 0) > 0:
                        a[7] += 1
                act = (o.get('a') or {}).get('action')
                if act == 'discard':
                    a[3] += 1
                elif act == 'hu':
                    a[4] += 1
        except Exception:
            continue

    print('=' * 96)
    print('自家决策上的「爆头形可达性」（本地 .dec.jsonl，零延迟）  since=%s' % since)
    print('=' * 96)
    if not S:
        print('窗口内没有可归属的决策记录。'); return
    print('%-14s %7s %7s %10s %10s %10s %10s' % ('arm', '决策', '可胡', '有爆头形%', '实弃胡%', '平均对数', '平均白数'))
    for stg in sorted(S):
        a = S[stg]
        if not a[0]:
            continue
        hu = a[1]
        bo = a[2] / max(1, hu)
        se = math.sqrt(bo * (1 - bo) / max(1, hu))
        print('%-14s %7d %7d %9.1f%% %9.1f%% %10.2f %10.2f' % (
            stg, a[0], hu, 100 * bo, 100 * a[3] / max(1, hu), a[5] / max(1, hu), a[6] / max(1, hu)))
        print('%-14s %7s %7s %9.2f%%' % ('  ±SE(1σ)', '', '', 100 * se))
    print()
    print('判读：候选若声称"造爆头形"，则看「有爆头形%」；若它同时压低「平均对数」，机制链就闭合了。')


if __name__ == '__main__':
    main()
