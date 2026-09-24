# -*- coding: utf-8 -*-
"""`_ps.py` —— **PowerShell 可执行文件解析器**（R1379）。

## 为什么需要（真实隐患，本轮实测）

`var/_4test_gate_precheck.py`、`var/_bsegment.py`、`var/_enter_event.py` 原先都硬编码调 **`pwsh`**（PowerShell 7）。
但本机**只有 Codex 运行时自带**的一份 `pwsh.exe`，它在**注册表 PATH 里不存在**（实测：User/Machine PATH 均无）：

* **计划任务**（cmd /c，继承注册表环境）里 `pwsh` ⇒ **FileNotFoundError**；
* **用户自己开的 PowerShell 窗口**同理（系统里没装 PowerShell 7）。

只有“在 Codex 会话里跑”时才会碰巧命中（我的 shell PATH 被注入了那个目录）—— 属于**只在真实执行场景才暴露**的缺陷。

## 行为

1. 环境变量 `HM_PS` 指定的路径（若存在）；
2. PATH 上的 `pwsh` / `pwsh.exe`；
3. **回退** 到一定存在的 Windows PowerShell 5.1（`%SystemRoot%\\System32\\WindowsPowerShell\\v1.0\\powershell.exe`）；
4. 再回退 `powershell`。

> 注：`_register_*.ps1` 都是 **UTF-8 BOM**（R1323 回归门钉住）⇒ 5.1 能正确解码；
> 它们只用 `Register-ScheduledTask` / `New-ScheduledTaskAction` 等基础 cmdlet ⇒ 5.1 可用。
"""
from __future__ import annotations
import os
import shutil


def exe():
    """返回可用的 PowerShell 可执行文件（字符串）。"""
    env = os.environ.get("HM_PS")
    if env and os.path.exists(env):
        return env
    for cand in ("pwsh", "pwsh.exe"):
        hit = shutil.which(cand)
        if hit:
            return hit
    win = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                       "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
    if os.path.exists(win):
        return win
    return "powershell"


def argv(*args):
    """把 `["-NoProfile", "-File", ...]` 前面接上已解析的 PowerShell。"""
    return [exe()] + list(args)
