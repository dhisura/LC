"""Unit tests for LC Skill Plugin System."""
import tempfile
import unittest
from pathlib import Path

from lc.engine.skills import SkillManager, _bundled_skills_dir


class TestSkillManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.skills_dir = Path(self.temp_dir.name)
        self.sm = SkillManager(skills_dir=self.skills_dir)
        # Point the bundled lookup at an empty dir so these tests assert only on
        # the local dir; bundled-skill discovery is covered separately below.
        self.sm.bundled_dir = self.temp_dir.name

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

    def test_private_and_dotfolders_skipped(self):
        (self.skills_dir / "_hidden").mkdir()
        (self.skills_dir / ".dotdir").mkdir()
        (self.skills_dir / "visible").mkdir()
        (self.skills_dir / "visible" / "SKILL.md").write_text("# visible", encoding="utf-8")

        names = [s.name for s in self.sm.discover()]
        self.assertEqual(names, ["visible"])

    def test_skill_without_md_still_loads(self):
        folder = self.skills_dir / "bare"
        folder.mkdir()
        skills = self.sm.discover()
        self.assertEqual(len(skills), 1)
        self.assertIn("bare", skills[0].description)


class TestBundledSkills(unittest.TestCase):
    """The repo's skills/ folder must actually be discovered, not dead weight."""

    def test_bundled_dir_exists_in_repo(self):
        bundled = _bundled_skills_dir()
        self.assertTrue(bundled.is_dir(), f"expected a bundled skills dir, got {bundled}")
        self.assertEqual(bundled.name, "skills")

    def test_bundled_skills_are_discovered(self):
        sm = SkillManager()
        skills = sm.discover()
        names = {s.name for s in skills}
        self.assertIn("github_deploy", names)
        self.assertIn("git_cleaner", names)

    def test_local_dir_overrides_bundled_on_name_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp)
            bundled = local / "bundled"
            override = local / "override"
            bundled.mkdir()
            override.mkdir()

            (bundled / "dup").mkdir()
            (bundled / "dup" / "SKILL.md").write_text("# from bundled", encoding="utf-8")
            (override / "dup").mkdir()
            (override / "dup" / "SKILL.md").write_text("# from local", encoding="utf-8")

            sm = SkillManager(skills_dir=override)
            sm.bundled_dir = bundled
            skills = {s.name: s for s in sm.discover()}

            self.assertEqual(len(skills), 1)
            self.assertIn("from local", skills["dup"].description)


if __name__ == "__main__":
    unittest.main()
