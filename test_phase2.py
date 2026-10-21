import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import bot
from database import MemberRepository


class PhaseTwoDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "members.db"
        self.repository = MemberRepository(self.database_path)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def create_member(self, user_id: int = 1, referred_by: str | None = None):
        return self.repository.create_member(
            bale_user_id=user_id,
            chat_id=user_id,
            display_name="کاربر نمونه",
            university="دانشگاه نمونه",
            role="student",
            participation="member",
            notification="important",
            referred_by=referred_by,
        )

    def test_create_read_and_update_member(self):
        member = self.create_member()
        self.assertTrue(member.membership_number.startswith("SH-"))
        self.assertTrue(member.referral_code.startswith("R-"))
        self.assertEqual("pending", member.status)
        updated = self.repository.update_member(1, "display_name", "نام جدید")
        self.assertEqual("نام جدید", updated.display_name)

    def test_referral_is_counted(self):
        referrer = self.create_member(1)
        invited = self.create_member(2, referred_by=referrer.referral_code)
        self.assertEqual(referrer.referral_code, invited.referred_by)
        self.assertEqual(1, self.repository.count_referrals(referrer.referral_code))

    def test_unknown_referral_is_not_stored(self):
        member = self.create_member(1, referred_by="R-NOT-VALID")
        self.assertIsNone(member.referred_by)

    def test_sensitive_identity_columns_do_not_exist(self):
        connection = sqlite3.connect(self.database_path)
        try:
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(members)").fetchall()
            }
        finally:
            connection.close()
        self.assertFalse({"national_id", "student_id", "card_number", "phone"} & columns)

    def test_disallows_updating_unapproved_columns(self):
        self.create_member()
        with self.assertRaises(ValueError):
            self.repository.update_member(1, "status", "active")

    def test_workshop_interest_is_idempotently_updated(self):
        self.repository.save_workshop_interest(
            bale_user_id=1, chat_id=1, topic="programming", attendance_mode="online"
        )
        self.repository.save_workshop_interest(
            bale_user_id=1, chat_id=1, topic="programming", attendance_mode="either"
        )
        interests = self.repository.list_workshop_interests(1)
        self.assertEqual(1, len(interests))
        self.assertEqual("either", interests[0]["attendance_mode"])

    def test_branch_interest_is_idempotently_updated(self):
        self.repository.save_branch_interest(
            bale_user_id=1,
            chat_id=1,
            university="دانشگاه نمونه",
            team_role="local_coordination",
            availability="monthly",
        )
        self.repository.save_branch_interest(
            bale_user_id=1,
            chat_id=1,
            university="دانشگاه نمونه",
            team_role="workshops",
            availability="online",
        )
        interests = self.repository.list_branch_interests(1)
        self.assertEqual(1, len(interests))
        self.assertEqual("workshops", interests[0]["team_role"])
        self.assertEqual("pending", interests[0]["status"])


class PhaseTwoBotFlowTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.old_repository = bot._member_repository
        bot._member_repository = MemberRepository(Path(self.temporary_directory.name) / "flow.db")
        bot.MEMBER_SESSIONS.clear()
        bot.PENDING_REFERRALS.clear()

    def tearDown(self):
        bot._member_repository = self.old_repository
        bot.MEMBER_SESSIONS.clear()
        bot.PENDING_REFERRALS.clear()
        self.temporary_directory.cleanup()

    @staticmethod
    def query(data: str, user_id: int = 20) -> dict:
        return {
            "id": "callback-2",
            "data": data,
            "from": {"id": user_id},
            "message": {"message_id": 30, "chat": {"id": user_id}},
        }

    @staticmethod
    def message(text: str, user_id: int = 20) -> dict:
        return {"text": text, "from": {"id": user_id}, "chat": {"id": user_id}}

    def finish_registration(self, user_id: int = 20):
        bot.handle_callback_query(self.query("member:start", user_id))
        bot.handle_callback_query(self.query("member:consent", user_id))
        bot.handle_message(self.message("همیار نمونه", user_id))
        bot.handle_message(self.message("دانشگاه نمونه", user_id))
        bot.handle_callback_query(self.query("member:pick:role:student", user_id))
        bot.handle_callback_query(self.query("member:pick:participation:member", user_id))
        bot.handle_callback_query(self.query("member:pick:notification:important", user_id))
        bot.handle_callback_query(self.query("member:confirm", user_id))

    @patch.object(bot, "send_message")
    @patch.object(bot, "show_screen")
    @patch.object(bot, "answer_callback_query")
    def test_complete_registration_and_prevent_duplicate(self, _answer, _screen, _send):
        self.finish_registration()
        member = bot.get_member_repository().get_member(20)
        self.assertIsNotNone(member)
        self.assertEqual("همیار نمونه", member.display_name)
        bot.handle_callback_query(self.query("member:start"))
        self.assertEqual(member, bot.get_member_repository().get_member(20))

    @patch.object(bot, "send_message")
    @patch.object(bot, "show_screen")
    @patch.object(bot, "answer_callback_query")
    def test_edit_text_and_choice_fields(self, _answer, _screen, _send):
        self.finish_registration()
        bot.handle_callback_query(self.query("member:editfield:display_name"))
        bot.handle_message(self.message("نام ویرایش‌شده"))
        bot.handle_callback_query(self.query("member:update:role:supporter"))
        member = bot.get_member_repository().get_member(20)
        self.assertEqual("نام ویرایش‌شده", member.display_name)
        self.assertEqual("supporter", member.role)

    @patch.object(bot, "send_message")
    @patch.object(bot, "show_screen")
    @patch.object(bot, "answer_callback_query")
    def test_referral_from_start_command_is_persisted(self, _answer, _screen, _send):
        self.finish_registration(20)
        referrer = bot.get_member_repository().get_member(20)
        bot.handle_message(self.message(f"/start ref_{referrer.referral_code}", 21))
        self.finish_registration(21)
        invited = bot.get_member_repository().get_member(21)
        self.assertEqual(referrer.referral_code, invited.referred_by)
        self.assertEqual(1, bot.get_member_repository().count_referrals(referrer.referral_code))

    @patch.object(bot, "send_message")
    def test_invalid_profile_text_is_rejected(self, send_mock):
        bot.MEMBER_SESSIONS[bot.form_session_key(20, 20)] = {
            "mode": "register",
            "step": "display_name",
            "answers": {},
            "referred_by": None,
        }
        self.assertTrue(bot.process_member_text(self.message("x")))
        self.assertEqual("display_name", bot.MEMBER_SESSIONS[("20", "20")]["step"])
        send_mock.assert_called_once()

    @patch.object(bot, "show_screen")
    @patch.object(bot, "answer_callback_query")
    def test_workshop_interest_flow_persists_and_can_be_viewed(self, _answer, screen_mock):
        bot.handle_callback_query(self.query("form:start:workshop"))
        bot.handle_callback_query(self.query("form:pick:workshop:topic:programming"))
        bot.handle_callback_query(self.query("form:pick:workshop:attendance:online"))
        bot.handle_callback_query(self.query("form:confirm"))

        interests = bot.get_member_repository().list_workshop_interests(20)
        self.assertEqual("programming", interests[0]["topic"])
        self.assertEqual("online", interests[0]["attendance_mode"])
        self.assertIn("هیچ وجهی دریافت نشده", screen_mock.call_args.args[2])

        bot.handle_callback_query(self.query("phase3:my_workshops"))
        self.assertIn("برنامه‌نویسی", screen_mock.call_args.args[2])

    @patch.object(bot, "show_screen")
    @patch.object(bot, "answer_callback_query")
    def test_branch_interest_requires_member_and_uses_profile_university(self, _answer, screen_mock):
        bot.handle_callback_query(self.query("form:start:branch", user_id=99))
        self.assertNotIn(bot.form_session_key(99, 99), bot.FORM_SESSIONS)
        self.assertIn("ابتدا پروفایل عضویت", screen_mock.call_args.args[2])

        self.finish_registration(20)
        bot.handle_callback_query(self.query("form:start:branch"))
        bot.handle_callback_query(self.query("form:pick:branch:team_role:local_coordination"))
        bot.handle_callback_query(self.query("form:pick:branch:availability:monthly"))
        bot.handle_callback_query(self.query("form:confirm"))

        interests = bot.get_member_repository().list_branch_interests(20)
        self.assertEqual("دانشگاه نمونه", interests[0]["university"])
        self.assertEqual("local_coordination", interests[0]["team_role"])
        self.assertIn("دانشگاه نمونه", screen_mock.call_args.args[2])

        bot.handle_callback_query(self.query("phase3:my_branches"))
        self.assertIn("هماهنگی محلی", screen_mock.call_args.args[2])


if __name__ == "__main__":
    unittest.main()
