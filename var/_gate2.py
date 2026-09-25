# -*- coding: utf-8 -*-
"""Campaign judgment on the LOW-VARIANCE replay endpoint (READ-ONLY).

Pre-registered rule (plan §G, from R1037):
  * PRIMARY   : replay 和牌率/房, z >= 1.50, each arm >= 80 rooms, coverage >= 70%
  * SECONDARY : replay 番/房, z >= 1.50 and SAME SIGN as primary
  * GUARDRAIL : ledger 第一率 (candidate >= baseline); ledger 净分 same sign (not blocking)
  * MECHANISM : declared mechanism metric must move the right way (melds / gangs / none)
  * Fail-closed: coverage < 70% or arm < 80 rooms -> REFUSE (攒房/补复盘), never adopt.

usage:
  python -X utf8 var/_gate2.py --since "2026-09-24 00:00:00" \
      --baseline speedc151 --candidate speedvalue --mechanism melds
"""
from __future__ import annotations
import argparse, collections, glob, importlib.util, io, json, math, os, statistics, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # ★ R1522：从 __file__ 推（原硬编码 D:\hangzhouMaj ⇒ clone 里必崩）
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, os.path.join(ROOT, 'var'))
import ab_readout as AR                                    # noqa: E402

_spec = importlib.util.spec_from_file_location('rep_ep2', os.path.join(ROOT, 'var', '_replay_endpoint.py'))
REP = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(REP)

MIN_ROOMS = 80
MIN_COVER = 0.70
Z_CRIT = 1.50


def _stats(a, b):
    ma, mb = statistics.mean(a), statistics.mean(b)
    se = math.sqrt(statistics.variance(a) / len(a) + statistics.variance(b) / len(b))
    return mb - ma, se, (mb - ma) / se if se else 0.0



