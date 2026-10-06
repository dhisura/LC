"""Tests for the bundled github_deploy skill.

These never contact GitHub: the skill is exercised against a temp workspace and
asserted on its refusal/confirmation behaviour, which is where the safety
properties live.
"""
import importlib.util
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_PATH = REPO_ROOT / "skills" / "github_deploy" / "skill.py"


def _load_skill():
    spec = importlib.util.spec_from_file_location("github_deploy_skill", SKILL_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


skill = _load_skill()


class TestRefusals(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name)
        (self.ws / "index.html").write_text("<h1>hi</h1>", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_index_html_refused(self):
        (self.ws / "index.html").unlink()
        result = skill.run({"workspace": str(self.ws), "confirm": True})
        self.assertFalse(result["success"])
        self.assertIn("index.html", result["error"])

    def test_credential_files_block_deploy(self):
        # The whole point: publishing these would expose them permanently.
        (self.ws / ".env").write_text("SECRET=hunter2\n", encoding="utf-8")
        result = skill.run({"workspace": str(self.ws), "confirm": True})
        self.assertFalse(result["success"])
        self.assertIn("credential-like", result["error"])
        self.assertIn(".env", result["error"])

    def test_private_key_blocks_deploy(self):
        (self.ws / "id_rsa").write_text("-----BEGIN OPENSSH PRIVATE KEY-----\n", encoding="utf-8")
        result = skill.run({"workspace": str(self.ws), "confirm": True})
        self.assertFalse(result["success"])
        self.assertIn("credential-like", result["error"])

    def test_nested_repo_refused(self):
        # A site inside an existing checkout would be detached from its history.
        (self.ws / "parent").mkdir()
        (self.ws / "parent" / ".git").mkdir()
        site = self.ws / "parent" / "site"
        site.mkdir()
        (site / "index.html").write_text("<h1>hi</h1>", encoding="utf-8")

        result = skill.run({"workspace": str(site), "confirm": True})
        self.assertFalse(result["success"])
        self.assertIn("inside an existing git repository", result["error"])

    def test_invalid_repo_name_refused(self):
        for bad in ("../escape", "has space", "semi;colon", ""):
            with self.subTest(name=bad):
                result = skill.run({
                    "workspace": str(self.ws),
                    "repo_name": bad,
                    "confirm": True,
                })
                self.assertFalse(result["success"])
                self.assertIn("Invalid repository name", result["error"])

    def test_missing_workspace_refused(self):
        result = skill.run({"workspace": str(self.ws / "nope"), "confirm": True})
        self.assertFalse(result["success"])
        self.assertIn("does not exist", result["error"])


class TestConfirmationGate(unittest.TestCase):
    """No remote change may happen without an explicit confirm=True."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name)
        (self.ws / "index.html").write_text("<h1>hi</h1>", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_without_confirm_reports_plan_and_stops(self):
        result = skill.run({"workspace": str(self.ws)})
        self.assertFalse(result["success"])
        self.assertTrue(result["needs_confirmation"])
        self.assertIn("confirm=True", result["error"])
        # Nothing local should have been created either.
        self.assertFalse((self.ws / ".git").exists())

    def test_dry_run_makes_no_changes(self):
        result = skill.run({"workspace": str(self.ws), "dry_run": True})
        self.assertTrue(result["success"])
        self.assertTrue(result["dry_run"])
        self.assertIn("public", result["plan"].lower())
        self.assertFalse((self.ws / ".git").exists())

    def test_plan_names_the_public_consequence(self):
        result = skill.run({"workspace": str(self.ws)})
        self.assertIn("public", result["plan"].lower())
        self.assertIn("Pages", result["plan"])


class TestHelpers(unittest.TestCase):
    def test_normalise_repo_name_accepts_slugs(self):
        for good in ("my-site", "my_site", "site123", "a.b.c", "A-B_1"):
            with self.subTest(name=good):
                self.assertEqual(skill._normalise_repo_name(good), good)

    def test_normalise_repo_name_rejects_everything_else(self):
        for bad in ("", "  ", "a b", "a/b", "a;b", "a&b", "$(x)", "a" * 101, "a\nb"):
            with self.subTest(name=bad):
                self.assertIsNone(skill._normalise_repo_name(bad))

    def test_secret_scan_finds_nested_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / ".env").write_text("x", encoding="utf-8")
            (ws / "config").mkdir()
            (ws / "config" / "server.pem").write_text("x", encoding="utf-8")
            (ws / "src").mkdir()
            (ws / "src" / "app.js").write_text("x", encoding="utf-8")
            (ws / "node_modules").mkdir()
            (ws / "node_modules" / ".env").write_text("x", encoding="utf-8")

            found = skill._scan_for_secrets(ws)
            self.assertIn(".env", found)
            self.assertIn("config/server.pem", found)
            self.assertNotIn("src/app.js", found)
            # Build dirs are skipped -- a vendored .env there is not a deploy risk.
            self.assertFalse(any("node_modules" in f for f in found))

    def test_run_never_uses_a_shell(self):
        """The injection surface is shell=True; guard the executable path.

        Checks the AST rather than the raw text, because the module docstring
        discusses `shell=True` when explaining why it is not used.
        """
        import ast

        tree = ast.parse(SKILL_PATH.read_text(encoding="utf-8"))
        calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "run"
        ]
        self.assertTrue(calls, "expected at least one subprocess.run call")

        for call in calls:
            shell_kwargs = [kw for kw in call.keywords if kw.arg == "shell"]
            if shell_kwargs:
                self.assertIs(
                    shell_kwargs[0].value.value,
                    False,
                    "subprocess.run must pass shell=False",
                )
            else:
                self.fail("subprocess.run should state shell=False explicitly")

    def test_run_never_force_pushes(self):
        """--force destroys remote history; inspect the argv, not the prose."""
        import ast

        tree = ast.parse(SKILL_PATH.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.List) and node.elts):
                continue
            elements = [
                e.value for e in node.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)
            ]
            if "push" in elements:
                self.assertNotIn(
                    "--force",
                    elements,
                    f"argv list builds a force-push: {elements}",
                )


if __name__ == "__main__":
    unittest.main()
