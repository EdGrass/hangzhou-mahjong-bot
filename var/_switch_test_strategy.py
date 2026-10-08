# -*- coding: utf-8 -*-
"""安全切换测试房 keeper 策略：写 _keeper_strategy.txt → 只杀 keeper（不碰 match_super/run_bot）
→ 等 watchdog 自愈（≤180s）→ 校验单实例与新策略。

R1595 修复：watchdog 可能在旧循环里已读到旧策略，导致刚拉起的新 keeper 把策略文件覆盖回去。
本脚本现在会在超时窗口内反复校正策略文件，并只终结 argv 不是目标策略的 keeper。

用法：python -X utf8 var/_switch_test_strategy.py <strategy> [rooms]
"""
import io
import os
import sys
import time

sys.path.insert(0, '.')
import psutil

NEW = sys.argv[1] if len(sys.argv) > 1 else 'speedc118'
ROOMS = sys.argv[2] if len(sys.argv) > 2 else '4'
assert NEW in io.open('run_bot.py', encoding='utf-8').read(), '策略未注册到 run_bot.py: %s' % NEW

STRAT_FILE = os.path.join('var', '_keeper_strategy.txt')
TIMEOUT_S = 180.0


def write_target():
    io.open(STRAT_FILE, 'w', encoding='utf-8').write(NEW)


def keeper_rows():
    me = os.getpid()
    rows = []
    for p in psutil.process_iter(['pid', 'cmdline', 'exe']):
        try:
            if p.info['pid'] == me:
                continue
            exe = os.path.basename(p.info.get('exe') or '').lower()
            if 'python' not in exe:
                continue
            argv = [str(a) for a in (p.info.get('cmdline') or [])]
            strat = ''
            for i, a in enumerate(argv):
                if os.path.basename(a.replace('\\', '/')).lower() == '_keeper.py':
                    if i + 1 < len(argv):
                        strat = argv[i + 1]
                    rows.append((p.info['pid'], strat, ' '.join(argv)))
                    break
        except Exception:
            pass
    return rows


def print_procs():
    rows = []
    for p in psutil.process_iter(['pid', 'cmdline', 'exe']):
        try:
            exe = os.path.basename(p.info.get('exe') or '').lower()
            if 'python' not in exe:
                continue
            cl = ' '.join(str(x) for x in (p.info.get('cmdline') or []))
            if '_keeper.py' in cl or 'match_super.py' in cl or 'run_bot.py' in cl:
                rows.append((p.info['pid'], cl[:150]))
        except Exception:
            pass
    print('进程:')
    for r in rows:
        print('  ', r)
    print('keeper 数 =', sum(1 for _p, cl in rows if '_keeper.py' in cl))


write_target()
print('strategy file ->', NEW)

deadline = time.time() + TIMEOUT_S
last_wrong = []
while time.time() < deadline:
    write_target()
    ks = keeper_rows()
    good = [r for r in ks if r[1] == NEW]
    if len(ks) == 1 and len(good) == 1:
        print('keeper 已切换 pid=%d strategy=%s' % (good[0][0], good[0][1]))
        print_procs()
        raise SystemExit(0)

    wrong = [r for r in ks if r[1] != NEW]
    last_wrong = wrong
    for pid, strat, _cl in wrong:
        try:
            psutil.Process(pid).kill()
            print('killed _keeper pid %d strategy=%s' % (pid, strat or '?'))
        except Exception as e:
            print('kill fail', pid, e)
    time.sleep(2)

write_target()
print('切换超时：未看到 strategy=%s 的单 keeper' % NEW)
if last_wrong:
    print('最后看到的 keeper:')
    for pid, strat, cl in last_wrong:
        print('  ', pid, strat, cl[:150])
print_procs()
raise SystemExit(2)
