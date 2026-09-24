"""ab_own_endpoint.py —— 按 A/B 臂读**我方自己**的机制端点（本地录制，零延迟，无"全场稀释"）。

为什么需要（§9.48）：`tools/ab_endpoint.py` 统计的是**全场**爆头占胡 ——
而候选只改**我们自己的**出牌，全场指标把效应稀释到约 1/4，筛选中枢就不灵敏了。
本工具用本地 `.dec.jsonl` 里的 `s`（**我方座位号**，按房取众数）把事件流的 `round_ended` 归因到我方，
于是能直接量**我方**的：胡率 / 番每胡 / **爆头占胡** / 净胜每房。

用法：python -X utf8 tools/ab_own_endpoint.py
"""
from __future__ import annotations
import collections, glob, json, math, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


ME_UID = 'u_7a3fba48d70b'


def our_seat_by_room():
    """room -> 我方座位号 —— ⚠ **必须来自门户 `seats[].user_id`**。

    ★ 2026-09-16 更正（这是一次严重的方法错误）：本地 `dec.jsonl` 的 `s` **不是"我方座位"** ——
    同一房的 10 个 `<gid>_r1_b<N>_t0.dec.jsonl` **每个文件只有一个座位**（b0=0、b1=1、b2=1、b3=3…），
    说明该目录把**同房多个 bot 的决策流都写了进来**（按座位分文件），不是按 block。
    ⇒ 从 `s` 的众数推"我方座位"是错的（318 个可比房里只有 139=44% 碰巧一致，实测）。
    ⇒ 正确做法：用门户复盘的 `seats[].user_id` 找到我们的下标；**未发布的房只能排除**。
    """
    seat = {}
    for f in glob.glob(os.path.join(ROOT, 'var', 'replays', '*', '*.json')):
        try:
            j = json.load(open(f, encoding='utf-8'))
        except Exception:
            continue
        if not isinstance(j, dict):
            continue
        seats = j.get('seats') or []
        if len(seats) != 4:
            continue
        room = os.path.basename(f).split('_r')[0]
        for i, x in enumerate(seats):
            if (x.get('user_id') or '') == ME_UID:
                seat[room] = i
                break
    return seat


def our_seat_from_logs():
    """从 `logs/auto_*.log` 解析 **gid -> 我方座位**（本地权威来源，§9.52 的 TODO）。

    日志形态（实测）：
        [19:28:26] 本场结束: finished 标记（gid=a_0aca4ad1f990_r1_b9_t0）
        [19:28:26] 本场积分 seat=2: [44, -6, 12, -50]
        [19:28:26] 我的本场得分: 12          ← 与 scores[seat] 相等，可自证
    ⇒ 每个 **block gid** 一条；`seat=N` 即我方座位。
    """
    import re
    pat_gid = re.compile(r'本场结束.*gid=([A-Za-z0-9_]+)')
    pat_seat = re.compile(r'本场积分 seat=(\d)')
    pat_mine = re.compile(r'我的本场得分: (-?\d+)')
    out = {}
    for f in glob.glob(os.path.join(ROOT, 'logs', 'auto_*.log')):
        pend = None
        try:
            for line in open(f, encoding='utf-8', errors='replace'):
                m = pat_gid.search(line)
                if m:
                    pend = m.group(1)
                    continue
                if pend:
                    ms = pat_seat.search(line)
                    if ms:
                        out[pend] = int(ms.group(1))
                        continue
                    if pat_mine.search(line):
                        continue
        except Exception:
            continue
    return out


