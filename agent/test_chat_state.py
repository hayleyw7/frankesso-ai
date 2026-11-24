from datetime import date
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import agent
import chat_state


class ChatTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.path = self.root / "chat-state"
        self.approve = Mock(return_value=True)
        self.controller = agent.Controller(self.root, approval=self.approve, chat_root=self.path)
        self.chat = self.controller.chat
        self.model = Mock(return_value={"content": "Plant under the oak."})
        self.reply = Mock(return_value={"content": "Label the pots."})

    def turn(self, prompt):
        return self.controller.chat_turn(prompt, self.model, self.reply)

    def test_device_date_refreshes_and_does_not_claim_live_event_knowledge(self):
        with patch.object(chat_state, "date", wraps=date) as clock:
            clock.today.return_value = date(2026, 12, 31)
            self.assertEqual(self.turn("What’s today’s date?"), "Today is 2026-12-31.")
            self.assertEqual(self.turn("What year is it?"), "The current year is 2026.")
            self.model.assert_not_called()
            self.turn("What's happening this week?")
            first = self.model.call_args.args[0][0]["content"]
            self.assertIn("The device's local date is 2026-12-31.", first)
            self.assertIn("This gives the date only. It does not verify current events.", first)
            clock.today.return_value = date(2027, 1, 1)
            self.assertEqual(self.turn("What's the date today?"), "Today is 2027-01-01.")
            self.assertEqual(self.turn("What year is it?"), "The current year is 2027.")
            self.turn("Let's talk: Replanting herbs.")
            second = self.reply.call_args.args[0][0]["content"]
            self.assertIn("The device's local date is 2027-01-01.", second)
            self.assertNotIn("2026-12-31", second)

    def test_general_and_advice_requests_receive_the_direct_answer_policy(self):
        self.turn("Tell me about Jupiter.")
        self.turn("Let's talk: Replanting herbs.")
        for request in (self.model, self.reply):
            messages = request.call_args.args[0]
            self.assertEqual(messages[0]["role"], "system")
            for rule in ("Answer the question directly.", "If unsure, say so. Do not invent facts.",
                         "Never use your persona to avoid answering.",
                         "Do not introduce yourself or mention your identity or lore unless asked."):
                self.assertIn(rule, messages[0]["content"])

    def test_manual_memory_persists_and_forgets_without_changing_history(self):
        self.turn("Sketch a leaf.")
        chat_id = self.chat.chat_id
        self.assertEqual(self.chat.notes(), [])
        self.turn("Remember this: Paint the garden signs teal.")
        self.turn("remember this: PAINT THE GARDEN SIGNS TEAL.")
        clone = agent.Controller(self.root, chat_root=self.path).chat
        note = clone.notes()[0]
        self.assertEqual(len(clone.notes()), 1)
        self.assertEqual(note["text"], "Paint the garden signs teal.")
        self.assertIn(chat_id, self.turn("/chats"))
        self.assertEqual(self.turn("/new"), "New chat.")
        self.assertIn("Sketch a leaf.", self.turn("/open " + chat_id))
        self.assertIn(note["id"], self.turn("/memories"))
        with self.assertRaises(ValueError):
            self.turn("Forget Paint")
        self.turn("Forget " + note["id"])
        self.assertEqual(self.turn("/memories"), "No saved notes.")
        self.assertIn("Sketch a leaf.", self.turn("/open " + chat_id))
        self.turn("/delete " + chat_id)
        self.assertEqual(self.turn("/chats"), "No saved chats.")
        self.assertEqual(self.model.call_count, 1)

    def test_context_text_only_cannot_replay_tools_or_request_the_web(self):
        self.chat.save_turn("Search for garden notes.", "A historical write request.")
        self.turn("Remember this: Secret color is chartreuse.")
        self.model.side_effect = lambda messages: self.assert_not_in_tool_request(messages)
        self.reply.return_value = {"tool_calls": [{"function": {
            "name": "web_search", "arguments": '{"query":"chartreuse"}'}}]}
        self.assertIn("No action taken", self.turn("How should I label the pots?"))
        context = self.reply.call_args.args[0]
        self.assertIn("chartreuse", str(context))
        self.assertIn("historical write request", str(context))
        self.assertFalse(self.approve.called)

    def assert_not_in_tool_request(self, messages):
        self.assertNotIn("chartreuse", str(messages))
        self.assertNotIn("historical write request", str(messages))
        return {"content": "A new reply."}

    def test_tools_and_approval_text_are_not_persisted(self):
        self.model.side_effect = [
            {"tool_calls": [{"id": "read", "function": {
                "name": "list_files", "arguments": '{"path":"."}'}}]},
            {"content": "A summary of local files."},
        ]
        self.turn("List my sketch files.")
        self.turn("APPROVE ONCE")
        self.assertEqual(self.chat.messages, [])
        self.assertEqual(self.chat.chats(), [])
        self.assertFalse(self.approve.called)

    def test_easter_egg_is_local_and_only_matches_standalone_test(self):
        expected = "Signal received from the other side. Something knocked back. ☕"
        self.assertEqual(self.turn("test"), expected)
        self.assertEqual(self.turn("  TEST  "), expected)
        self.model.assert_not_called()
        self.reply.assert_not_called()
        self.approve.assert_not_called()
        self.assertNotEqual(self.turn("run the tests"), expected)
        self.model.assert_called_once()

    def test_favorites_are_exact_standalone_and_do_not_access_storage(self):
        expected = "Crimson. It’s the only color that makes it through the portal intact."
        with patch.object(self.chat, "context", side_effect=AssertionError("Unexpected read")), \
                patch.object(self.chat, "save_turn", side_effect=AssertionError("Unexpected write")):
            for question in ("What's your favorite color?", "What’s your favourite colour?",
                             "WHAT IS YOUR FAVORITE COLOUR!", "  favorite color?  "):
                self.assertEqual(self.turn(question), expected)
            for question in ("favorite food?", "What is your favourite drink?", "What's your favorite food or drink?"):
                self.assertEqual(self.turn(question), "Coffee.")
            self.assertEqual(self.turn("WHAT’S YOUR FAVOURITE DRUG?"), "Caffeine.")
            self.assertEqual(self.turn("What's your favourite weather?"),
                             "Fog.")
            self.assertEqual(self.turn("What is your biggest pet peeve?"),
                             "Decaf.")
            self.assertEqual(self.turn("pet peeve?"), "Decaf.")
            self.assertEqual(self.turn("WHERE ARE YOU FROM?"), "The side of the mirror that stays warm.")
            self.assertEqual(self.turn("What's your favorite time of day?"), "Night.")
            for question in ("Favorite exact time?", "What is your favourite clock time?",
                             "What's your favorite hour?", "What exact time is your favourite?"):
                self.assertEqual(self.turn(question), "Midnight.")
        self.model.assert_not_called()
        self.reply.assert_not_called()
        self.approve.assert_not_called()
        self.assertEqual(self.turn("test"), "Signal received from the other side. Something knocked back. ☕")
        self.assertNotEqual(self.turn("Run a tool to check the favorite color setting."), expected)
        self.assertNotEqual(self.turn("What's your favorite drug, and which use would you recommend?"), "Caffeine.")
        self.assertIsNone(chat_state.direct_response("What's the weather outside?"))
        self.assertIsNone(chat_state.direct_response("What time is it?"))
        self.assertIsNone(chat_state.direct_response("What's your favorite hour? Also, set a reminder."))
        self.assertIsNone(chat_state.direct_response("Where are you from and how do I uninstall Frankesso?"))
        self.assertIsNone(chat_state.direct_response("My biggest pet peeve is the app freezing. Help."))
        self.assertTrue(self.model.called)

    def test_modes_are_advice_only(self):
        for prompt in ("Just the diff: Change the pot color.", "Let’s talk: Replanting herbs."):
            self.assertEqual(self.turn(prompt), "Label the pots.")
        self.assertFalse(self.model.called)
        self.assertFalse(self.approve.called)
        self.assertEqual(self.reply.call_count, 2)

    def test_storage_is_outside_file_tools_and_bounded(self):
        self.chat.remember("Sketch a pot.")
        self.assertIn("error", self.controller.execute("read_file", {"path": "chat-state/notes.json"}))
        self.assertNotIn("notes.json", str(self.controller.execute("list_files", {"path": "."})))
        self.assertIn("error", self.controller.execute(
            "write_file", {"path": "chat-state/notes.json", "content": "[]"}))
        self.assertFalse(self.approve.called)
        with self.assertRaises(ValueError):
            self.chat.open("../notes")
        for index in range(20):
            self.chat.save_turn("x" * 8000 + str(index), "y" * 8000)
        self.assertLess(len(self.chat.context()), 1900)

    def test_text_request_omits_tool_schemas(self):
        with patch.object(agent.http.client, "HTTPConnection") as connect:
            response = connect.return_value.getresponse.return_value
            response.status = 200
            response.read.return_value = b'{"choices":[{"message":{"content":"A fern."}}]}'
            self.assertEqual(agent.text_request([]), {"content": "A fern."})
            payload = json.loads(connect.return_value.request.call_args.args[2])
            self.assertNotIn("tools", payload)
            self.assertNotIn("tool_choice", payload)


if __name__ == "__main__":
    unittest.main()
