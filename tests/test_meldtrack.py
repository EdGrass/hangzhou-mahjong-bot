"""bot/meldtrack 单测。"""
import unittest

from bot.meldtrack import MeldTracker


class TestMeldTracker(unittest.TestCase):
    def test_peng_chi_count(self):
        t = MeldTracker()
        t.record_action({"action": "peng", "tile": "5w"})
        t.record_action({"action": "chi", "tile": "3b"})
        self.assertEqual(t.exposed(), 2)
        self.assertEqual(t.gangs(), 0)

    def test_ankan_increments_both(self):
        t = MeldTracker()
        t.record_action({"action": "gang", "tile": "1w"})   # 暗杠
        self.assertEqual(t.exposed(), 1)
        self.assertEqual(t.gangs(), 1)

    def test_bugang_upgrades_peng(self):
        t = MeldTracker()
        t.record_action({"action": "peng", "tile": "5w"})
        t.record_action({"action": "gang", "tile": "5w"})   # 补杠：命中碰组
        self.assertEqual(t.exposed(), 1)                    # 面子数不变
        self.assertEqual(t.gangs(), 1)

    def test_minggang_from_discard(self):
        t = MeldTracker()
        t.record_action({"action": "gang", "tile": "东"})    # 手牌三张直杠
        self.assertEqual(t.exposed(), 1)
        self.assertEqual(t.gangs(), 1)

    def test_ignore_pass_discard_hu(self):
        t = MeldTracker()
        t.record_action({"action": "discard", "tile": "5w"})
        t.record_action({"action": "hu"})
        t.record_action({"action": "pass", "tile": ""})
        self.assertEqual(t.exposed(), 0)
        self.assertEqual(t.gangs(), 0)

    def test_not_committed_ignored(self):
        t = MeldTracker()
        t.record_action({"action": "peng", "tile": "5w"}, committed=False)
        self.assertEqual(t.exposed(), 0)

    def test_white_gang_defensive(self):
        # 客户端不提交白板(财神)杠，但防御记录时 view_extra 不得崩
        t = MeldTracker()
        t.record_action({"action": "gang", "tile": "白"})
        self.assertEqual(t.gangs(), 1)
        v = t.view_extra()
        self.assertEqual(v["melds"][-1]["tile"], "白")
        self.assertEqual(v["melds"][-1]["type"], "gang")

    def test_bugang_does_not_add_new_meld(self):
        # 已有碰组后补杠：只升杠，不新增面子里数（e 不变、g+1）
        t = MeldTracker()
        t.record_action({"action": "peng", "tile": "3b"})
        t.record_action({"action": "peng", "tile": "7w"})
        t.record_action({"action": "gang", "tile": "3b"})   # 升第一个碰
        self.assertEqual(t.exposed(), 2)                    # e 仍 2
        self.assertEqual(t.gangs(), 1)
        melds = t.view_extra()["melds"]
        self.assertEqual(melds[0], {"type": "gang", "tile": "3b"})
        self.assertEqual(melds[1], {"type": "peng", "tile": "7w"})

    def test_retain_order_after_upgrade(self):
        # 升级只就地改 type，不改 meld 顺序/数量
        t = MeldTracker()
        t.record_action({"action": "peng", "tile": "5w"})
        t.record_action({"action": "gang", "tile": "5w"})
        self.assertEqual(t.view_extra()["melds"],
                         [{"type": "gang", "tile": "5w"}])
        self.assertEqual(t.gangs(), 1)
        self.assertEqual(t.exposed(), 1)

    def test_reset_and_view(self):
        t = MeldTracker()
        t.record_action({"action": "peng", "tile": "3t"})
        v = t.view_extra()
        self.assertEqual(len(v["melds"]), 1)
        t.reset()
        self.assertEqual(t.exposed(), 0)


if __name__ == "__main__":
    unittest.main()
