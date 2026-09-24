# -*- coding: utf-8 -*-
"""自愈入口（供 Windows 计划任务每 5 分钟调用）：确保 watchdog 与 keeper 都在跑。

- 只做「缺失才启动」，幂等、静默、不杀任何进程；
- 依赖 var/_keeper_strategy.txt 记录当前策略；watchdog 自己会保证 keeper/match_super 存在。
"""
import io, json, os, subprocess, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import psutil
sys.path.insert(0, os.path.join(ROOT, "var"))
import _feature_mode as _fm  # noqa: E402


def _has(script_base):
    for p in psutil.process_iter(["cmdline", "exe"]):
        try:
            exe = os.path.basename(p.info.get("exe") or "").lower()
            if "python" not in exe:
                continue
            for a in (p.info.get("cmdline") or [])[1:]:
                if os.path.basename(str(a).replace("\\", "/")).lower() == script_base:
                    return True
        except Exception:
            pass
    return False


def _start(script, *args):
    subprocess.Popen([sys.executable, "-X", "utf8", "-u", os.path.join(ROOT, "var", script)] + list(args),
                     cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


LOG_PATH = os.path.join(ROOT, "var", "_ensure_all.log")
FLAG = os.path.join(ROOT, "var", ".official_mode")
SPEC = os.path.join(ROOT, "var", ".official_spec.json")


def official_argv(spec_path=None):
    """官方赛自愈重启 keeplive 时要带的参数（以 .official_spec.json 为准）。

    ★ 2026-09-16 新增：旧实现**不带参数**拉起 `_official_keepalive.py` ⇒ 回落到默认
    （`speedtugc` + 二测令牌）。正式赛换了令牌/策略后，一旦整机重启就会**静默用错参数参赛**。
    """
    path = spec_path or SPEC
    try:
        with io.open(path, encoding="utf-8-sig") as fh:      # ★ 2026-09-17：顺手修掉未关闭的句柄（行为不变）
            d = json.loads(fh.read())
    except Exception:
        return []
    out = []
    for key, flag in (("strategy", "--strategy"), ("token_file", "--token-file"), ("server", "--server")):
        v = d.get(key)
        if v:
            out += [flag, str(v)]
    return out
AB_FLAG = os.path.join(ROOT, "var", ".ab_mode")


def official_mode():
    """官方赛期间为 True：不拉起测试房 keeper（防与正式赛同账号并发 E002）。"""
    return os.path.exists(FLAG)


def ab_mode():
    """并发交替 A/B 期间为 True：keeper 由 _ab_driver 取代，不要拉起。"""
    return os.path.exists(AB_FLAG)


def main():
    if _fm.handle_pause_on_startup():
        return
    # 官方赛期间不拉起测试房 keeper（否则与正式赛同账号并发 → E002）。
    if official_mode():
        # 正式赛期间：**不拉测试房 keeper**，但必须保证**正式赛 keepalive** 活着 ——
        # 否则 keepalive 自己死掉就没人管了（与当年 keeper 死掉无人管是同一类缺口）。
        if not _has("_watchdog.py"):
            _start("_watchdog.py")
        if not _has("_official_keepalive.py"):
            argv = official_argv()
            if not argv:
                try:
                    with io.open(LOG_PATH, "a", encoding="utf-8") as f:
                        f.write("%s ⚠ 官方赛重启缺 .official_spec.json ⇒ 将用默认参数"
                                "（策略/令牌可能不对！）\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
                except Exception:
                    pass
            _start("_official_keepalive.py", *argv)
        return
    if ab_mode():
        # A/B 期间排批由 _ab_driver 负责：不拉 keeper，但要保证**驱动**活着
        if not _has("_watchdog.py"):
            _start("_watchdog.py")
        if not _has("_ab_driver.py"):
            _start("_ab_driver.py")
        return
    if not _has("_watchdog.py"):
        _start("_watchdog.py")
    if not _has("_keeper.py"):
        try:
            strat = io.open(os.path.join(ROOT, "var", "_keeper_strategy.txt"), encoding="utf-8-sig").read().strip()
        except OSError:
            strat = "speedc073w2"
        io.open(os.path.join(ROOT, "var", ".keeper.lock"), "w", encoding="utf-8").write("0")
        _start("_keeper.py", strat, "4")


if __name__ == "__main__":
    main()
