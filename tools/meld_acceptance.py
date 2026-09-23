"""meld_acceptance.py —— 吃碰"有资格 vs 接受"的窗口层审计（同房对照）。

回答的问题：我方副露率只有榜单强手的 ~70%（0.106 vs 0.156 副露/巡）——
是**没被 offer**（手形结构），还是**拒得太多**（门控）？

做法（不依赖策略、不需要算向听，因此很快）：
  `var/replays/*/*.json` 的 `blocks[i].start_hands` 是**精确初始手牌**，从它出发按事件流重建四家手牌：
    - `tile_drawn`    → 手牌 +1
    - `tile_discarded`→ 手牌 -1；同时对**其他三家**判定资格：
                        碰：手里有 ≥2 张同一张牌；吃：仅下家有该牌的两面/嵌张/边张搭子
    - `chi/peng/gang` → 从手牌扣除相应牌
  统计每人的「有资格窗口数」与「接受数」⇒ **接受率**（= 条件概率，跨人可比）。

用法：
    python -X utf8 tools/meld_acceptance.py                # 我方 vs 榜单 top32
    python -X utf8 tools/meld_acceptance.py --top 8        # 只看前 8
    python -X utf8 tools/meld_acceptance.py --by-day       # 按日期分层（看趋势）

⚠ 边界：只统计带 `start_hands` 的 block（部分 block 缺）；两侧用**同一批 block**，所以
   **接受率的比较是公平的**，但绝对接受数会**低估**总副露（另见：摸牌后暗杠/补杠不走窗口）。
"""
from __future__ import annotations
import argparse, collections, glob, json, os, ssl, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ME = 'u_7a3fba48d70b'


def tile_parts(t):
    if not t:
        return (None, None)
    if t[-1] in 'wbt':
        try:
            return (t[-1], int(t[:-1]))
        except ValueError:
            return ('h', t)
    return ('h', t)


def chi_options(hand, x):
    suit, num = tile_parts(x)
    if suit is None or suit == 'h':
        return 0
    n = 0
    for a, b in ((num - 2, num - 1), (num - 1, num + 1), (num + 1, num + 2)):
        if 1 <= a <= 9 and 1 <= b <= 9:
            if ('%d%s' % (a, suit)) in hand and ('%d%s' % (b, suit)) in hand:
                n += 1
    return n


