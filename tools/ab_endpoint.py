"""ab_endpoint.py —— 按 A/B 臂读**机制端点**（**本地录制，零门户延迟**）。

数据源：`var/replays/auto_<stamp>/<gid>.jsonl`（`replay_rec` 落的**本地事件流**，含
`round_ended.data.fan/detail/scores`）+ `var/auto_ranking.jsonl`（room → strategy 权威归属）。
⇒ 不必等门户发布（门户有数小时延迟，会让"16 房/臂筛选"看起来没数据）。

端点：**爆头占胡**（番差全在爆头；2σ 辨 +4.8pp ≈ 16 房/臂）、胡率、番/胡、净胜/房。
筛选段判"机制是否生效"看**该候选自己声称的端点**（不是一律看分数）。

用法：python -X utf8 tools/ab_endpoint.py
"""
from __future__ import annotations
import collections, glob, json, math, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    since = None
    arms = None
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
            rmap[d['room']] = (d.get('strategy') or '?', d.get('ts') or '', d.get('ranking') or [])

    S = collections.defaultdict(lambda: [0, 0, 0, 0])      # 局, 赢, 番和, 爆头胡
    R = collections.defaultdict(lambda: [0, 0])            # 房, 净分
    seen_rooms = collections.Counter()
    for f in glob.glob(os.path.join(ROOT, 'var', 'replays', 'auto_*', '*.jsonl')):
        base = os.path.basename(f)
        if base.endswith('.dec.jsonl'):
            continue
        room = base.split('_r')[0]
        info = rmap.get(room)
        if not info:
            continue
        stg, ts, ranking = info
        if since and ts < since:
            continue
        if arms and stg not in arms:
            continue
        if seen_rooms[room] == 0:
            seen_rooms[room] = 1
            R[stg][0] += 1
            for p in ranking:
                if (p.get('user_id') or '') == 'u_7a3fba48d70b':
                    R[stg][1] += p.get('total_score', 0) + p.get('place_points', 0)
        try:
            for ln2 in open(f, encoding='utf-8'):
                ln2 = ln2.strip()
                if not ln2:
                    continue
                try:
                    e = json.loads(ln2)
                except Exception:
                    continue
                if e.get('type') != 'round_ended':
                    continue
                data = e.get('data') or {}
                a = S[stg]
                a[0] += 1
                # 只统计"我方胡"：需要 seat→我方；本地事件流没有 seats，改用 detail 无法判定归属
                # ⇒ 用 scores 的符号模式近似不可靠，故这里统计**全场**，并在下方按臂对比（同池同对手）
                a[1] += 1
                a[2] += data.get('fan') or 1
                if '爆头' in (data.get('detail') or []):
                    a[3] += 1
        except Exception:
            continue

    print('=' * 92)
    print('A/B 机制端点（**本地录制**）   since=%s   arms=%s' % (since, sorted(arms) if arms else '-'))
    print('=' * 92)
    if not S:
        print('本地 auto_* 里没有窗口内的战役房。')
        return
    print('%-14s %5s %7s %9s %10s %10s' % ('arm', '房', '局', '覆盖率', '全场爆头占胡', '净胜/房'))
    for stg in sorted(S):
        a = S[stg]
        n = a[0]; bo = a[3] / max(1, n)
        se = math.sqrt(bo * (1 - bo) / max(1, n))
        net = R[stg][1] / max(1, R[stg][0])
        expect = R[stg][0] * 80.0          # 一房 = M x Rounds = 10 x 8 = 80 局
        print('%-14s %5d %7d %8.0f%% %9.2f%% %+10.1f' % (
            stg, R[stg][0], n, 100.0 * n / max(1.0, expect), 100 * bo, net))
        print('%-14s %5s %7s %8s %9.3f%%' % ('  ±SE(1σ)', '', '', '', 100 * se))
    print()
    print('⚠ 覆盖率 = 本工具从**本地事件流**数到的 round_ended / (房数 x 80)。')
    print('   实测本地录制只捕获**一房约 39~45 个 round_ended（≈50~60%）** ⇒ 爆头占胡是**子集口径**。')
    print('   ⇒ 只用于**两臂同口径的相对比较**；要**绝对水平**或做最终判定，请用门户语料 `tools/fan_types.py`')
    print('     （有 seats、数据完整，但有数小时发布延迟）。两臂覆盖率若差得多，需谨慎。')
    print()
    print('注：本工具统计的是**全场**爆头占胡（本地事件流没有 seats，无法只挑我方）；')
    print('    因为两臂在**同一池、同时段、轮转**，全场口径的臂间差仍可用于筛选。')
    print('    若要"只算我方"，需用门户语料（`tools/fan_types.py`，有 seats，但有数小时发布延迟）。')


if __name__ == '__main__':
    main()
