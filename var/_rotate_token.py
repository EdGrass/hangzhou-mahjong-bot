# -*- coding: utf-8 -*-
"""轮换门户全局令牌（POST /portal/api/test-rooms/identity/token）并保存 var/.global_token。

旧全局令牌随即作废；测试房/报名令牌不受影响。用法：python var/_rotate_token.py
"""
import json
import ssl
import urllib.request
import urllib.error

ctx = ssl._create_unverified_context()
cookie = open("var/.portal_cookie", encoding="utf-8-sig").read().strip()
base = "https://10.240.169.190:18080"
r = urllib.request.Request(base + "/portal/api/test-rooms/identity/token",
                           headers={"Cookie": cookie,
                                    "Content-Type": "application/json"},
                           data=b"{}", method="POST")
try:
    with urllib.request.urlopen(r, timeout=20, context=ctx) as x:
        d = json.loads(x.read().decode("utf-8"))
except urllib.error.HTTPError as e:
    print("rotate failed:", e.code, e.read().decode("utf-8", "replace")[:300])
    raise SystemExit(1)
tok = d.get("token") or d.get("global_token") or ""
if not tok:
    print("unexpected response:", json.dumps(d, ensure_ascii=False)[:500])
    raise SystemExit(1)
with open("var/.global_token", "w", encoding="utf-8") as f:
    f.write(tok)
print("token rotated & saved: var/.global_token len=%d" % len(tok))
print("user:", json.dumps(d, ensure_ascii=False)[:200])
