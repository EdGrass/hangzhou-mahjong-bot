"""ev_decomp.py —— 逐局期望值分解（我方 vs 榜单强手）。

关键口径（2026-09-16 实测确认）：
  一房 = M x Rounds 局。自动房 = 10 x 8 = **80 局**（auto_ranking 的 games_played=80、
  复盘每房 10 个 block 文件 x 8 局，两边一致）。正式赛 = 10 x 16 = **160 局/场**。
  => 分/房 = 分/局 x 80 ； 分/场 = 分/局 x 160。
  （早期文档里"分/房 = 分/局 x 8"是错的。）

赔付矩阵（实测，倍率 m in {1,2,4,8,16}）：
  庄家自摸：庄 +24m ，三个闲家各 -8m
  闲家自摸：闲 +10m ，庄 -8m ，另两个闲家各 -1m
  两者之和恒为 0；实测 25155 局无一例外。

自检：
  (1) 每局四家得分和 == 0
  (2) 我方在该房的逐局得分和 应 == auto_ranking.jsonl 的 total_score
"""
import json, glob, os, collections, statistics, argparse


def iter_files():
    for f in glob.glob('var/replays/*/*.json'):
        try:
            j = json.load(open(f, encoding='utf-8'))
        except Exception:
            continue
        if isinstance(j, dict) and len(j.get('seats') or []) == 4:
            yield os.path.basename(f).split('_r')[0], j


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--me', default='u_7a3fba48d70b')
    ap.add_argument('--min-rounds', type=int, default=300)
    ap.add_argument('--no-board', action='store_true')
    args = ap.parse_args()

    targets = {}
    if not args.no_board:
        import urllib.request, ssl
        ctx = ssl._create_unverified_context()
        cookie = open('var/.portal_cookie', encoding='utf-8-sig').read().strip()
        req = urllib.request.Request(
            '<平台地址>/portal/api/leaderboard?period=all',
            headers={'Cookie': cookie})
        d = json.loads(urllib.request.urlopen(req, timeout=25, context=ctx).read().decode('utf-8'))
        for p in d.get('top') or []:
            targets[p['user_id']] = p

    S = collections.defaultdict(lambda: [0] * 12)
    fan_sum = collections.Counter()
    our_room_pts = collections.defaultdict(float)
    nz = 0
    rooms_with_me = set()
    all_rooms = set()

    for room, j in iter_files():
        all_rooms.add(room)
        uids = [s.get('user_id') for s in j['seats']]
        if args.me in uids:
            rooms_with_me.add(room)
        for r in j.get('rounds') or []:
            if not isinstance(r, dict):
                continue
            sc = r.get('scores') or []
            w = r.get('winner'); dl = r.get('dealer'); m = r.get('multiplier') or 1
            if len(sc) != 4 or w is None or dl is None or not (0 <= w < 4 and 0 <= dl < 4):
                continue
            if sum(sc) != 0:
                nz += 1
            for i, uid in enumerate(uids):
                a = S[uid]; a[0] += 1
                is_d = (i == dl)
                a[2 if is_d else 4] += 1
                v = sc[i]
                if args.me == uid:
                    our_room_pts[room] += v
                if i == w:
                    a[1] += 1; a[6] += v; a[8 if is_d else 9] += v
                    a[3 if is_d else 5] += 1
                    fan_sum[uid] += m
                else:
                    a[7] += -v
                    if is_d or w == dl:
                        a[10] += -v
                    else:
                        a[11] += -v

    def row(uid):
        a = S[uid]; n = a[0]
        if n < args.min_rounds:
            return None
        return dict(uid=uid, n=n, hurate=a[1]/n, wd=a[3]/a[2] if a[2] else 0.0,
                    wn=a[5]/a[4] if a[4] else 0.0, dfrac=a[2]/n,
                    inc=a[6]/n, out=a[7]/n, net=(a[6]-a[7])/n,
                    inc_d=a[8]/n, inc_n=a[9]/n, out_d=a[10]/n, out_i=a[11]/n,
                    fan=fan_sum[uid]/a[1] if a[1] else 0.0)

    print('自检① 非零和局数 = %d（应为 0）' % nz)
    print('复盘覆盖房间 = %d，其中含我方 = %d' % (len(all_rooms), len(rooms_with_me)))
    # 自检②：与 auto_ranking 对照我方逐房得分
    rec = {}
    for line in open('var/auto_ranking.jsonl', encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        for p in d.get('ranking') or []:
            if p['user_id'] == args.me:
                rec[d['room']] = p.get('total_score', 0)
    both = [(r, our_room_pts[r], rec[r]) for r in rec if r in our_room_pts]
    if both:
        diff = [a - b for _, a, b in both]
        print('自检② 与 auto_ranking 逐房对照 n=%d，完全一致=%d，均值差=%+.2f' % (
            len(both), sum(1 for x in diff if abs(x) < 1e-9), statistics.mean(diff)))
    print()
    me = row(args.me)
    print('%-24s %6s %7s %7s %7s %7s %6s %9s %11s' % (
        'name', '局', '胡率', '庄胡率', '闲胡率', '庄占比', '番/胡', '分/局', '分/房(x80)'))
    print('%-24s %6d %6.1f%% %6.1f%% %6.1f%% %6.1f%% %6.2f %+9.3f %+11.1f' % (
        'EdGrass(我方)', me['n'], 100*me['hurate'], 100*me['wd'], 100*me['wn'],
        100*me['dfrac'], me['fan'], me['net'], 80*me['net']))
    print('    收入明细 庄胡 %+.3f + 闲胡 %+.3f = %+.3f /局' % (me['inc_d'], me['inc_n'], me['inc']))
    print('    支出明细 被庄胡 %+.3f + 被闲胡 %+.3f = %+.3f /局' % (-me['out_d'], -me['out_i'], -me['out']))
    if not args.no_board:
        rows = []
        for uid, p in targets.items():
            r = row(uid)
            if r:
                r['rank'] = p['rank']; r['name'] = p['name']
                r['board'] = p['score'] / (p['rooms'] or 1)
                rows.append(r)
        rows.sort(key=lambda r: r['rank'])
        print('-' * 120)
        for r in rows:
            print('%-2d %-21s %6d %6.1f%% %6.1f%% %6.1f%% %6.1f%% %6.2f %+9.3f %+11.1f  (榜单 %+8.1f)' % (
                r['rank'], r['name'][:20], r['n'], 100*r['hurate'], 100*r['wd'], 100*r['wn'],
                100*r['dfrac'], r['fan'], r['net'], 80*r['net'], r['board']))
        if rows:
            print()
            print('榜单强手均值(n=%d, >=%d局): 胡率 %.1f%%  庄胡率 %.1f%%  番/胡 %.2f  分/局 %+.3f  (=> %.1f 分/房)' % (
                len(rows), args.min_rounds, 100*statistics.mean(r['hurate'] for r in rows),
                100*statistics.mean(r['wd'] for r in rows), statistics.mean(r['fan'] for r in rows),
                statistics.mean(r['net'] for r in rows), 80*statistics.mean(r['net'] for r in rows)))


if __name__ == '__main__':
    main()
