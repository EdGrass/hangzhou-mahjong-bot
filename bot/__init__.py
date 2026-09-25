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
# v28（changed 2026-09-09）：门户胡大牌榜排序链去掉第 3 键「该牌型全史次数」
#   ——门户 API 面，bot 玩家 API 契约零影响。
# v29（BREAKING 2026-09-09）：新增全服功能开关——管理页可关闭自由匹配与自建
#   测试房，关闭后 POST /api/match / POST /portal/api/test-rooms 一律
#   403 FEATURE_DISABLED（**永久条件，不要重试**；在途对局与已在房中的幂等
#   路径照常）。本 bot 已在 tools/match_super.py 与 run_bot.py --match 分支
#   把 403 与瞬态错误分流（403 直接退出，不做退避重试）。免认证可读
#   GET /portal/api/features 预检 {match_enabled, test_rooms_enabled}。
# v30（changed 2026-09-10）：他人真名全面收口——正式赛以外一切 API 的姓名字段
#   只下发 AI 昵称（为空则空串，消费方回退 user_id）。契约 schema 逐字节不变、
#   无新错误码；本 bot 不依赖对手姓名字段（按 user_id 匹配）→ 零影响，仅同步版本号。
# v31（changed 2026-09-11）：局间暂停 5s（phase=settled）——本 bot 的 decide 对
#   非 draw/response_ 相位返回 None（my_turn/window_pending 皆 False），实测无影响；
#   吞吐实测：09-15 起房间间隔中位 15.0 min = 4.00 房/h（与改版前一致，暂停被房间
#   时长吸收）⇒ 一个月计划里的 ~4 房/h 假设仍成立。
# v32（changed 2026-09-12）：杠爆判定在**杠动作时重算**——self-gang 后补到爆头牌
#   记 杠开+爆头（fan 4，而非此前的杠开 fan 2）。已用线上 /portal/api/fan_calc 核对：
#   chain={1,0} + 爆头 ⇒ fan 4；本地 mahjong/fan.calc 完全一致（tests/test_engine_v21 覆盖）。
# v33（changed 2026-09-13）：杠后补牌**不再自动结算**（可 hu / 续杠 / 弃胡打财神续飘）
#   ⇒ 「杠 + 财飘」链可叠到 count=2：线上核对 {count:2,piao:1} + 爆头 ⇒ fan 8（detail
#   标签为「杠飘链×2」；本地 fan 值一致、仅标签字符串不同）⇒ C141 的 chain 修正正好
#   吃到这条新规（已加单测 tests/test_speedc141.py::test_v33_gang_then_piao_chain）。
# v34（added 2026-09-14）：今日榜加 last（垫底）键——纯门户 API，玩家侧零影响。
GUIDE_VERSION_KNOWN = 35
