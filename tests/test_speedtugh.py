"""C061 副露门控分档：向听<=2 mild，向听>=3 strict。"""
import unittest

import bot.speedtugh as m


class TestTieredClaim(unittest.TestCase):
    def setUp(self):
        self.view = {
            "offer_tile": "1w",
            "my_hand": ["1w"] * 13,
            "melds": [],
        }
        self.calls = []
        self._old_s = m.exact_shanten
        self._old_melds = m._melds_info
        self._old_mild = m.want_claim_mild
        m._melds_info = lambda view: (0, 0)
        m.want_claim_mild = lambda view, kind, allow_equal=True: (
            self.calls.append(allow_equal) or True)

    def tearDown(self):
        m.exact_shanten = self._old_s
        m._melds_info = self._old_melds
        m.want_claim_mild = self._old_mild

    def test_shanten_two_allows_equal_call(self):
        m.exact_shanten = lambda *a, **k: 2
        self.assertTrue(m.want_claim_tiered(self.view, "peng"))
        self.assertEqual(self.calls, [True])

    def test_shanten_three_requires_strict_call(self):
        m.exact_shanten = lambda *a, **k: 3
        self.assertTrue(m.want_claim_tiered(self.view, "peng"))
        self.assertEqual(self.calls, [False])


if __name__ == "__main__":
    unittest.main()
