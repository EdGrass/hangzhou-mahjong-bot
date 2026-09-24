# -*- coding: utf-8 -*-
"""Replay-model self-tests: the reconstruction must be error-free and the canonical
metrics must stay in plausible bands (this is the failure mode that produced
mutually inconsistent counts in earlier ad-hoc scripts).

usage: python -X utf8 tests/test_replay_model.py -v
"""
import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
_spec = importlib.util.spec_from_file_location(
    'replay_model', os.path.join(ROOT, 'var', '_replay_model.py'))
RM = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(RM)


class TestReplayModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.idx = RM.room_files()
        cls.rooms = sorted(cls.idx)[:12]

    def test_reconstruction_has_no_errors(self):
        blocks, errs, samples = RM.validate(12)
        self.assertGreater(blocks, 100, "sample too small")
        self.assertEqual(errs, 0, "reconstruction errors: %s" % (samples,))

    def test_chi_is_always_from_the_upstream_seat(self):
        bad = tot = 0
        for r in self.rooms:
            for rec in RM.iter_rounds(self.idx[r]):
                last = None
                for e, _h, _m, _d in rec['snapshots']:
                    t = e.get('type')
                    if t == 'tile_drawn':
                        last = None
                    elif t == 'tile_discarded':
                        last = e.get('seat')
                    elif t == 'chi':
                        tot += 1
                        if last is None or (e.get('seat') - last) % 4 != 1:
                            bad += 1
                    elif t in ('peng', 'gang'):
                        pass
        self.assertGreater(tot, 50, "need chi samples")
        self.assertEqual(bad, 0, "chi must come from the upstream seat")

    def test_canonical_metrics_in_plausible_bands(self):
        rounds = wins = pengs = legal = 0
        for r in self.rooms:
            for rec in RM.iter_rounds(self.idx[r]):
                rounds += 1
                wins += 1 if rec['my_win'] else 0
                pengs += RM.peng_claims(rec)
                prev = None
                for e, hands, _m, _d in rec['snapshots']:
                    if e.get('type') == 'tile_discarded' and prev is not None \
                            and e.get('seat') != rec['me']:
                        tile = e.get('tile')
                        h = prev[1][rec['me']]
                        if tile and h.count(tile) >= 2:
                            legal += 1
                    prev = (e, hands, _m, _d)
        self.assertGreater(rounds, 100)
        # NOTE units: legal peng windows are ~0.8 per ROUND (= ~65 per room of 80
        # rounds), our pengs ~0.47/round; earlier ad-hoc scripts mixed per-round and
        # per-room units, which is exactly what these bands are here to catch.
        self.assertTrue(0.15 <= wins / rounds <= 0.35, "win rate out of band: %.3f" % (wins / rounds))
        self.assertTrue(0.25 <= pengs / rounds <= 0.70, "peng/round out of band: %.3f" % (pengs / rounds))
        self.assertTrue(0.40 <= legal / rounds <= 1.30, "legal windows/round out of band: %.2f" % (legal / rounds))
        rate = pengs / legal if legal else 0
        self.assertTrue(0.35 <= rate <= 0.85, "peng realisation rate out of band: %.3f" % rate)


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
