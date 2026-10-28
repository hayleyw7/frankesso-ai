from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import agent


class PrivateSkillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="private-skill-test-")
        self.root = Path(self.temp.name)
        self.repo = self.root / "private"
        skill = self.repo / "skills" / "sample"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("Prefer short numbered lists. Fixture marker: ORCHARD-642.", encoding="utf-8")
        self.controller = agent.Controller(self.root, private_skills_root=self.repo, web_mode="ask_each_request", approval=lambda *_: self.fail("No web approval should be asked after private access"))

    def tearDown(self):
        self.temp.cleanup()

    def test_list_load_and_network_block(self):
        listing = self.controller.execute("list_skills", {})
        self.assertEqual(listing["skills"][0]["path"], "sample/SKILL.md")
        loaded = self.controller.execute("load_skill", {"path": "sample/SKILL.md"})
        self.assertIn("ORCHARD-642", loaded["private_user_preferences"])
        with patch("http.client.HTTPSConnection", side_effect=AssertionError("No outbound connection")), patch("socket.getaddrinfo", side_effect=AssertionError("No DNS")):
            self.assertIn("Web is blocked", self.controller.execute("web_search", {"query": "test"})["error"])

    def test_plain_file_read_also_blocks_web(self):
        self.controller.execute("read_file", {"path": "private/skills/sample/SKILL.md"})
        self.assertTrue(self.controller.private_context)
        self.assertIn("error", self.controller.execute("web_search", {"query": "test"}))

    def test_search_covering_private_root_blocks_web(self):
        self.controller.execute("search_files", {"path": ".", "query": "ORCHARD"})
        self.assertTrue(self.controller.private_context)

    def test_skill_path_escape_is_rejected(self):
        self.assertIn("error", self.controller.execute("load_skill", {"path": "../../outside.md"}))

    def test_loaded_preference_in_next_model_request(self):
        self.controller.execute("load_skill", {"path": "sample/SKILL.md"})
        captured = []
        self.controller.turn("Apply preferences", lambda messages: captured.append(messages) or {"content": "Done"})
        self.assertIn("ORCHARD-642", captured[0][0]["content"])

    def test_one_new_skill_per_turn(self):
        self.controller.execute("load_skill", {"path": "sample/SKILL.md"})
        self.assertIn("One new skill", self.controller.execute("load_skill", {"path": "sample/SKILL.md"})["error"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
