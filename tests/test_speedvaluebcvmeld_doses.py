# -*- coding: utf-8 -*-
"""\u5242\u91cf\u5bf9\u9f50\u7684\u4e09\u5c42\u90e8\u7f72\u81c2\u5951\u7ea6\u5355\u6d4b\uff08R1411/R1413\uff09\u3002

\u4e3a\u4ec0\u4e48\uff1a`var/_campaign_ready.py` \u7684\u8d77\u5f79\u524d\u4f53\u68c0\u4f1a\u8981\u6c42\u6bcf\u4e2a\u53ef\u9009\u81c2**\u6709\u5355\u6d4b\u5f15\u7528**\uff1b
\u672c\u8f6e\u65b0\u52a0\u4e86 `speedvaluebcvmeldp40/p35`\uff08\u82e5\u5f79 4 \u5224\u526f\u9732\u6fc0\u8fdb\u6863\u66f4\u597d\uff0c\u6700\u7ec8\u81c2\u5c31\u7528\u5b83\u4eec\uff09\uff0c
\u5fc5\u987b\u628a\u201c\u6ce8\u518c\u5c31\u4f4d + \u53e3\u5f84\u6b63\u786e + \u4e09\u5c42\u771f\u7684\u6302\u4e0a\u4e86\u201d\u9489\u6b7b\uff0c\u5426\u5219\u5230\u6b63\u5f0f\u8d5b\u624d\u53d1\u73b0\u201c\u67d0\u4e00\u5c42\u6ca1\u751f\u6548\u201d\u5c31\u662f\u9759\u9ed8\u53d8\u5f62\u3002
"""
from __future__ import annotations
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.speedvalue import SpeedValue                    # noqa: E402
from bot.speedvaluebc import SpeedValueBC                # noqa: E402
from bot.speedvaluebcv import SpeedValueBCV              # noqa: E402
from bot.speedvaluemeld import SpeedValueMeld            # noqa: E402


class TestTripleDoses(unittest.TestCase):
    CASES = (("speedvaluebcvmeld", 0.45),
             ("speedvaluebcvmeldp40", 0.40),
             ("speedvaluebcvmeldp35", 0.35))

    def test_registered_and_dose(self):
        from run_bot import STRATEGY_FACTORIES as F
        for key, p in self.CASES:
            self.assertIn(key, F, "%s \u672a\u6ce8\u518c" % key)
            o = F[key]()
            self.assertAlmostEqual(p, float(getattr(o, "claim_p")), places=6,
                                   msg="%s \u7684 claim_p \u5e94 = %.2f" % (key, p))

    def test_three_layers_are_hooked(self):
        from run_bot import STRATEGY_FACTORIES as F
        for key, _p in self.CASES:
            t = type(F[key]())
            for cls in (SpeedValueBCV, SpeedValueBC, SpeedValueMeld, SpeedValue):
                self.assertIn(cls, t.__mro__, "%s \u7f3a\u5c42 %s" % (key, cls.__name__))
            # \u7a97\u53e3\u5c42\uff1a\u53d6\u6d88\u606f\u94a9\u5b50\u5fc5\u987b\u88ab\u526f\u9732\u5c42\u63a5\u7ba1\uff08\u4e0d\u662f SpeedValue \u539f\u7248\uff09
            self.assertIsNot(t._want_claim, SpeedValue._want_claim,
                             "%s \u7684\u526f\u9732\u5c42\u6ca1\u751f\u6548" % key)


if __name__ == "__main__":
    unittest.main()