"""Unit tests for LC Skill Plugin System."""
import tempfile
import unittest
from pathlib import Path
from lc.engine.skills import SkillManager


class TestSkillManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.skills_dir = Path(self.temp_dir.name)
        self.sm = SkillManager(skills_dir=self.skills_dir)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_scaffold_and_discover_skill(self):
        # Scaffold a new skill
        folder = SkillManager.create_skill_template("test_skill", skills_dir=self.skills_dir)
        self.assertTrue((folder / "SKILL.md").exists())
        self.assertTrue((folder / "skill.py").exists())

        # Discover it
        skills = self.sm.discover()
        self.assertEqual(len(skills), 1)
        self.assertEqual(skills[0].name, "test_skill")
        self.assertIsNotNone(skills[0].run)

        # Context generation
        context = self.sm.get_prompt_context()
        self.assertIn("[SKILL: test_skill]", context)


if __name__ == "__main__":
    unittest.main()
