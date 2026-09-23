"""ex_split.py —— 用**修正后的"前 8 巡"口径**（按局累计）重跑「听牌率 × 副露数 ex」分层。

重跑理由（§9.20）：`real_game_audit` 旧实现的 `turn` **每个 block 重置** ⇒ "前 8 巡"把一局后段
出牌也算进来，听牌率被高估 ~1.5 倍。§4c-45/§4c-63 的「听牌率差距几乎全部来自副露数分布」
与「同等副露下逐格相同」正是用旧口径得出的 ⇒ **必须重跑**。

口径：
  - 一局 = 从带 `start_hands` 的 block 到下个 `start_hands`；
  - `turn` = 该局内**自己第几次出牌**，只取 turn ≤ 8；
  - `ex` = 该次出牌时的副露数（面子 + 杠）；
  - `听牌率` = 出牌时向听 == 0 的比例。

用法：python -X utf8 tools/ex_split.py [--top 32] [--maxturn 8] [--limit N]
"""
from __future__ import annotations
import argparse, collections, glob, json, os, ssl, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from mahjong.shanten_exact import shanten as exact_shanten   # noqa: E402

ME = 'u_7a3fba48d70b'
MAXEX = 3


def board_top(n):
    ctx = ssl._create_unverified_context()
    cookie = open(os.path.join(ROOT, 'var', '.portal_cookie'), encoding='utf-8-sig').read().strip()
    req = urllib.request.Request('<平台地址>/portal/api/leaderboard?period=all',
                                 headers={'Cookie': cookie})
    d = json.loads(urllib.request.urlopen(req, timeout=25, context=ctx).read().decode('utf-8'))
    return [(p['rank'], p['user_id'], p['name']) for p in (d.get('top') or [])][:n]


