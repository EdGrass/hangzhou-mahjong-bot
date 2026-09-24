# -*- coding: utf-8 -*-
"""自包含门（R1346）：依赖真实对局语料（var/replays）的测试模块，必须自带“无语料则跳过”的门。

为什么（本轮实测）：公网 clone（无 var/ 状态）跑全量单测 ⇒ 910 条里 66 条失败/错误，
全是“取不到真实吃牌窗口”这类假失败（语料不在）。假失败比跳过更坏：它会**淹没真问题**，
也让判官看到一堆红。本门把归因模式固定下来：**要么自带语料，要么自带跳过门**。

名单是**实测出来的**：公网 clone 里报失败/错误的那 26 个模块（它们都要在真实对局记录上取窗口）。
不用“文件名/关键字”启发式匹配：实测过，它会误伤 10 个“只是文档里提到 replays”的模块。
"""
import io
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(ROOT, "tests")
GUARD = ("def setUpModule", "skipUnless", "skipIf", "skipTest")

_RE_SHUFFLE_FILES = re.compile(r"shuffle\(\s*files\s*\)")

CORPUS_MODULES = (
    "test_replay_guard",
    "test_speedc151b",
    "test_speedc151c",
    "test_speedc151m",
    "test_speedc221",
    "test_speedc135d",
    "test_speedmeldtier",
    "test_speedc230",
    "test_speedgiveup",
    "test_speedmeldmore0chi",
    "test_speedc161",
    "test_speedvaluemeldmore0chi",
    "test_speedlookahead",
    "test_speedlookahead_anytime",
    "test_speedlookahead_tugc",
    "test_speedroute",
    "test_speedroutekeep",
    "test_speedstack",
    "test_speedtenpai",
    "test_speedvalue",
    "test_ycbk_twins",
    "test_arm_smoke",
    "test_speedc147",
    "test_speedmeldmore",
    "test_speedmeldtoldose",
    "test_replay_model",
    "test_speedc069",
    "test_speedvaluemeldmore0chigang",
    "test_speedc220"
)



def _modules():
    return [os.path.join(TESTS, f) for f in sorted(os.listdir(TESTS))
            if f.startswith("test_") and f.endswith(".py")]


class TestHermeticCorpusGate(unittest.TestCase):
    def test_list_is_complete(self):
        self.assertGreaterEqual(len(CORPUS_MODULES), 25, "名单被削掉了？本门是空跑")

    def test_no_shuffle_of_globbed_files(self):
        """★ R1347：**不要对“扫出来的文件列表”shuffle**。

        为什么：固定种子只能保证“同一个列表”的洗牌结果不变，而语料列表**每打一房就变长** ⇒
        抽到的 60 个局面会随新对局漂移 ⇒ 同一份代码会**时红时绿**。实测：`test_speedc151c::test_not_a_noop` 11:01 绿、
        11:33 红（期间只多了几个房间）。改成“按文件名有序扫描”后：前 N 个局面不受增长影响，
        且差异只会变多不会变少（单调）。
        """
        bad = []
        for p in _modules():
            with io.open(p, encoding="utf-8-sig", errors="replace") as f:
                src = f.read()
            if _RE_SHUFFLE_FILES.search(src):
                bad.append(os.path.basename(p))
        self.assertEqual([], bad,
                         "以下模块对“扫出来的文件列表”做了 shuffle ⇒ 样本会随语料增长漂移"
                         "（改成按文件名有序扫描）：%s" % bad)

    def test_corpus_modules_are_guarded(self):
        bad, missing = [], []
        for name in CORPUS_MODULES:
            p = os.path.join(TESTS, name + ".py")
            if not os.path.exists(p):
                missing.append(name)
                continue
            with io.open(p, encoding="utf-8-sig", errors="replace") as f:
                src = f.read()
            if not any(g in src for g in GUARD):
                bad.append(name)
        self.assertEqual([], missing, "名单里的模块不存在（名字改了？）：%s" % missing)
        self.assertEqual([], bad,
                         "以下模块依赖 var/replays 却没有跳过门 ⇒ clone/CI 里会报假失败"
                         "（加 setUpModule 或 skipUnless）：%s" % bad)


if __name__ == "__main__":
    unittest.main()
