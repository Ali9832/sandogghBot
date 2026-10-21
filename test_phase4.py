import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import bot
from database import MemberRepository


class PhaseFourTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.old_repository = bot._member_repository
        bot._member_repository = MemberRepository(Path(self.temporary_directory.name) / "phase4.db")
        bot.FORM_SESSIONS.clear()

    def tearDown(self):
        bot._member_repository = self.old_repository
        bot.FORM_SESSIONS.clear()
        self.temporary_directory.cleanup()

    @staticmethod
    def query(data: str) -> dict:
        return {
            "id": "callback-phase4",
            "data": data,
            "from": {"id": 41},
            "message": {"message_id": 42, "chat": {"id": 43}},
        }

    def test_interest_is_saved_and_can_be_viewed(self):
        with patch.object(bot, "show_screen"), patch.object(bot, "answer_callback_query"):
            bot.handle_callback_query(self.query("form:start:enterprise"))
            bot.handle_callback_query(
                self.query("form:pick:enterprise:idea_type:student_market")
            )
            bot.handle_callback_query(
                self.query("form:pick:enterprise:contribution:ideation")
            )
            bot.handle_callback_query(self.query("form:confirm"))

            interests = bot.get_member_repository().list_enterprise_interests(41)
            self.assertEqual(1, len(interests))
            self.assertEqual("student_market", interests[0]["idea_type"])
            self.assertEqual("ideation", interests[0]["contribution"])

            bot.handle_callback_query(self.query("phase4:my_enterprises"))
            self.assertIn(
                "بازارچهٔ دانشجویی",
                bot.show_screen.call_args.args[2],
            )

    def test_interest_upsert_does_not_duplicate(self):
        repository = bot.get_member_repository()
        repository.save_enterprise_interest(
            bale_user_id=41,
            chat_id=43,
            idea_type="student_market",
            contribution="ideation",
        )
        repository.save_enterprise_interest(
            bale_user_id=41,
            chat_id=43,
            idea_type="student_market",
            contribution="operations",
        )
        interests = repository.list_enterprise_interests(41)
        self.assertEqual(1, len(interests))
        self.assertEqual("operations", interests[0]["contribution"])


if __name__ == "__main__":
    unittest.main()
