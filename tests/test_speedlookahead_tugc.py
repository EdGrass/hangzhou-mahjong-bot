# -*- coding: utf-8 -*-
"""Guards for the pure TUGC lookahead candidate."""
import io, json, os, sys, unittest
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,ROOT); sys.path.insert(0,os.path.join(ROOT,'tools'))
from arm_smoke import to_view
from bot.speedtugc import SpeedTUGC
from bot.speedlookahead_tugc import SpeedLookaheadTUGC


def views(limit=300):
    out=[]
    with io.open(os.path.join(ROOT,'var','smoke_corpus_v1.jsonl'),encoding='utf-8') as fh:
        for line in fh:
            line=line.strip()
            if not line:continue
            r=json.loads(line)
            if r.get('p')=='draw' and len(r.get('h') or [])==14:
                out.append(to_view(r))
                if len(out)>=limit:break
    return out


class TestSpeedLookaheadTUGC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.views=views()
        cls.arm=SpeedLookaheadTUGC()
        cls.base=SpeedTUGC()

    def test_identity_and_scope(self):
        self.assertTrue(issubclass(SpeedLookaheadTUGC, SpeedTUGC))
        self.assertEqual(self.arm.name,'speedlookaheadtugc')
        self.assertIn(1,self.arm.PARAMS)
        self.assertIn(2,self.arm.PARAMS)

    def test_end_to_end(self):
        n=0
        for v in self.views[:120]:
            a=self.arm.decide(v)
            self.assertIsInstance(a,dict)
            self.assertIn('action',a)
            n+=1
        self.assertGreater(n,0)

    def test_deadline_fallback(self):
        checked=0
        old=self.arm.LOOK_DEADLINE_MS
        try:
            self.arm.LOOK_DEADLINE_MS=1e-9
            for v in self.views:
                h=list(v.get('my_hand') or [])
                if not h:continue
                a=self.arm._pick_discard(h,v.get('drawn_tile'),0,0,view=v)
                b=self.base._pick_discard(h,v.get('drawn_tile'),0,0,view=v)
                self.assertEqual(a,b)
                checked+=1
                if checked>=5:break
        finally:
            self.arm.LOOK_DEADLINE_MS=old
        self.assertGreater(checked,0)


if __name__=='__main__':
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