def rounds_of(d):
    out, cur = [], None
    for b in d.get('blocks') or []:
        if not isinstance(b, dict):
            continue
        sh = b.get('start_hands')
        if sh and len(sh) == 4 and any(isinstance(x, (list, tuple)) for x in sh):
            if cur is not None:
                out.append(cur)
            cur = {'hands': [list(x) if isinstance(x, (list, tuple)) else [] for x in sh],
                   'nm': [0] * 4, 'ng': [0] * 4, 'turn': [0] * 4, 'events': []}
        if cur is not None:
            cur['events'].extend(b.get('events') or [])
    if cur is not None:
        out.append(cur)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--top', type=int, default=32)
    ap.add_argument('--maxturn', type=int, default=8)
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()
    board = board_top(args.top)
    strong = {u for _, u, _ in board}

    files = sorted(glob.glob(os.path.join(ROOT, 'var/replays/server/*.json'))) + \
            sorted(glob.glob(os.path.join(ROOT, 'var/replays/recent/*.json')))
    if args.limit:
        files = files[-args.limit:]

    # arm -> ex -> [disards, tenpai]
    T = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
    # arm -> [总出牌, 总听牌] 与 ex 分布
    tot = collections.defaultdict(lambda: [0, 0])

    for f in files:
        try:
            j = json.load(open(f, encoding='utf-8'))
        except Exception:
            continue
        if not isinstance(j, dict) or len(j.get('seats') or []) != 4:
            continue
        uids = [s.get('user_id') for s in j['seats']]
        arms = {}
        for i, u in enumerate(uids):
            if u == ME:
                arms[i] = 'me'
            elif u in strong:
                arms[i] = 'strong'
        if not arms:
            continue
        for cur in rounds_of(j):
            hands, nm, ng, turn = cur['hands'], cur['nm'], cur['ng'], cur['turn']
            for e in cur['events']:
                t, s = e.get('type'), e.get('seat')
                if t == 'round_ended':
                    hands = [[], [], [], []]; turn = [0] * 4
                    nm = [0] * 4; ng = [0] * 4
                    break
                if s is None or not (0 <= s < 4):
                    continue
                if t == 'tile_drawn':
                    hands[s].append(e.get('tile'))
                elif t == 'tile_discarded':
                    x = e.get('tile')
                    if x in hands[s]:
                        hands[s].remove(x)
                    else:
                        continue
                    turn[s] += 1
                    if s in arms and turn[s] <= args.maxturn:
                        ex = nm[s] + ng[s]
                        key = min(ex, MAXEX)
                        try:
                            shv = exact_shanten(list(hands[s]), qidui=(ex == 0),
                                                exposed_melds=nm[s] + ng[s], gangs=ng[s])
                        except Exception:
                            continue
                        a = arms[s]
                        T[a][key][0] += 1
                        tot[a][0] += 1
                        if shv == 0:
                            T[a][key][1] += 1
                            tot[a][1] += 1
                elif t == 'peng':
                    for _ in range(2):
                        if e.get('tile') in hands[s]:
                            hands[s].remove(e.get('tile'))
                    nm[s] += 1
                elif t == 'chi':
                    used = list((e.get('data') or {}).get('tiles') or [])
                    if e.get('tile') in used:
                        used.remove(e.get('tile'))
                    for x in used:
                        if x in hands[s]:
                            hands[s].remove(x)
                    nm[s] += 1
                elif t == 'gang':
                    kind = (e.get('data') or {}).get('kind')
                    if kind == 'bu':
                        if e.get('tile') in hands[s]:
                            hands[s].remove(e.get('tile'))
                        nm[s] -= 1; ng[s] += 1
                    else:
                        for _ in range(4 if kind == 'an' else 3):
                            if e.get('tile') in hands[s]:
                                hands[s].remove(e.get('tile'))
                        ng[s] += 1

    print('=' * 92)
    print('「听牌率 × 副露数 ex」——**修正口径**（按局累计 turn，前 %d 巡）' % args.maxturn)
    print('=' * 92)
    hdr = '%-16s %9s' % ('', '总计')
    for ex in range(MAXEX + 1):
        hdr += ' %14s' % ('ex=%d' % ex if ex < MAXEX else 'ex>=%d' % MAXEX)
    print(hdr)
    for arm, lbl in (('me', 'EdGrass(我方)'), ('strong', '榜单 top%d' % args.top)):
        line = '%-16s %5d %4.1f%%' % (lbl, tot[arm][0], 100 * tot[arm][1] / max(1, tot[arm][0]))
        for ex in range(MAXEX + 1):
            n, k = T[arm][ex]
            line += ' %6d %6.1f%%' % (n, 100 * k / max(1, n))
        print(line)
    print()
    print('--- 同上，但每格显示「占该玩家全部出牌的比例 / 该格听牌率」 ---')
    for arm, lbl in (('me', 'EdGrass(我方)'), ('strong', '榜单 top%d' % args.top)):
        line = '%-16s' % lbl
        for ex in range(MAXEX + 1):
            n, k = T[arm][ex]
            line += '  %5.1f%% / %5.1f%%' % (100 * n / max(1, tot[arm][0]), 100 * k / max(1, n))
        print(line)
    print()
    print('⇒ 复核 §4c-63 的说法：① 我方 ex 分布是否比强手更偏 ex=0？')
    for arm, lbl in (('me', '我方'), ('strong', '强手')):
        n0 = T[arm][0][0]
        print('   %s: ex=0 占比 %.1f%%' % (lbl, 100 * n0 / max(1, tot[arm][0])))
    print('⇒ ② 同等 ex 下听牌率是否逐格相同？（同 ex 上两行之差）')
    for ex in range(MAXEX + 1):
        n_m, k_m = T['me'][ex]; n_s, k_s = T['strong'][ex]
        if n_m and n_s:
            print('   ex=%d: 我方 %.1f%% vs 强手 %.1f%%  ⇒ %+.1fpp' % (
                ex, 100 * k_m / n_m, 100 * k_s / n_s,
                100 * (k_m / n_m - k_s / n_s)))


if __name__ == '__main__':
    main()
