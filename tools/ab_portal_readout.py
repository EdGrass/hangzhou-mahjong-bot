"""ab_portal_readout.py —— **门户口径**的逐臂"我方自己"终点读数（终判用）。

为什么需要（§10.3/§9.53）：
- 主判据 `ab_readout.py` 是**净胜/房**（按 user_id 归因，可靠），但它不回答"机制层（爆头/胡率）动了没有"；
- 机制层的**本地**口径全部失败：`dec.jsonl` 的 `s`、日志的 `seat=N`、事件流 `scores` 三种来源互相矛盾；
- **只有门户复盘的 `seats[].user_id` 是经真值对账的座位来源** ⇒ 本工具用它算**我方自己**的端点。

口径：一房 = `auto_ranking.jsonl` 里 `room → strategy`（同房多行取 finished 行，冲突告警）。
未在门户发布的房**直接排除**并报告覆盖率（门户有数小时延迟）。

用法：
  python -X utf8 tools/ab_portal_readout.py
  python -X utf8 tools/ab_portal_readout.py --since "2026-09-16 16:23:34"
"""
from __future__ import annotations
import argparse, collections, glob, io, json, math, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ME = 'u_7a3fba48d70b'


def room_arms():
    raw = collections.defaultdict(list)
    for ln in open(os.path.join(ROOT, 'var', 'auto_ranking.jsonl'), encoding='utf-8'):
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
        except Exception:
            continue
        if d.get('room'):
            raw[d['room']].append(d)
    out, conflicts = {}, []
    for room, ds in raw.items():
        fin = [x for x in ds if x.get('status') == 'finished'] or ds
        pick = fin[-1]
        out[room] = (pick.get('strategy') or '?', pick.get('ts') or '')
        if len({(x.get('strategy') or '?') for x in ds}) > 1:
            conflicts.append((room, [(x.get('ts'), x.get('strategy'), x.get('status')) for x in ds]))
    return out, conflicts


