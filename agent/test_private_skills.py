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
        self.controller = agent.Controller(self.root, private_skills_root=self.repo)

    def tearDown(self):
        self.temp.cleanup()

    def test_list_load_marks_private_context(self):
        listing = self.controller.execute("list_skills", {})
        self.assertEqual(listing["skills"][0]["path"], "sample/SKILL.md")
        loaded = self.controller.execute("load_skill", {"path": "sample/SKILL.md"})
        self.assertIn("ORCHARD-642", loaded["private_user_preferences"])
        self.assertTrue(self.controller.private_context)

    def test_plain_file_read_marks_private_context(self):
        self.controller.execute("read_file", {"path": "private/skills/sample/SKILL.md"})
        self.assertTrue(self.controller.private_context)

    def test_search_covering_private_root_marks_private_context(self):
        self.controller.execute("search_files", {"path": ".", "query": "ORCHARD"})
        self.assertTrue(self.controller.private_context)

    def test_skill_path_escape_is_rejected(self):
        self.assertIn("error", self.controller.execute("load_skill", {"path": "../../outside.md"}))

    def test_skill_walk_prunes_reparse_directories_before_descending(self):
        junction = self.repo.resolve() / "skills" / "remote"
        junction.mkdir()
        (junction / "SKILL.md").write_text("Must not be read", encoding="utf-8")
        real = Path.lstat
        def lstat(path):
            if path == junction:
                return type("Info", (), {"st_mode": 0o040000, "st_file_attributes": 0x400})()
            self.assertNotIn(junction, path.parents)
            return real(path)
        with patch.object(Path, "lstat", lstat):
            listing = self.controller.execute("list_skills", {})
        self.assertEqual([entry["path"] for entry in listing["skills"]], ["sample/SKILL.md"])

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
