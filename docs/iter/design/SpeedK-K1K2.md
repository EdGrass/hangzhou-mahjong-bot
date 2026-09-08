# SpeedK（K1+K2 牌效吸收）——设计要点

> 日期：2026-09-08 | 候选：C007 | 对照：SpeedE（真机同桌/窗口两段式判据不变）
> 出处：牌效综述 https://wongsingfo.github.io/comp-sys/docs/mahjong/efficiency/（用户提供）
> 规则语境：杭麻 财神(白板=万能)、自摸和、无荣和 → 纯自摸竞速；财神稀释"形"差，
> 历史 F(s==1 ukeire) 真机 null —— K1/K2 的价值在于补全 E 从未系统化的两个行为面。

## K1：全向听级一步有效牌 tie-break（弃牌）

现状（SpeedE `_best_discard_honor`）：键 = (s, −等待数[s==0 时], 孤字, 留摸)。
缺口：s≥1 的弃牌 tie 无"进张"比较 → 改键为：
- s==0（听牌）：保持 等待数（waits）不变；
- s≥1：**一步有效牌数 ukeire(rem)** = 对每类牌 t∈候选牌集，摸 t 后（14 张）
  存在一张弃牌使向听 < shanten(rem) 的类数（SpeedF 语义推广到任意 s≥1；
  仅当"同一最小 s 的候选 ≥2"才付计算代价；候选牌集预过滤见实现）。
- 键 = (s, −ukeire, 孤字, 留摸)。副露/七对/财神口径全部沿用 exact_shanten。
性能约束：单决策 <100ms（真机窗口 1s）；tie 常态 <10ms（预过滤 + 早停）。

## K2：副露 ukeire 判据（碰/吃/直杠）

现状（`_want_claim`）：副露后成型更快（after<before）才要。
改为"向听相同也要比进张"：
- 构造副露后终态：hand −2(peng)/−3(gang_ming)/−2(chi 对) → e+1 → 最佳弃牌后的
  13-3(e+1)-g 状态（复用 _claim_value 推导）；
- 判定：s_after < s_before → 要（原规则，向听提速）
        s_after == s_before == 0 → 要 当且仅当 after 的最佳弃牌听牌等待数 > before
          （已听：不碰是 E 现状——保留听形；仅当碰后等待更多才破坏现状）
        s_after == s_before >= 1 → 要 当且仅当 ukeire(after_best) > ukeire(before)
        s_after > s_before → 不要（绝不倒退）
- 已听不碰的 E 语义被上一条取代为"比较后决定"（行为面变化点，K2 的核心）；
- 抓打圈/窗口 409 语义不变；直杠（gang_ming）同谓词（e+1,g+1 口径）。

## 验证

1. 单测：ukeire 纯函数（例题手牌有效牌数、与 F 语义一致性）；tie 键顺序；
   K2 谓词各分支（提速要/同速更好要/同速更差不要/已听碰后等待更多要）；
   与 E 的一致性：无 tie/无有效差场景决策逐手相同（性质测试）；
2. 全量回归 + stability；
3. 真机同桌快筛（speedk×2 vs speedE×2，n≈40-60，window_audit）→ δ<-1 枪毙；
4. 正/边缘者 → 正式赛窗口 n≈150 终裁（同 W1 流程，令牌由用户提供）。

## 防重注记

- SpeedF 已测 s==1 ukeire null：K1 的增量= s≥2 覆盖 + 与孤字键的交互，不重复 F；
- 不触碰打点/财飘（C005 范畴）与防守（C004 方法论受限）。