def board_top(limit):
    ctx = ssl._create_unverified_context()
    cookie = open(os.path.join(ROOT, 'var', '.portal_cookie'), encoding='utf-8-sig').read().strip()
    req = urllib.request.Request(
        '<平台地址>/portal/api/leaderboard?period=all',
        headers={'Cookie': cookie})
    d = json.loads(urllib.request.urlopen(req, timeout=25, context=ctx).read().decode('utf-8'))
    return [(p['rank'], p['user_id'], p['name']) for p in (d.get('top') or [])][:limit]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--top', type=int, default=32)
    ap.add_argument('--by-day', action='store_true')
    ap.add_argument('--me', default=ME)
    args = ap.parse_args()

    board = board_top(args.top)
    tmap = {u: (r, n) for r, u, n in board}

    rdate = {}
    for line in open(os.path.join(ROOT, 'var', 'auto_ranking.jsonl'), encoding='utf-8'):
        line = line.strip()
        if line:
            r = json.loads(line)
            rdate[r['room']] = r['ts'][:10]

    E = collections.Counter(); A = collections.Counter()          # 总
    EP = collections.Counter(); AP = collections.Counter()        # 碰
    EC = collections.Counter(); AC = collections.Counter()        # 吃
    blocks_used = 0; blocks_skipped = 0
    byday = collections.defaultdict(lambda: [0, 0, 0, 0])         # day -> [我们E,我们A,强手E,强手A]

    for f in glob.glob(os.path.join(ROOT, 'var', 'replays', '*', '*.json')):
        try:
            j = json.load(open(f, encoding='utf-8'))
        except Exception:
            continue
        if not isinstance(j, dict) or len(j.get('seats') or []) != 4:
            continue
        room = os.path.basename(f).split('_r')[0]
        day = rdate.get(room, '?')
        uids = [s.get('user_id') for s in j['seats']]
        for b in j.get('blocks') or []:
            if not isinstance(b, dict):
                continue
            sh = b.get('start_hands')
            if not sh or len(sh) != 4 or any(not isinstance(h, list) for h in sh):
                blocks_skipped += 1
                continue
            blocks_used += 1
            hands = [list(h) for h in sh]
            pending = None
            for e in b.get('events') or []:
                t = e.get('type'); s = e.get('seat')
                if t == 'round_ended':
                    pending = None
                    continue
                if s is None or not (0 <= s < 4):
                    continue
                if t == 'tile_drawn':
                    hands[s].append(e.get('tile'))
                elif t == 'tile_discarded':
                    x = e.get('tile')
                    if x in hands[s]:
                        hands[s].remove(x)
                    for i in range(4):
                        if i == s:
                            continue
                        uid = uids[i]
                        pe = hands[i].count(x) >= 2
                        ce = (i == (s + 1) % 4) and chi_options(hands[i], x) > 0
                        if pe:
                            E[uid] += 1; EP[uid] += 1
                        if ce:
                            E[uid] += 1; EC[uid] += 1
                        if uid == args.me:
                            byday[day][0] += (1 if pe else 0) + (1 if ce else 0)
                        elif uid in tmap:
                            byday[day][2] += (1 if pe else 0) + (1 if ce else 0)
                    pending = (s, x)
                elif t in ('chi', 'peng', 'gang'):
                    uid = uids[s]
                    data = e.get('data') or {}
                    tile = e.get('tile')
                    if t == 'chi':
                        # data['tiles'] 是**含被吃那张**的 3 张组合；被吃的那张来自河里，不该从手牌扣
                        used_offer = False
                        for tl in data.get('tiles') or []:
                            if tl == tile and not used_offer:
                                used_offer = True
                                continue
                            if tl in hands[s]:
                                hands[s].remove(tl)
                        AC[uid] += 1
                    elif t == 'peng':
                        for _ in range(2):
                            if tile in hands[s]:
                                hands[s].remove(tile)
                        AP[uid] += 1
                    else:
                        # ⚠ 2026-09-17 修正：原来一律扣 3 张且用 pending（河里那张）——
                        # 补杠(bu) 的那张来自**自己摸牌**且只该扣 1；暗杠(an) 扣 4。旧写法会让手牌
                        # 从此刻起持续漂移（实测弃牌前长度保真度只有 82.1%），把 E（有资格）算歪。
                        kind = str(data.get('kind') or 'ming')
                        n = {'an': 4, 'bu': 1}.get(kind, 3)
                        for _ in range(n):
                            if tile in hands[s]:
                                hands[s].remove(tile)
                        AP[uid] += 1
                    A[uid] += 1
                    if uid == args.me:
                        byday[day][1] += 1
                    elif uid in tmap:
                        byday[day][3] += 1

    def pct(a, b):
        return (100.0 * a / b) if b else 0.0

    print('=' * 84)
    print('吃碰「有资格 vs 接受」审计    block 使用 %d / 跳过 %d' % (blocks_used, blocks_skipped))
    print('=' * 84)
    print('%-24s %10s %10s %10s %10s %10s' % ('', '有资格', '接受', '接受率', '碰接受率', '吃接受率'))
    print('%-24s %10d %10d %9.1f%% %9.1f%% %9.1f%%' % (
        'EdGrass(我方)', E[args.me], A[args.me], pct(A[args.me], E[args.me]),
        pct(AP[args.me], EP[args.me]), pct(AC[args.me], EC[args.me])))
    se = sa = sep = sap = sec = sac = 0
    for r, u, n in board:
        if E[u] < 100:
            continue
        se += E[u]; sa += A[u]; sep += EP[u]; sap += AP[u]; sec += EC[u]; sac += AC[u]
    if args.by_day:
        print()
        print('%-12s %9s %9s %9s %9s' % ('日期', '我方接受率', '强手接受率', '我方有资格', '强手有资格'))
        for day in sorted(d for d in byday if d != '?'):
            me_e, me_a, st_e, st_a = byday[day]
            if me_e < 200:
                continue
            print('%-12s %8.1f%% %9.1f%% %9d %9d' % (
                day, pct(me_a, me_e), pct(st_a, st_e), me_e, st_e))
    print()
    print('榜单 top%d 合计：有资格 %d，接受 %d ⇒ 接受率 %.1f%%' % (args.top, se, sa, pct(sa, se)))
    print('我方            ：有资格 %d，接受 %d ⇒ 接受率 %.1f%%' % (E[args.me], A[args.me], pct(A[args.me], E[args.me])))
    print('⇒ 接受率差 %+.1fpp（碰 %+.1fpp / 吃 %+.1fpp）' % (
        pct(A[args.me], E[args.me]) - pct(sa, se),
        pct(AP[args.me], EP[args.me]) - pct(sap, sep),
        pct(AC[args.me], EC[args.me]) - pct(sac, sec)))
    if se:
        extra = E[args.me] * (sa / se - (A[args.me] / E[args.me]) if E[args.me] else 0)
        print('⇒ 若我方接受率追平强手：多接受 %.0f 次（该审计覆盖范围内）' % extra)


if __name__ == '__main__':
    main()
