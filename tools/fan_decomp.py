"""fan_decomp.py —— 番/胡（= 我方胡牌的平均倍率 m∈{1,2,4,8,16}）的分布分解：我方 vs 榜单强手。

为什么：§9.13 把残差定位为「番/胡 1.29 → 1.36」+「庄位」，本工具回答**这 0.07 从哪来**：
  - 是 m=1（小胡）占比太高，还是 m>=2（爆头/大牌）占比太低？
  - 庄/闲分开看是否一致？
  - 同时看我方「付给别人的倍率分布」——别人胡我们的牌是否更大（= 我们送分更多）？

用法：python -X utf8 tools/fan_decomp.py [--top 32] [--by-day]
"""
from __future__ import annotations
import argparse, collections, glob, json, os, ssl, statistics, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ME = 'u_7a3fba48d70b'


def board_top(n):
    ctx = ssl._create_unverified_context()
    cookie = open(os.path.join(ROOT, 'var', '.portal_cookie'), encoding='utf-8-sig').read().strip()
    req = urllib.request.Request('<平台地址>/portal/api/leaderboard?period=all',
                                 headers={'Cookie': cookie})
    d = json.loads(urllib.request.urlopen(req, timeout=25, context=ctx).read().decode('utf-8'))
    return [(p['rank'], p['user_id'], p['name'], p['rooms'], p['score']) for p in (d.get('top') or [])][:n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--top', type=int, default=32)
    ap.add_argument('--by-day', action='store_true')
    args = ap.parse_args()
    board = board_top(args.top)
    tmap = {u: r for r, u, n, rm, sc in board}

    rdate = {}
    for line in open(os.path.join(ROOT, 'var', 'auto_ranking.jsonl'), encoding='utf-8'):
        line = line.strip()
        if line:
            r = json.loads(line)
            rdate[r['room']] = r['ts'][:10]

    # uid -> [胡数, 倍率和, 庄胡数, 庄倍率和, 闲胡数, 闲倍率和, m>=2 数, m>=4 数, 局数, 被胡次数, 被胡倍率和]
    S = collections.defaultdict(lambda: [0] * 11)
    day = collections.defaultdict(lambda: [0, 0, 0])   # day -> [我们胡, 我们倍率和, 我们局]

    for f in glob.glob(os.path.join(ROOT, 'var', 'replays', '*', '*.json')):
        try:
            j = json.load(open(f, encoding='utf-8'))
        except Exception:
            continue
        if not isinstance(j, dict) or len(j.get('seats') or []) != 4:
            continue
        room = os.path.basename(f).split('_r')[0]
        d = rdate.get(room, '?')
        uids = [s.get('user_id') for s in j['seats']]
        for r in j.get('rounds') or []:
            if not isinstance(r, dict):
                continue
            sc = r.get('scores') or []; w = r.get('winner'); dl = r.get('dealer')
            m = r.get('multiplier') or 1
            if len(sc) != 4 or w is None or dl is None or not (0 <= w < 4):
                continue
            for i, u in enumerate(uids):
                a = S[u]; a[8] += 1
                if i == w:
                    a[0] += 1; a[1] += m
                    if i == dl: a[2] += 1; a[3] += m
                    else: a[4] += 1; a[5] += m
                    if m >= 2: a[6] += 1
                    if m >= 4: a[7] += 1
                    if u == ME:
                        day[d][0] += 1; day[d][1] += m; day[d][2] += 1
                else:
                    a[9] += 1; a[10] += m

    def line(label, a, rooms=None, score=None):
        w = a[0] or 1
        extra = ''
        if rooms:
            extra = '  榜单%+7.1f 分/房' % (score / rooms)
        print('%-22s %7d %8.3f %7.1f%% %7.1f%% %8.3f %8.3f%s' % (
            label[:20], a[0], a[1] / w,
            100 * a[6] / w, 100 * a[7] / w,
            a[3] / (a[2] or 1), a[5] / (a[4] or 1), extra))

    print('=' * 108)
    print('番/胡（胡牌平均倍率）分布分解    我方 vs 榜单 top%d' % args.top)
    print('=' * 108)
    print('%-22s %7s %8s %8s %8s %8s %8s' % ('', '胡数', '番/胡', 'm>=2', 'm>=4', '庄胡番', '闲胡番'))
    line('EdGrass(我方)', S[ME])
    ae = collections.Counter(); aw = collections.Counter()
    tot_w = tot_sum = 0
    for r, u, n, rm, sc in board:
        a = S[u]
        if a[0] < 40:
            continue
        tot_w += a[0]; tot_sum += a[1]
        ae['w'] += a[0]; ae['sum'] += a[1]; ae['d'] += a[2]; ae['ds'] += a[3]
        ae['n'] += a[4]; ae['ns'] += a[5]; ae['g2'] += a[6]; ae['g4'] += a[7]
    if tot_w:
        print('%-22s %7d %8.3f %7.1f%% %7.1f%% %8.3f %8.3f' % (
            '榜单 top%d 合计' % args.top, tot_w, tot_sum / tot_w,
            100 * ae['g2'] / tot_w, 100 * ae['g4'] / tot_w,
            ae['ds'] / (ae['d'] or 1), ae['ns'] / (ae['n'] or 1)))
    print()
    print('--- 逐强手（胡数 >= 40）---')
    print('%-5s %-18s %7s %8s %8s %8s' % ('rank', 'name', '胡数', '番/胡', 'm>=2', '榜单分/房'))
    for r, u, n, rm, sc in board:
        a = S[u]
        if a[0] < 40:
            continue
        print('%-5d %-18s %7d %8.3f %7.1f%% %+9.1f%s' % (
            r, n[:16], a[0], a[1] / a[0], 100 * a[6] / a[0], sc / (rm or 1), '   <= 我方' if False else ''))
    print()
    print('--- 付给别人的倍率（我们被胡时对手的番）---')
    print('%-22s %9s %10s' % ('', '被胡次数', '对手番/胡'))
    a = S[ME]
    print('%-22s %9d %10.3f' % ('EdGrass(我方)', a[9], a[10] / (a[9] or 1)))
    g = collections.Counter()
    for r, u, n, rm, sc in board:
        b = S[u]
        if b[0] >= 40:
            g['n'] += b[9]; g['s'] += b[10]
    if g['n']:
        print('%-22s %9d %10.3f' % ('榜单 top%d 合计' % args.top, g['n'], g['s'] / g['n']))
    if args.by_day:
        print()
        print('%-12s %8s %9s %8s' % ('日期', '胡数', '番/胡', '局数'))
        for d in sorted(x for x in day if x != '?'):
            h, hs, n = day[d]
            if n < 300:
                continue
            print('%-12s %8d %9.3f %8d' % (d, h, hs / (h or 1), n))


if __name__ == '__main__':
    main()
