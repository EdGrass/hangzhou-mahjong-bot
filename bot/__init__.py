"""杭州麻将竞技平台 AI Bot —— 面向 SpeedA 的参赛与优化。

- 参赛策略：bot/speed.py SpeedA（向听数驱动速度算法）；
- 协议层：v10/v11（v11 为轮询限速放宽，无 BREAKING）；
- 评估台：arena/（SpeedA 变体对决）+ 面板。
"""

__version__ = "1.0.0"

# 本 bot 开发时对应的服务器接入指南版本（用于版本自检，见 bot/smoke.py）
# v12（2026-09-04）：新增可选 SSE notify 端点（added，非破坏）
GUIDE_VERSION_KNOWN = 12