def _pair_profile(files):
    """(mean pairs, % of states with >=3 pairs) at own draws 5 and 7, 0-白, no melds.

    Measured on the SAME replays the campaign produced, so it is the *realised*
    mechanism footprint (the leaderboard top32 sits at ~2.48 mean / ~24.8% >=3 pairs
    at draw 7, while our c151 family is pinned at ~2.33 / ~8.5%).  READ-ONLY.
    """
    import collections as _c
    cnt = _c.Counter()
    tot = n3 = 0
    for f in files:
        try:
            d = json.load(io.open(f, encoding='utf-8'))
        except Exception:
            continue
        seats = d.get('seats') or []
        uids = [(s.get('user_id') or '') for s in seats]
        if len(seats) != 4 or REP.ME not in uids:
            continue
        me = uids.index(REP.ME)
        rounds = {}
        for b in d.get('blocks') or []:
            rn = b.get('round_no')
            if rn is None:
                continue
            rec = rounds.setdefault(rn, {'ev': {}, 'start': None})
            sh0 = b.get('start_hands')
            if sh0 and len(sh0) == 4 and all(isinstance(x, (list, tuple)) for x in sh0):
                rec['start'] = [list(x) for x in sh0]
            for e in b.get('events') or []:
                if e.get('seq') is not None:
                    rec['ev'][e['seq']] = e
        for rn, rec in rounds.items():
            if rec['start'] is None or rec['start'][me].count('白') != 0:
                continue
            h = list(rec['start'][me])
            draws = 0
            melds = 0
            for sq in sorted(rec['ev']):
                e = rec['ev'][sq]
                t = e.get('type'); s = e.get('seat')
                if not isinstance(s, int) or not (0 <= s < 4):
                    continue
                if s == me:
                    if t == 'tile_drawn':
                        h.append(e.get('tile')); draws += 1
                    elif t == 'tile_discarded':
                        tile = e.get('tile')
                        if tile in h:
                            h.remove(tile)
                        if melds == 0 and draws in (5, 7):
                            c = _c.Counter(x for x in h if x != '白')
                            p = sum(1 for v in c.values() if v >= 2)
                            tot += 1
                            cnt[min(p, 4)] += 1
                            if p >= 3:
                                n3 += 1
                    elif t == 'chi':
                        for x in ((e.get('data') or {}).get('tiles') or []):
                            if x != e.get('tile') and x in h:
                                h.remove(x)
                        melds += 1
                    elif t == 'peng':
                        tile = e.get('tile')
                        for _ in range(2):
                            if tile in h:
                                h.remove(tile)
                        melds += 1
                    elif t == 'gang':
                        tile = e.get('tile'); knd = (e.get('data') or {}).get('kind')
                        need = 4 if knd == 'an' else (3 if knd == 'ming' else 1)
                        for _ in range(need):
                            if tile in h:
                                h.remove(tile)
                        melds += 1
                else:
                    if t == 'tile_discarded' and e.get('tile') in h:
                        pass
    if not tot:
        return 0.0, 0.0
    mean = sum(k * v for k, v in cnt.items()) / tot
    return mean, 100.0 * n3 / tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--since', required=True)
    ap.add_argument('--baseline', required=True)
    ap.add_argument('--candidate', required=True)
    ap.add_argument('--mechanism', default='none', choices=('none', 'melds', 'gangs', 'pairs'))
    ap.add_argument('--min-rooms', type=int, default=MIN_ROOMS)
    a = ap.parse_args()
    # ★ R1458：本工具由**看护每 10 分钟自动跑**（读 150–250 份复盘，CPU 突发 1–3 分钟），
    #   而 R1182 实测『A/B 期间跑重活会抬高提交延迟、丢动作』⇒ 不降级会**既扰动正在判的数据、又实打实丢分**。
    #   故开跑前自我降到 BelowNormal（与 _campaign_status.py 同一机制；失败不阻塞）。
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from _lowprio_run import lower_self
        print('[gate2] %s' % lower_self())
    except Exception as _e:
        print('[gate2] 降级失败（继续跑）：%s' % str(_e)[:60])
    a.mechanism_key = (lambda: {'melds': 'melds', 'gangs': 'gangs',
                                'pairs': 'pair3'}.get(a.mechanism, 'melds'))
    idx = REP.room_index()
    led_a = AR.rooms_for(a.baseline, a.since)
    led_b = AR.rooms_for(a.candidate, a.since)
    print('=== 役：%s（基线） vs %s（候选）  since=%s' % (a.baseline, a.candidate, a.since))
    print('ledger 房数：%s=%d  %s=%d' % (a.baseline, len(led_a), a.candidate, len(led_b)))
    # replay metrics on the rooms that have replays
    def collect(rows):
        out = collections.defaultdict(list)
        n_rep = 0
        for r in rows:
            files = idx.get(r['room'])
            if not files:
                out['missing'].append(r['room'])
                continue
            rr = REP.room_rounds(files)
            R = len(rr)
            if R < 60:
                out['missing'].append(r['room'])
                continue
            n_rep += 1
            wins = sum(1 for v in rr.values() if v['my_win'])
            fan = sum(v['my_fan'] for v in rr.values())
            det = [x for v in rr.values() for x in (v.get('detail') or [])]
            out['hu_rate'].append(100.0 * wins / R)
            out['fan_rate'].append(100.0 * fan / R)
            out['melds'].append(sum(v['melds'] for v in rr.values()) / R * 100.0)
            out['gangs'].append(sum(v['ming'] + v['an'] + v['bu'] for v in rr.values()) / R * 100.0)
            out['baotou'].append(100.0 * sum(1 for x in det if '爆头' in str(x)) / R)
            pc = _pair_profile(files)
            out['pair_mean'].append(pc[0])
            out['pair3'].append(pc[1])
        out['n_rep'] = n_rep
        return out
    A, B = collect(led_a), collect(led_b)
    ca = A['n_rep'] / max(1, len(led_a))
    cb = B['n_rep'] / max(1, len(led_b))
    print('复盘覆盖：%s=%.1f%%（%d/%d）  %s=%.1f%%（%d/%d）' % (
        a.baseline, 100 * ca, A['n_rep'], len(led_a),
        a.candidate, 100 * cb, B['n_rep'], len(led_b)))
    verdict = []
    if len(A['hu_rate']) < a.min_rooms or len(B['hu_rate']) < a.min_rooms:
        verdict.append('房数不足（各需 >= %d 房有复盘）' % a.min_rooms)
    if min(ca, cb) < MIN_COVER:
        verdict.append('复盘覆盖 < %.0f%%（先补拉 tools/fetch_room_replays.py）' % (100 * MIN_COVER))
    print()
    print('%-18s %9s %9s %9s %8s %8s' % ('端点', '基线', '候选', '差', 'z', '判定'))
    rows = [('和牌率/房(主)', 'hu_rate'), ('番/房(副)', 'fan_rate'),
            ('副露/房(机制)', 'melds'), ('杠/房(机制)', 'gangs'), ('爆头/房(机制)', 'baotou'),
            ('平均对数(机制)', 'pair_mean'), ('>=3对占比(机制)', 'pair3')]
    res = {}
    for label, key in rows:
        d, se, z = _stats(A[key], B[key])
        res[key] = (d, z)
        tag = ''
        if key == 'hu_rate':
            tag = 'PASS' if z >= Z_CRIT else ('REJECT' if z <= -Z_CRIT else 'undecided')
        elif key == 'fan_rate':
            tag = 'PASS' if z >= Z_CRIT else ('REJECT' if z <= -Z_CRIT else 'undecided')
        elif a.mechanism != 'none' and key == a.mechanism_key():
            tag = 'PASS' if (z > 0 and res['hu_rate'][0] >= 0) else 'CHECK'
        print('%-18s %9.2f %9.2f %+9.2f %+8.2f %8s' % (
            label, statistics.mean(A[key]), statistics.mean(B[key]), d, z, tag))
    # ledger guardrails
    fr_a = 100.0 * sum(1 for r in led_a if r['rank'] == 1) / max(1, len(led_a))
    fr_b = 100.0 * sum(1 for r in led_b if r['rank'] == 1) / max(1, len(led_b))
    dnet, _, znet = _stats([r['net'] for r in led_a], [r['net'] for r in led_b])
    print()
    print('护栏：第一率 %s=%.1f%% vs %s=%.1f%%  %s' % (
        a.baseline, fr_a, a.candidate, fr_b, 'PASS' if fr_b >= fr_a else 'FAIL'))
    print('      净分/房（不作阻塞）差 %+.1f  z=%+.2f' % (dnet, znet))
    if fr_b < fr_a:
        verdict.append('第一率护栏未过（候选低于基线）')
    # mechanism
    if a.mechanism != 'none':
        key = a.mechanism_key()
        d, z = res[key]
        ok = (z > 0) and (res['hu_rate'][0] >= 0)
        print('机制核对（%s）：差 %+.2f  z=%+.2f  ⇒ %s' % (
            a.mechanism, d, z, 'PASS' if ok else 'FAIL（机制未同向或和牌率下降）'))
        if not ok:
            verdict.append('机制核对未过')
    # ★ R1522：把预登记的**熔断护栏**（campaign7 熔断行：`_breaker_watch` 两档不触发）放进判词取数里
    #   —— 此前只有人工跑 `_gate_report.py` 才能看到，而判词那一刻没有任何自动出口。
    try:
        _bp = subprocess.run([sys.executable, "-X", "utf8",
                              os.path.join(ROOT, "var", "_breaker_watch.py"),
                              "--since", a.since],
                             cwd=ROOT, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=600)
        _bl = [x for x in (_bp.stdout or "").strip().splitlines() if x.strip()][-6:]
        print('熔断护栏（_breaker_watch，rc=%s）：' % _bp.returncode)
        for _l in _bl:
            print('      ' + _l)
    except Exception as _e:
        print('熔断护栏（_breaker_watch）：不可得（%s）' % str(_e)[:60])
    print()
    if verdict:
        print('★ 判定：REFUSE / CONTINUE —— ' + '；'.join(verdict))
        return 3
    dh, zh = res['hu_rate']
    df, zf = res['fan_rate']
    if zh >= Z_CRIT and zf >= Z_CRIT and dh > 0 and df > 0:
        print('★ 判定：ADOPT %s（和牌率 z=%+.2f、番 z=%+.2f、护栏通过）' % (a.candidate, zh, zf))
        return 0
    if zh <= -Z_CRIT or zf <= -Z_CRIT:
        print('★ 判定：REJECT %s（和牌率 z=%+.2f、番 z=%+.2f）' % (a.candidate, zh, zf))
        return 1
    print('★ 判定：UNDECIDED（和牌率 z=%+.2f、番 z=%+.2f）⇒ 继续攒房' % (zh, zf))
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
