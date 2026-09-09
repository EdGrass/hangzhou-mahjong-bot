"""杭州麻将竞技平台 AI Bot —— 面向 SpeedA 的参赛与优化。

- 参赛策略：bot/speed.py SpeedA（向听数驱动速度算法）；
- 协议层：v10/v11（v11 为轮询限速放宽，无 BREAKING）；
- 评估台：arena/（SpeedA 变体对决）+ 面板。
"""

__version__ = "1.0.0"

# 本 bot 开发时对应的服务器接入指南版本（用于版本自检，见 bot/smoke.py）
# v13（BREAKING，仅新锦标赛）：分桌实到=ready∧开赛前90s在线（本 bot 轮询/ready
#   节奏均满足）；v14（added）：/portal/api/guide 全文免认证
# v15（BREAKING）：/api/match 自动房默认 M=10/Rounds=8——本 bot 不调用 /api/match
#   （测试房/锦标赛均走门户派发报名令牌），无影响；
# v21（changed 2026-09-07）：七对/爆头 4 白板口径——mahjong 引擎已对齐
#   （c660ccc + tests/test_engine_v21.py + 黄金集 140 例在线刷新）；
# v24（BREAKING 2026-09-08）：删除 POST /api/users 匿名注册、全局令牌须门户绑定
#   ——本 bot 令牌来源 = 门户测试房/报名令牌，不受影响（run_bot 注释已更新）。
# v25（BREAKING 2026-09-08）：服务端补齐「吃最多 2 摊」校验——speed._want_claim
#   chi 分支已自限（chi_cnt>=2 拒，防 harmful 409）；
# v26（changed 2026-09-08）：抓打圈豁免方（打财神者本人）可吃碰明杠补杠；快照
#   god 新增 god_discarder_seat——我方弃白场景极低频（自动房实测 0 弃白），
#   snap_god 映射字段预留在 model.py，行为适配待真机实测后落地；
# v27（portal 榜 added/changed）：bot 玩家 API 零影响。
GUIDE_VERSION_KNOWN = 27
