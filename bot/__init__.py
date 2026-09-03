"""杭州麻将竞技平台 AI Bot —— v8 协议骨架。

当前实现范围（第一阶段）：
- v8 多阶段锦标赛协议循环（registering / stage_open / stage_done / running / finished / closed / void）
- 单局 seq 长轮询 / 快照重建 / 窗口去重
- 策略接口 + NaiveStrategy（出第一张、窗口全过、不主动胡——依赖服务端超时兜底）

牌技（胡牌判定 / 番型 / 出牌策略）为后续迭代，只改 bot.strategy 即可接入。
"""

__version__ = "0.1.0"

# 本 bot 开发时对应的服务器接入指南版本（用于版本自检，见 bot/smoke.py）
GUIDE_VERSION_KNOWN = 8
