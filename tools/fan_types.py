# 番种分布：我方胡牌 vs 榜单强手胡牌（用 round_ended.data.detail + fan）
import json, glob, collections, ssl, urllib.request
ME = 'u_7a3fba48d70b'
ctx = ssl._create_unverified_context()
cookie = open('var/.portal_cookie', encoding='utf-8-sig').read().strip()
req = urllib.request.Request('https://10.240.169.190:18080/portal/api/leaderboard?period=all',
                             headers={'Cookie': cookie})
d = json.loads(urllib.request.urlopen(req, timeout=25, context=ctx).read().decode('utf-8'))
board = [(p['rank'], p['user_id'], p['name']) for p in d['top']]
tm = {u: r for r, u, n in board}

A = collections.defaultdict(lambda: [0, 0, 0])          # arm -> [胡数, 番和, m>=2]
D = collections.defaultdict(collections.Counter)        # arm -> detail 组合 -> 次数
D2 = collections.defaultdict(collections.Counter)       # arm -> 单个番种 -> 次数
fanby = collections.defaultdict(collections.Counter)    # arm -> fan -> 次数
nfile = 0
for f in glob.glob('var/replays/*/*.json'):
    try: j = json.load(open(f, encoding='utf-8'))
    except Exception: continue
    if not isinstance(j, dict) or len(j.get('seats') or []) != 4: continue
    uids = [s.get('user_id') for s in j['seats']]
    arms = {}
    for i, u in enumerate(uids):
        if u == ME: arms[i] = 'me'
        elif u in tm: arms[i] = 'strong'
    if not arms: continue
    nfile += 1
    for b in j.get('blocks') or []:
        if not isinstance(b, dict): continue
        for e in b.get('events') or []:
            if e.get('type') != 'round_ended': continue
            s = e.get('seat'); data = e.get('data') or {}
            if s not in arms or data.get('draw'): continue
            arm = arms[s]
            fan = data.get('fan') or 1
            det = tuple(data.get('detail') or [])
            a = A[arm]; a[0] += 1; a[1] += fan
            if fan >= 2: a[2] += 1
            D[arm][det] += 1
            for x in set(det): D2[arm][x] += 1
            fanby[arm][fan] += 1

def show(arm, lbl):
    a = A[arm]
    if not a[0]: return
    print('%-14s 胡数 %5d   番/胡 %.3f   番>=2 占比 %.1f%%' % (lbl, a[0], a[1]/a[0], 100*a[2]/a[0]))
print('=' * 96)
print('番种分布（真机语料 %d 文件）' % nfile)
print('=' * 96)
show('me', 'EdGrass(我方)')
show('strong', '榜单 top32 合计')
print()
print('--- 番数分布 ---')
print('%-6s %10s %10s %10s' % ('番', '我方占比', '强手占比', '差'))
tot_m = A['me'][0]; tot_s = A['strong'][0]
for fan in sorted(set(list(fanby['me']) + list(fanby['strong']))):
    pm = 100*fanby['me'][fan]/max(1,tot_m); ps = 100*fanby['strong'][fan]/max(1,tot_s)
    print('%-6d %9.1f%% %9.1f%% %+9.1fpp' % (fan, pm, ps, pm-ps))
print()
print('--- 单个番种出现率（占各家胡牌数）前 20（按强手排序）---')
print('%-22s %10s %10s %10s' % ('番种', '我方', '强手', '差'))
rows = sorted(D2['strong'].items(), key=lambda kv: -kv[1])[:20]
for name, cnt in rows:
    pm = 100*D2['me'][name]/max(1,tot_m); ps = 100*cnt/max(1,tot_s)
    print('%-22s %9.1f%% %9.1f%% %+9.1fpp' % (name[:20], pm, ps, pm-ps))
print()
print('--- "平胡单独胡"（detail 只有 平胡）比例 ---')
ph_m = sum(c for k, c in D['me'].items() if list(k) == ['平胡'])
ph_s = sum(c for k, c in D['strong'].items() if list(k) == ['平胡'])
print('  我方 %.1f%%  强手 %.1f%%  ⇒ %+.1fpp' % (100*ph_m/max(1,tot_m), 100*ph_s/max(1,tot_s), 100*(ph_m/max(1,tot_m)-ph_s/max(1,tot_s))))
