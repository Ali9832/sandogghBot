import unittest
from unittest.mock import patch

import bot


class PhaseOneTests(unittest.TestCase):
    def setUp(self):
        bot.FORM_SESSIONS.clear()

    @staticmethod
    def query(data: str) -> dict:
        return {
            "id": "callback-1",
            "data": data,
            "from": {"id": 20},
            "message": {"message_id": 30, "chat": {"id": 10}},
        }

    def test_main_menu_is_inline_and_two_columns(self):
        keyboard = bot.main_menu_keyboard()
        self.assertIn("inline_keyboard", keyboard)
        self.assertEqual(4, len(keyboard["inline_keyboard"]))
        self.assertTrue(all(len(row) == 2 for row in keyboard["inline_keyboard"]))

    def test_every_section_has_back_to_main(self):
        for section in bot.SECTION_DESCRIPTIONS:
            keyboard = bot.submenu_keyboard(section)["inline_keyboard"]
            self.assertEqual("menu:main", keyboard[-1][0]["callback_data"])

    def test_callback_data_stays_within_bale_limit(self):
        callback_values = []
        for keyboard in [bot.main_menu_keyboard(), *(bot.submenu_keyboard(s) for s in bot.SUBMENU_ROWS)]:
            for row in keyboard["inline_keyboard"]:
                for button in row:
                    if "callback_data" in button:
                        callback_values.append(button["callback_data"])
        for flow, spec in bot.FORM_SPECS.items():
            for key, _, options in spec["steps"]:
                callback_values.extend(
                    f"form:pick:{flow}:{key}:{value}" for _, value in options
                )
        self.assertTrue(callback_values)
        self.assertTrue(all(len(value.encode("utf-8")) <= 64 for value in callback_values))

    def test_demo_forms_do_not_request_sensitive_fields(self):
        forbidden = {"name", "phone", "national_id", "student_id", "card", "account"}
        for spec in bot.FORM_SPECS.values():
            keys = {key for key, _, _ in spec["steps"]}
            self.assertFalse(keys & forbidden)

    def test_every_action_button_has_content(self):
        action_targets = {
            target.removeprefix("action:")
            for rows in bot.SUBMENU_ROWS.values()
            for row in rows
            for _, target in row
            if target.startswith("action:")
        }
        self.assertEqual(action_targets, set(bot.ACTION_MESSAGES))

    @patch.object(bot, "show_screen")
    @patch.object(bot, "answer_callback_query")
    def test_every_demo_form_can_reach_confirmation(self, _answer_mock, _screen_mock):
        session_key = bot.form_session_key(10, 20)
        for flow, spec in bot.FORM_SPECS.items():
            bot.handle_callback_query(self.query(f"form:start:{flow}"))
            for key, _, options in spec["steps"]:
                value = options[0][1]
                bot.handle_callback_query(self.query(f"form:pick:{flow}:{key}:{value}"))
            self.assertEqual(len(spec["steps"]), bot.FORM_SESSIONS[session_key]["step"])
            bot.handle_callback_query(self.query("form:confirm"))
            self.assertNotIn(session_key, bot.FORM_SESSIONS)

    @patch.object(bot, "show_screen")
    @patch.object(bot, "answer_callback_query")
    def test_member_form_can_finish_and_clears_memory(self, answer_mock, screen_mock):
        bot.handle_callback_query(self.query("form:start:member"))
        session_key = bot.form_session_key(10, 20)
        self.assertIn(session_key, bot.FORM_SESSIONS)

        bot.handle_callback_query(self.query("form:pick:member:role:student"))
        bot.handle_callback_query(self.query("form:pick:member:participation:member"))
        bot.handle_callback_query(self.query("form:pick:member:notification:bale"))
        self.assertEqual(3, bot.FORM_SESSIONS[session_key]["step"])

        bot.handle_callback_query(self.query("form:confirm"))
        self.assertNotIn(session_key, bot.FORM_SESSIONS)
        self.assertEqual(5, answer_mock.call_count)
        self.assertEqual(5, screen_mock.call_count)

    @patch.object(bot, "show_screen")
    @patch.object(bot, "answer_callback_query")
    def test_form_back_and_cancel(self, _answer_mock, _screen_mock):
        bot.handle_callback_query(self.query("form:start:loan"))
        bot.handle_callback_query(self.query("form:pick:loan:type:urgent"))
        bot.handle_callback_query(self.query("form:back"))
        state = bot.FORM_SESSIONS[bot.form_session_key(10, 20)]
        self.assertEqual(0, state["step"])
        self.assertEqual({}, state["answers"])
        bot.handle_callback_query(self.query("form:cancel"))
        self.assertFalse(bot.FORM_SESSIONS)


if __name__ == "__main__":
    unittest.main()
