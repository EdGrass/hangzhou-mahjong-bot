"""免认证冒烟自检（--smoke）：版本自检 + fan-calc 往返试算。

不需要任何令牌：版本端点 5/s、fan-calc 10/s/IP，纯计算无状态变更。
用于验证 服务器连通 → 指南版本 → 番型计算口径 整条链路。
"""
from __future__ import annotations

import bot
from bot.api import ApiError, Client
from bot.util import log

# 确定性用例：13 张互不相同且无白板 → 任何摸牌都不可能组成面子/将/七对
NO_HU_HAND = ["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w",
              "东", "南", "西", "北"]
NO_HU_DRAW = "中"

# 指南示例：三张 1w + 234/567/89 万 + 一对东，摸东成将（手留牌数按示例）
HU_HAND = ["1w", "1w", "1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w", "东", "东"]
HU_DRAW = "东"


def run_smoke(server):
    """返回 True=全部通过。"""
    client = Client(server)
    ok = True

    # 1) 指南版本与变更日志
    log("== 1. 指南版本自检 ==")
    meta = client.guide_version()
    ver = meta.get("version")
    log("服务器指南版本: v%s（updated %s）；本 bot 已知: v%s" % (
        ver, meta.get("updated_at"), bot.GUIDE_VERSION_KNOWN))
    if not isinstance(ver, int) or ver <= 0:
        log("✗ version 字段异常: %r", ver)
        ok = False
    breaking = [c for c in (meta.get("changes") or [])
                if c.get("type") == "breaking" and c.get("version", 0) > bot.GUIDE_VERSION_KNOWN]
    if breaking:
        for c in breaking:
            log("✗ BREAKING v%s（%s）: %s", c.get("version"), c.get("date"), c.get("summary"))
        log("✗ 存在本 bot 未知的 BREAKING 变更，需人工核对")
        ok = False
    else:
        log("✓ 无未知 BREAKING 变更")

    # 2) fan-calc 确定性用例（不含白板 → 必不胡）
    log("== 2. fan-calc 必不胡用例 ==")
    try:
        r = client.fan_calc({"hand": NO_HU_HAND, "draw": NO_HU_DRAW,
                             "chain": {"count": 0, "piao": 0}, "base": 1})
        if r.get("hu") is False:
            log("✓ 不胡判定正确（13 散牌 + 字）")
        else:
            log("✗ 期望 hu=false，实际: %r", r)
            ok = False
    except ApiError as e:
        log("✗ fan-calc 请求失败: %s %s", e.status, e.body[:200])
        ok = False

    # 3) fan-calc 指南示例用例（可胡，校验结算结构）
    log("== 3. fan-calc 指南示例（平胡 ×1） ==")
    try:
        r = client.fan_calc({"hand": HU_HAND, "draw": HU_DRAW,
                             "chain": {"count": 0, "piao": 0}, "base": 1})
        if r.get("hu") is True:
            log("✓ 胡牌判定通过，detail=%s fan=%s", r.get("detail"), r.get("fan"))
            s = r.get("scores") or {}
            if s.get("dealer_hu") and s.get("nondealer_hu"):
                log("✓ 结算结构齐全: 庄胡 win=%s / 闲胡 win=%s",
                    s["dealer_hu"].get("win"), s["nondealer_hu"].get("win"))
            else:
                log("✗ scores 结构缺失: %r", s)
                ok = False
        else:
            log("✗ 期望 hu=true，实际: %r", r)
            ok = False
    except ApiError as e:
        log("✗ fan-calc 请求失败: %s %s", e.status, e.body[:200])
        ok = False

    log("== 冒烟结果: %s ==" % ("全部通过" if ok else "存在失败项"))
    return ok
