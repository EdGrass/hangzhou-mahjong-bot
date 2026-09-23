"""v8 锦标赛状态机映射（tournament_intent）与终态判定的单测。"""
import unittest

from bot.protocol import tournament_intent

STAGE = {"no": 2, "role": "final", "total": 3, "name": "测试锦标赛-第2轮"}


class TestIntent(unittest.TestCase):
    def test_terminal(self):
        for s in ("finished", "closed", "void"):
            intent, why = tournament_intent({"status": s})
            self.assertEqual(intent, "exit", s)

    def test_registering(self):
        intent, _ = tournament_intent({"status": "registering"})
        self.assertEqual(intent, "register")

    def test_stage_open_qualified(self):
        for q in (True, "true", 1):
            intent, why = tournament_intent({"status": "stage_open", "qualified": q})
            self.assertEqual(intent, "confirm", q)
        # 阶段 1 崩溃重赛例外：qualified=true、role 空 → 仍应确认
        intent, why = tournament_intent(
            {"status": "stage_open", "qualified": True, "stage": {"no": 1, "role": ""}})
        self.assertEqual(intent, "confirm")

    def test_stage_open_not_qualified(self):
        for q in (False, "", None):
            intent, why = tournament_intent({"status": "stage_open", "qualified": q})
            self.assertEqual(intent, "eliminated", q)

    def test_stage_done_wait(self):
        intent, why = tournament_intent({"status": "stage_done", "stage": STAGE})
        self.assertEqual(intent, "wait")
        self.assertNotIn("中断", why)

    def test_stage_done_crashed(self):
        # 顶层 stage_crashed 与嵌套两种形态都要识别
        for t in ({"status": "stage_done", "stage_crashed": True},
                  {"status": "stage_done", "stage": {"crashed": True}}):
            intent, why = tournament_intent(t)
            self.assertEqual(intent, "wait")
            self.assertIn("中断", why)

    def test_running(self):
        intent, _ = tournament_intent({"status": "running", "stage": STAGE})
        self.assertEqual(intent, "play")

    def test_unknown_status(self):
        intent, _ = tournament_intent({"status": "brand_new_status_x"})
        self.assertEqual(intent, "unknown")


if __name__ == "__main__":
    unittest.main()
