"""dealer_split.py —— 把真机指标按【庄 / 闲】拆开：我方 vs 榜单强手。

口径与 `real_game_audit.py` 一致：`start_hands` **每局只出现一次**，其后的 block 属于同一局
（`_rounds_of` 把连续 block 串成一局），逐局处置手牌后：
  - `听牌率` = 前 8 巡里向听 0 的比例；`张|听` = 听牌时平均听牌张数；`爆头|听` = 听牌态里爆头比例；
  - 另加 `胡率`（该角色下的胜率）与 `副露/局`。
全部按"**该局庄家是否是该玩家**"分桶。

用法：python -X utf8 tools/dealer_split.py [--limit N] [--top 32] [--maxturn 8]
"""
from __future__ import annotations
import argparse, collections, glob, json, os, ssl, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from mahjong.shanten import waits                          # noqa: E402
from mahjong.shanten_exact import shanten as exact_shanten   # noqa: E402
from mahjong.hu import is_baotou                            # noqa: E402

ME = 'u_7a3fba48d70b'


def board_top(n):
    ctx = ssl._create_unverified_context()
    cookie = open(os.path.join(ROOT, 'var', '.portal_cookie'), encoding='utf-8-sig').read().strip()
    req = urllib.request.Request('<平台地址>/portal/api/leaderboard?period=all',
                                 headers={'Cookie': cookie})
    d = json.loads(urllib.request.urlopen(req, timeout=25, context=ctx).read().decode('utf-8'))
    return [(p['rank'], p['user_id'], p['name']) for p in (d.get('top') or [])][:n]


def rounds_of(d):
    """按【局】分组：一局 = 从带 start_hands 的 block 开始，到下一个 start_hands 前的所有 block。

    ⚠ 这与 `real_game_audit._rounds_of` 不同：那个函数**每个 block 返回一项**，
    于是它的 `turn` 是"按 block 重置"的（§9.19/9.20）。本工具按局累计 `turn`。
    """
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
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--top', type=int, default=32)
    ap.add_argument('--maxturn', type=int, default=8)
    args = ap.parse_args()
    board = board_top(args.top)
    strong = {u for _, u, _ in board}

    files = sorted(glob.glob(os.path.join(ROOT, 'var/replays/server/*.json'))) + \
            sorted(glob.glob(os.path.join(ROOT, 'var/replays/recent/*.json')))
    if args.limit:
        files = files[-args.limit:]

    B = collections.defaultdict(lambda: [0] * 10)  # turns,tenpai,wsum,baotou,melds,rounds,wins,bad,tp_rounds,tp_wins
    nfile = 0
    for f in files:
        try:
            j = json.load(open(f, encoding='utf-8'))
        except Exception:
            continue
        if not isinstance(j, dict) or len(j.get('seats') or []) != 4:
            continue
        uids = [s.get('user_id') for s in j['seats']]
        if ME not in uids and not any(u in strong for u in uids):
            continue
        nfile += 1
        R = [r for r in (j.get('rounds') or []) if isinstance(r, dict)]
        groups = rounds_of(j)
        for gi, cur in enumerate(groups):
            if gi >= len(R):
                break
            events = cur['events']
            dl = R[gi].get('dealer')
            if dl is None or not (0 <= dl < 4):
                continue
            tracked = [i for i, u in enumerate(uids) if u == ME or u in strong]
            tp_players = set()
            for i in tracked:
                B[('dl' if i == dl else 'id', uids[i])][5] += 1
                if R[gi].get('winner') == i:
                    B[('dl' if i == dl else 'id', uids[i])][6] += 1
            hands, nm, ng, turn = cur['hands'], cur['nm'], cur['ng'], cur['turn']
            for e in events:
                t, s = e.get('type'), e.get('seat')
                if t == 'round_ended':
                    for i in tracked:
                        if i in tp_players:
                            k = ('dl' if i == dl else 'id', uids[i])
                            B[k][8] += 1
                            if R[gi].get('winner') == i:
                                B[k][9] += 1
                    hands = [[], [], [], []]
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
                    if s in tracked and turn[s] <= args.maxturn:
                        ex, gg = nm[s] + ng[s], ng[s]
                        try:
                            shv = exact_shanten(list(hands[s]), qidui=(ex == 0 and gg == 0),
                                                exposed_melds=ex, gangs=gg)
                        except Exception:
                            continue
                        a = B[('dl' if s == dl else 'id', uids[s])]
                        a[0] += 1
                        if shv == 0:
                            a[1] += 1
                            tp_players.add(s)
                            try:
                                a[2] += len(waits(list(hands[s]), exposed_melds=ex, gangs=gg))
                                if is_baotou(list(hands[s]), allow_qidui=(ex == 0 and gg == 0),
                                             exposed_melds=ex, gangs=gg):
                                    a[3] += 1
                            except Exception:
                                pass
                elif t in ('chi', 'peng', 'gang'):
                    if s in tracked:
                        B[('dl' if s == dl else 'id', uids[s])][4] += 1
                    if t == 'chi':
                        used = list((e.get('data') or {}).get('tiles') or [])
                        if e.get('tile') in used:
                            used.remove(e.get('tile'))
                        for x in used:
                            if x in hands[s]:
                                hands[s].remove(x)
                    elif t == 'peng':
                        for _ in range(2):
                            if e.get('tile') in hands[s]:
                                hands[s].remove(e.get('tile'))
                    else:
                        for _ in range(3):
                            if e.get('tile') in hands[s]:
                                hands[s].remove(e.get('tile'))

    def merge(role, uids):
        v = [0] * 10
        for u in uids:
            a = B.get((role, u))
            if a:
                for i in range(10):
                    v[i] += a[i]
        return v

    def show(label, v):
        if v[0] == 0:
            print('%-20s （无样本）' % label)
            return
        tp = v[1] / v[0]
        print('%-20s %7d %8.1f%% %8.1f%% %8.2f %8.1f%% %8.3f %10.1f%%' % (
            label, v[5], 100 * v[6] / max(1, v[5]), 100 * tp,
            (v[2] / v[1]) if v[1] else 0, 100 * v[3] / v[1] if v[1] else 0,
            v[4] / max(1, v[5]), 100 * v[9] / v[8] if v[8] else 0))

    print('=' * 100)
    print('庄/闲 分桶（语料 %d 文件，前 %d 巡；口径同 real_game_audit）' % (nfile, args.maxturn))
    print('=' * 100)
    print('%-20s %7s %8s %8s %8s %8s %8s %10s' % ('', '局数', '胡率', '听牌率', '张|听', '爆头|听', '副露/局', '兑现率'))
    show('我方 · 当庄', merge('dl', [ME]))
    show('我方 · 当闲', merge('id', [ME]))
    print('-' * 100)
    show('强手 · 当庄', merge('dl', strong))
    show('强手 · 当闲', merge('id', strong))
    print()
    for lbl, uids in (('我方', [ME]), ('强手', strong)):
        d = merge('dl', uids); i = merge('id', uids)
        if d[0] and i[0]:
            print('%s：胡率 庄-闲 %+.2fpp ；听牌率 庄-闲 %+.2fpp ；副露/局 庄-闲 %+.3f' % (
                lbl,
                100 * (d[6] / d[5] - i[6] / i[5]) if d[5] and i[5] else 0,
                100 * (d[1] / d[0] - i[1] / i[0]),
                d[4] / max(1, d[5]) - i[4] / max(1, i[5])))


if __name__ == '__main__':
    main()