def scan_portal():
    """room -> {'rounds': [(my_win, fan, my_baotou, my_score)], 'seat': <legacy>}

    ★ 2026-09-16 **重大修正：座位是"逐场重洗"的**。

    一个自动房 = **10 个文件**（`<room>_r1_b0..b9_t0.json` = 10 场比赛），**每场自带 `seats`**
    （指南：同一 4 人、座次逐场重洗）。旧实现把"我方座位"当成**整房一个值**（取最后一个文件），
    于是 **~90% 的局归错了人**；实测：320/320 个多文件房里我方座位**至少变过一次**，**0 个房**恒定。
    后果：`我方胡率 / 爆头占胡 / 番` 被稀释成"任意一席"的统计——**而"我方胡率 25.22% ≈ 已知 24.7%"
    这种对账是空检查**（任何一席的胡率都≈25%），验不出这个错。

    同时去掉旧的 `(round_no, dealer, winner, scores)` 去重：同一房 10 场里会**撞键**
    （实测每房只剩 ~64 局而不是 80 局）⇒ 改为按 `game_id`（缺省用文件名）去重。
    """
    per = collections.defaultdict(lambda: {'seat': None, 'rounds': [], 'games': set()})
    files = []
    for d in sorted(glob.glob(os.path.join(ROOT, 'var', 'replays', '*'))):
        files.extend(sorted(glob.glob(os.path.join(d, '*.json'))))
    for f in files:
        try:
            j = json.load(open(f, encoding='utf-8'))
        except Exception:
            continue
        if not isinstance(j, dict):
            continue
        seats = j.get('seats') or []
        if len(seats) != 4:
            continue
        me = next((i for i, x in enumerate(seats) if (x.get('user_id') or '') == ME), None)
        if me is None:
            continue
        room = os.path.basename(f).split('_r')[0]
        gid = j.get('game_id') or os.path.basename(f)
        if gid in per[room]['games']:
            continue
        per[room]['games'].add(gid)
        per[room]['seat'] = me          # legacy：仅最后一个文件的值，勿用于判"我方"
        # ★ `detail`（番种名，判"爆头"用）在 **`round_ended` 事件**里，不在 `rounds[]` 里
        #   —— 按顺序与本文件的 `rounds[]` 一一对应
        details = []
        for b in j.get('blocks') or []:
            if not isinstance(b, dict):
                continue
            for e in b.get('events') or []:
                if e.get('type') == 'round_ended':
                    details.append((e.get('data') or {}).get('detail') or [])
        for ri, r in enumerate(j.get('rounds') or []):
            if not isinstance(r, dict):
                continue
            sc = r.get('scores') or []
            if len(sc) != 4:
                continue
            w = r.get('winner')
            det = details[ri] if ri < len(details) else []
            per[room]['rounds'].append((
                1 if w == me else 0,
                r.get('multiplier') or 1,
                1 if '爆头' in (det or []) else 0,
                sc[me],
            ))
    return per


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--since', default=None)
    ap.add_argument('--top', type=int, default=0, help='>0 时同时打印我方对手的强度（调试用）')
    a = ap.parse_args()
    since = a.since or '2026-09-16 16:23:34'

    arms, conflicts = room_arms()
    portal = scan_portal()
    camp = {r: v for r, v in arms.items() if v[1] >= since}
    pub = {r: v for r, v in camp.items() if r in portal}

    for room, ds in conflicts:
        if room in camp:
            print('⚠ 归属冲突：%s 有多行且策略不同（已按 finished 归）：%s' % (room, ds))
    print('=' * 100)
    print('门户口径 · 逐臂「我方自己」端点   窗口 since=%s' % since)
    print('=' * 100)
    print('战役房 %d 个；门户已发布 %d 个（覆盖率 %.0f%%）⇒ 未发布的房被排除（门户有数小时延迟）'
          % (len(camp), len(pub), 100.0 * len(pub) / max(1, len(camp))))
    if not pub:
        print('⇒ 目前**没有可用的门户数据**；等发布后重跑本脚本即可（不要用本地替代口径，见 §9.53）。')
        return

    S = collections.defaultdict(lambda: [0] * 5)     # 局, 我胡, 番和, 爆头胡, 我方净分
    RM = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0, 0]))
    rcount = collections.Counter()
    for room, (stg, ts) in pub.items():
        rcount[stg] += 1
        for (mywin, m, mybo, mysc) in portal[room]['rounds']:
            x = S[stg]; x[0] += 1; x[4] += mysc
            rr = RM[stg][room]; rr[0] += 1
            if mywin:
                x[1] += 1; x[2] += m; rr[1] += 1
                if mybo:
                    x[3] += 1; rr[2] += 1

    print()
    print('%-14s %5s %7s %8s %10s %9s %10s' % ('arm', '房', '局', '我胡率', '我爆头占胡', '番/胡', '我净/房'))
    for stg in sorted(S):
        x = S[stg]
        n = max(1, x[0])
        hu = x[1] / n
        bo = x[3] / max(1, x[1])
        hs = [100.0 * r[1] / r[0] for r in RM[stg].values() if r[0] >= 10]
        bs = [100.0 * r[2] / r[1] for r in RM[stg].values() if r[1] >= 3]
        print('%-14s %5d %7d %7.2f%% %9.2f%% %9.3f %+10.1f' % (
            stg, rcount[stg], x[0], 100 * hu, 100 * bo, x[2] / max(1, x[1]), x[4] / max(1, rcount[stg])))
        print('%-14s %5s %7s %7.2f%% %9.2f%%   (逐局 SE)' % (
            '', '', '', 100 * math.sqrt(hu * (1 - hu) / n),
            100 * math.sqrt(bo * (1 - bo) / max(1, x[1]))))
        if len(hs) >= 2:
            print('%-14s %5s %7s %7.2f%% %9.2f%%   (按房聚类 SE, n房=%d/%d)' % (
                '', '', '', st.stdev(hs) / len(hs) ** 0.5,
                (st.stdev(bs) / len(bs) ** 0.5) if len(bs) >= 2 else float('nan'), len(hs), len(bs)))
    # ★ 尺子校验（2026-09-16 新增）：门户逐房"我方得分"必须等于 `auto_ranking.jsonl` 的 `total_score`
    #   —— 这是**唯一的正面证据**（胡率≈25% 的空检查验不出座位错）。
    ring = {}
    try:
        for ln in io.open(os.path.join(ROOT, 'var', 'auto_ranking.jsonl'), encoding='utf-8'):
            ln = ln.strip()
            if not ln:
                continue
            d = json.loads(ln)
            mine = next((x for x in (d.get('ranking') or []) if x.get('user_id') == ME), None)
            if d.get('room') and mine is not None:
                ring[d['room']] = mine.get('total_score')
    except OSError:
        ring = {}
    ok = bad = 0
    worst = []
    for room in pub:
        if room not in ring:
            continue
        got = sum(r[3] for r in portal[room]['rounds'])
        if abs(got - (ring[room] or 0)) <= 0.5:
            ok += 1
        else:
            bad += 1
            worst.append((room, got, ring[room], len(portal[room]['rounds'])))
    if ok or bad:
        print()
        print('★ 尺子校验（门户逐房我方得分 vs auto_ranking）：一致 %d / 不一致 %d = %.1f%%'
              % (ok, bad, 100.0 * ok / max(1, ok + bad)))
        for w in worst[:3]:
            print('   不一致示例：%s 门户=%s 榜单=%s 局数=%d' % w)

    ks = sorted(S)
    if len(ks) == 2:
        x, y = S[ks[0]], S[ks[1]]
        if x[1] and y[1]:
            print()
            print('两臂「我方」差：爆头占胡 %+.2fpp ；胡率 %+.2fpp ；番/胡 %+.3f ；净胜/房 %+.1f' % (
                100 * (y[3] / y[1] - x[3] / x[1]),
                100 * (y[1] / y[0] - x[1] / x[0]),
                y[2] / y[1] - x[2] / x[1],
                y[4] / max(1, rcount[ks[1]]) - x[4] / max(1, rcount[ks[0]])))
    print()
    print('注：① 座位来自门户 `seats[].user_id`（唯一经真值对账的来源）；② 覆盖率低于 ~80% 时结论要先打折扣；')
    print('    ③ 主判据仍是 `tools/ab_readout.py` 的净胜/房 t 值（预登记 t≥1.50 且 150 房/臂）。')


if __name__ == '__main__':
    main()
