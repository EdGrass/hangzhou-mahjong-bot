# -*- coding: utf-8 -*-
"""YouCaiBiKao insurance twins: deterministic legality test + identity.

The critical assertion: with 白 in hand and a 平胡 win that is NOT 爆头, an ungated arm
declares `hu` (=> the server would 409 it under YouCaiBiKao=true, losing the win) while
the YCBK twin refuses and keeps playing.

usage: python -X utf8 tests/test_ycbk_twins.py -v
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from bot.speedchirealized import SpeedMeldMore0Chi            # noqa: E402
from bot.speedgangtakefixed import SpeedGangTakeFixed          # noqa: E402
from bot.speedvalue import SpeedValue                          # noqa: E402
from bot.ycbk_fast import FastYCBKMixin                        # noqa: E402
from bot.ycbk_twins import (SpeedGangTakeFixedYCBK,            # noqa: E402
                            SpeedMeldMore0ChiYCBK, SpeedMeldTol2ChiYCBK,
                            SpeedValueYCBK)
from bot.ycbk_chain import (SpeedC151YCBK,                     # noqa: E402
                            SpeedValueBaotouV5YCBK, SpeedValueBaotouVMeldYCBK,
                            SpeedValueBCMeldP45YCBK,
                            SpeedValueBCMeldYCBK, SpeedValueBCVYCBK,
                            SpeedValueBCVMeldP35YCBK, SpeedValueBCVMeldP40YCBK,
                            SpeedValueBCVMeldYCBK, SpeedValueBCYCBK,
                            SpeedValueMeldP40YCBK, SpeedValueMeldP45YCBK,
                            SpeedValueMeldYCBK)

# 14 tiles: 234w 567w 89w 111w 2b2b 白 -- wins with 白 as the pair partner of 2b,
# holds 白, and the pre-draw 13 tiles are NOT 爆头 (verified below).
HAND = ['2w', '3w', '4w', '5w', '6w', '7w', '8w', '9w',
        '1w', '1w', '1w', '2b', '2b', '白']


def view():
    return {'seat': 0, 'phase': 'draw', 'turn': 0, 'responding_seats': [],
            'my_hand': list(HAND), 'melds': [], 'offer_tile': None, 'river': [],
            'all_melds': [[], [], [], []],
            'god': {'baotou': False, 'chain_count': 0, 'piao_count': 0,
                    'catch_play': False},
            'drawn_tile': '白', 'scores': None}


class TestYCBKTwins(unittest.TestCase):
    def test_identity(self):
        from bot.speedmeldtoldose import SpeedMeldTol2Chi
        for cls, base in ((SpeedValueYCBK, SpeedValue),
                          (SpeedGangTakeFixedYCBK, SpeedGangTakeFixed),
                          (SpeedMeldMore0ChiYCBK, SpeedMeldMore0Chi),
                          (SpeedMeldTol2ChiYCBK, SpeedMeldTol2Chi)):
            self.assertTrue(issubclass(cls, FastYCBKMixin))
            self.assertTrue(issubclass(cls, base))
            o = cls()
            self.assertTrue(o.YOU_CAI_BI_KAO)
            self.assertFalse(o.GOD_MELD)

    def test_case_is_a_legal_win_but_not_baotou(self):
        from mahjong.hu import is_baotou, is_win
        self.assertTrue(is_win(HAND))
        self.assertFalse(is_baotou(HAND[:-1]), "这个例子必须是'非爆头'的平胡才算 YCBK 违规")

    def test_gate_blocks_the_illegal_win(self):
        v = view()
        twin = SpeedValueYCBK()
        self.assertTrue(twin._ycbk_violation(v, HAND[:-1], 0, 0))
        self.assertEqual((SpeedValue().decide(v) or {}).get('action'), 'hu',
                         "未加闸门的臂应当直接宣胡（在 YCBK=true 下会被 409 掐掉）")
        act = twin.decide(v) or {}
        self.assertNotEqual(act.get('action'), 'hu', "加闸门后不得宣胡")
        for other in (SpeedGangTakeFixedYCBK(), SpeedMeldMore0ChiYCBK(),
                      SpeedMeldTol2ChiYCBK()):
            self.assertNotEqual((other.decide(v) or {}).get('action'), 'hu',
                                "所有双胞胎在 YCBK 违规局面下都不得宣胡")
        self.assertEqual(act.get('action'), 'discard')
        self.assertIn(act.get('tile'), HAND)

    def test_twins_stay_legal_on_a_real_window(self):
        import glob
        import io
        import json
        f = sorted(glob.glob(os.path.join(ROOT, 'var', 'replays', 'auto_*', '*.dec.jsonl')),
                   key=os.path.getmtime)[-1]
        got = 0
        for ln in io.open(f, encoding='utf-8'):
            ln = ln.strip()
            if not ln:
                continue
            r = json.loads(ln)
            if not str(r.get('p') or '').startswith('response_'):
                continue
            melds = [{'type': x[0], 'tile': x[1],
                      'tiles': [x[1]] * (4 if x[0] == 'gang' else 3)}
                     for x in (r.get('m') or [])]
            god = r.get('god') or {}
            v = {'seat': r.get('s'), 'phase': r.get('p'), 'turn': r.get('t'),
                 'responding_seats': r.get('rs') or [r.get('s')],
                 'my_hand': list(r.get('h') or []), 'melds': melds,
                 'offer_tile': r.get('o'), 'river': r.get('r') or [],
                 'all_melds': [([{'type': 'meld', 'tile': ts[0], 'tiles': list(ts)}]
                                if ts else []) for ts in (r.get('am') or [])],
                 'god': {'baotou': bool(god.get('b')),
                         'chain_count': int(god.get('cc') or 0),
                         'piao_count': int(god.get('piao') or 0),
                         'catch_play': bool(god.get('cp'))},
                 'drawn_tile': r.get('d'), 'scores': None}
            e = len(melds)
            g = sum(1 for m in melds if m['type'] == 'gang')
            if len(v['my_hand']) != 13 - 3 * e - g or not v['offer_tile']:
                continue
            act = SpeedMeldMore0ChiYCBK().decide(v) or {}
            self.assertIn(act.get('action'), ('chi', 'peng', 'gang', 'pass', 'hu'))
            got += 1
            if got >= 25:
                break
        self.assertGreater(got, 0, "需要真实窗口样本")



# ---- ★ R1502：役 3→役 5 候选链的孪生（此前一根都没有）----
#
# 为什么要钉这三件事：若正式赛 config 为 `YouCaiBiKao=true`，
# `tools/rules_guard.py` 会在**上线那一刻**动态实例化 `STRATEGY_FACTORIES[<arm>]()`、
# 读 `YOU_CAI_BI_KAO`；不一致 ⇒ `_switch_to_official.ps1` 直接 throw ⇒ **上不了线**。
# 所以：① 必须已注册（否则实例化失败）；② 必须与母臂**同剂量**（否则换的是另一根策略）；
# ③ 必须真的拦得住白-平胡（否则换了也是 409）。

CHAIN_TWINS = (
    (SpeedC151YCBK, "speedc151"),
    (SpeedValueBCYCBK, "speedvaluebc"),
    (SpeedValueBCVYCBK, "speedvaluebcv"),
    (SpeedValueBCMeldYCBK, "speedvaluebcmeld"),
    (SpeedValueBCMeldP45YCBK, "speedvaluebcmeldp45"),
    (SpeedValueBCVMeldYCBK, "speedvaluebcvmeld"),
    (SpeedValueBCVMeldP40YCBK, "speedvaluebcvmeldp40"),
    (SpeedValueBCVMeldP35YCBK, "speedvaluebcvmeldp35"),
    (SpeedValueMeldYCBK, "speedvaluemeld"),
    (SpeedValueMeldP45YCBK, "speedvaluemeldp45"),
    (SpeedValueMeldP40YCBK, "speedvaluemeldp40"),
    (SpeedValueBaotouV5YCBK, "speedvaluebaotouv5"),
    (SpeedValueBaotouVMeldYCBK, "speedvaluebaotouvmeld"),
)


class TestYCBKChainTwins(unittest.TestCase):
    def _factories(self):
        from run_bot import STRATEGY_FACTORIES as F
        return F

    def test_registered(self):
        F = self._factories()
        missing = [tw().name for tw, _b in CHAIN_TWINS if tw().name not in F]
        self.assertEqual([], missing,
                         "孪生**类写了但没注册** ⇒ rules_guard 实例化不了 ⇒ 上线仍 throw：%s" % missing)

    def test_same_dose_as_mother_arm(self):
        F = self._factories()
        for tw, base_name in CHAIN_TWINS:
            a, b = F[tw().name](), F[base_name]()
            self.assertIsInstance(a, FastYCBKMixin)
            self.assertTrue(a.YOU_CAI_BI_KAO)
            self.assertFalse(a.GOD_MELD)
            for knob in ("claim_p", "margin", "shanten_lo", "shanten_hi"):
                if hasattr(b, knob):
                    self.assertEqual(getattr(b, knob), getattr(a, knob),
                                     "%s.%s 与母臂 %s 不一致" % (tw.__name__, knob, base_name))

    def test_gate_blocks_the_illegal_win_for_every_chain_twin(self):
        v = view()
        F = self._factories()
        for base_name in sorted({b for _t, b in CHAIN_TWINS}):
            self.assertEqual("hu", (F[base_name]().decide(v) or {}).get("action"),
                             "母臂 %s 在这手牌上不宣胡 ⇒ 本用例对它没有鉴别力" % base_name)
        for tw, _b in CHAIN_TWINS:
            act = tw().decide(v) or {}
            self.assertNotEqual("hu", act.get("action"), "%s 没拦下白-平胡" % tw.__name__)
            self.assertEqual("discard", act.get("action"))
            self.assertIn(act.get("tile"), HAND)


if __name__ == '__main__':
    unittest.main(verbosity=2)


def setUpModule():
    """★ R1346：**无真实语料就整模块跳过**（clone / CI）。

    为什么：本模块的护栏都要在**真实对局记录**（`var/replays/**/*.dec.jsonl`）上取窗口；
    语料不在时它们会报“取不到真实吃牌窗口”这类**假失败**，把真问题淹没。
    `var/` 不在仓库里（.gitignore）⇒ 刚 clone 下来必定无语料，这里明确“跳过”而不是“失败”。
    本地（有语料）行为不变。
    """
    import os as _os
    import unittest as _ut
    _root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    _rep = _os.path.join(_root, "var", "replays")
    _has = False
    if _os.path.isdir(_rep):
        for _dp, _dn, _fn in _os.walk(_rep):
            if any(_x.endswith(".dec.jsonl") for _x in _fn):
                _has = True
                break
    if not _has:
        raise _ut.SkipTest("无真实语料 var/replays/**/*.dec.jsonl（clone/CI）⇒ 跳过本模块")