def main():
    since = None
    arms = None
    ab = os.path.join(ROOT, 'var', '.ab_mode')
    if os.path.exists(ab):
        try:
            cfg = json.loads(open(ab, encoding='utf-8').read())
            since = cfg.get('started')
            arms = {cfg.get('a'), cfg.get('b')}
        except Exception:
            pass

    # ⚠ 一个房可能出现**多行**（实测 400 房里 1 例：先 running/exit=-1、后 finished）⇒
    #   必须**确定性选取**（优先 finished 那行），并对"同一房出现不同策略"**告警**（A/B 归属会被污染）。
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
    rmap = {}
    conflict = []
    for room, ds in raw.items():
        fin = [x for x in ds if (x.get('status') == 'finished')] or ds
        pick = fin[-1]
        rmap[room] = (pick.get('strategy') or '?', pick.get('ts') or '')
        if len({(x.get('strategy') or '?') for x in ds}) > 1:
            conflict.append((room, [(x.get('ts'), x.get('strategy'), x.get('status'),
                                     x.get('exit_code')) for x in ds]))
    # ★ 我方座位 —— **只认门户 `seats[].user_id`**（§9.53 定案）。
    #   ⛔ 本地两条路都已实测失败：`dec.jsonl` 的 `s`（只有 44% 碰巧一致）、
    #      `logs/auto_*.log` 的 `seat=N`（与事件流 `scores` 的座位顺序只有 16% 对得上）
    #      ⇒ **不要再用本地来源**；门户未发布时本工具只能诚实输出"无样本"。
    seat_room = our_seat_by_room()
    print('座位来源：门户 `seats` room=%d 个（本地来源已废弃，见 docstring/§9.53）' % len(seat_room))

    S = collections.defaultdict(lambda: [0] * 6)   # 局, 我胡, 番和, 爆头和, 我方得分和, 房数
    PER_ROOM = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0, 0]))
    # arm -> room -> [局, 我胡, 爆头]  （★ 用于**按房聚类**的标准误）
    rooms = collections.Counter()
    skipped = collections.Counter()
    seen = set()
    for f in glob.glob(os.path.join(ROOT, 'var', 'replays', 'auto_*', '*.jsonl')):
        if f.endswith('.dec.jsonl'):
            continue
        room = os.path.basename(f).split('_r')[0]
        info = rmap.get(room)
        if not info:
            continue
        stg, ts = info
        if since and ts < since:
            continue
        if arms and stg not in arms:
            continue
        if room in seat_room:
            me = seat_room[room]
        else:
            skipped[stg] += 1
            continue
        if room not in seen:
            seen.add(room)
            rooms[stg] += 1
        try:
            for ln in open(f, encoding='utf-8'):
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    o = json.loads(ln)
                except Exception:
                    continue
                if o.get('type') != 'round_ended':
                    continue
                data = o.get('data') or {}
                sc = data.get('scores') or []
                a = S[stg]
                a[0] += 1
                if len(sc) > me:
                    a[4] += sc[me]
                pr = PER_ROOM[stg][room]
                pr[0] += 1
                if o.get('seat') == me and not data.get('draw'):
                    a[1] += 1
                    pr[1] += 1
                    fan = data.get('fan') or 1
                    a[2] += fan
                    if '爆头' in (data.get('detail') or []):
                        a[3] += 1
                        pr[2] += 1
        except Exception:
            continue

    for room, ds in conflict:
        print('⚠ 归属冲突：房 %s 在 auto_ranking 里有多行且**策略不同** ⇒ 该房可能被污染，已按 finished 行归属：' % room)
        for x in ds:
            print('     ', x)
    print('=' * 96)
    print('A/B **我方自己**的机制端点（本地录制）  since=%s' % since)
    print('=' * 96)
    if not S:
        print('窗口内没有可归属的房间（检查 .ab_mode / auto_ranking / dec 里的座位号）')
        return
    print('%-14s %5s %7s %8s %10s %10s %10s' % ('arm', '房', '局', '胡率', '爆头占胡', '番/胡', '净胜/房'))
    import statistics as _st
    for stg in sorted(S):
        a = S[stg]
        n = a[0]
        hu = a[1] / max(1, n)
        bo = a[3] / max(1, a[1])
        se_hu = math.sqrt(hu * (1 - hu) / max(1, n))
        se_bo = math.sqrt(bo * (1 - bo) / max(1, a[1]))
        net = a[4] / max(1, rooms[stg])
        print('%-14s %5d %7d %7.2f%% %9.2f%% %10.3f %+10.1f' % (
            stg, rooms[stg], n, 100 * hu, 100 * bo, a[2] / max(1, a[1]), net))
        print('%-14s %5s %7s %6.2f%% %9.2f%%   (逐局 SE)' % ('  ±SE(1σ)', '', '', 100 * se_hu, 100 * se_bo))
        # ★ 按房聚类：房内回合与对手都相同 ⇒ 逐局 SE 会低估；用"逐房率"的 SE 更诚实
        hs = [100.0 * p[1] / p[0] for p in PER_ROOM[stg].values() if p[0] >= 10]
        bs = [100.0 * p[2] / p[1] for p in PER_ROOM[stg].values() if p[1] >= 3]
        if len(hs) >= 2:
            print('%-14s %5s %7s %6.2f%% %9.2f%%   (按房聚类 SE, n房=%d/%d)' % (
                '  ±SE(聚类)', '', '', _st.stdev(hs) / len(hs) ** 0.5,
                (_st.stdev(bs) / len(bs) ** 0.5) if len(bs) >= 2 else float('nan'), len(hs), len(bs)))
    tot_skip = sum(skipped.values())
    if tot_skip:
        print()
        print('⚠ 跳过 %d 房（缺 dec 座位号 ⇒ 其复盘文件还没落盘）：%s' % (
            tot_skip, dict(skipped)))
        print('  ⇒ 房数在两次运行间可能变化，**不同时刻的读数不要直接比较**（这是本地录制的固有滞后）。')
    print()
    print('注：① 我方座位来自**门户 `seats`**（本地 dec 的 `s` 不可用，见函数 docstring 的更正说明）；')
    print('    未在门户发布的房会被**排除** ⇒ 本役若尚未发布，输出会是"无样本"。')
    print('    ② 这是**我方自己**的口径，比 `ab_endpoint` 的"全场"口径**灵敏约 4 倍**；')
    print('    ② 覆盖率仍是本地录制的 ~50~60%（每房只落 39~45 个 round_ended）⇒ 仍属子集口径；')
    print('    ③ **最终判定**请用门户完整语料 `tools/fan_types.py` 复核。')
    if len(S) == 2:
        ks = sorted(S)
        x, y = S[ks[0]], S[ks[1]]
        if x[1] and y[1]:
            print()
            print('两臂**我方**爆头占胡差 = %+.2fpp ；我方胡率差 = %+.2fpp' % (
                100 * (y[3] / y[1] - x[3] / x[1]), 100 * (y[1] / y[0] - x[1] / x[0])))
            def _cl(arm):
                hs2 = [100.0 * p[1] / p[0] for p in PER_ROOM[arm].values() if p[0] >= 10]
                return (_st.stdev(hs2) / len(hs2) ** 0.5) if len(hs2) >= 2 else float('nan')
            se_d = (_cl(ks[0]) ** 2 + _cl(ks[1]) ** 2) ** 0.5
            if se_d == se_d and se_d > 0:
                print('  （**按房聚类**：胡率差的 SE ≈ %.2fpp ⇒ z ≈ %.2f）' % (
                    se_d, abs(100 * (y[1] / y[0] - x[1] / x[0])) / se_d))


if __name__ == '__main__':
    main()
