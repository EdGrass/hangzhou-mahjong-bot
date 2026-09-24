# -*- coding: utf-8 -*-
"""安全切换测试房 keeper 策略：写 _keeper_strategy.txt → 只杀 keeper（不碰 match_super/run_bot）
→ 等 watchdog 自愈（≤90s）→ 校验单实例与新策略。
用法：python -X utf8 var/_switch_test_strategy.py <strategy> [rooms]
"""
import io, os, sys, time
sys.path.insert(0, '.')
import psutil

NEW = sys.argv[1] if len(sys.argv) > 1 else 'speedc118'
ROOMS = sys.argv[2] if len(sys.argv) > 2 else '4'
assert NEW in io.open('run_bot.py', encoding='utf-8').read(), '策略未注册到 run_bot.py: %s' % NEW
io.open('var/_keeper_strategy.txt', 'w', encoding='utf-8').write(NEW)
print('strategy file ->', NEW)
me = os.getpid()
killed = []
for p in psutil.process_iter(['pid', 'cmdline', 'exe']):
    try:
        if p.info['pid'] == me:
            continue
        exe = os.path.basename(p.info.get('exe') or '').lower()
        if 'python' not in exe:
            continue
        args = [os.path.basename(str(a).replace('\\', '/')) for a in (p.info.get('cmdline') or [])[1:]]
        if '_keeper.py' in args:
            killed.append(p.info['pid'])
    except Exception:
        pass
for pid in killed:
    try:
        psutil.Process(pid).kill()
        print('killed _keeper pid', pid)
    except Exception as e:
        print('kill fail', pid, e)
print('等待 watchdog 自愈（≤120s）...')
time.sleep(110)
rows = []
for p in psutil.process_iter(['pid', 'cmdline', 'exe']):
    try:
        exe = os.path.basename(p.info.get('exe') or '').lower()
        if 'python' not in exe:
            continue
        cl = ' '.join(str(x) for x in (p.info.get('cmdline') or []))
        if '_keeper.py' in cl or 'match_super.py' in cl or 'run_bot.py' in cl:
            rows.append((p.info['pid'], cl[:130]))
    except Exception:
        pass
print('进程:')
for r in rows:
    print('  ', r)
print('keeper 数 =', sum(1 for _p, cl in rows if '_keeper.py' in cl))
