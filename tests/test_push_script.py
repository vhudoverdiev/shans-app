import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class PushScriptTests(unittest.TestCase):
    def test_push_script_stages_commits_and_pushes(self):
        script = (PROJECT_ROOT / "push.ps1").read_text(encoding="utf-8")

        self.assertIn("git add -A", script)
        self.assertIn("git diff --cached --quiet", script)
        self.assertIn("git commit -m", script)
        self.assertIn("git push", script)

    def test_push_script_is_graceful_when_repo_is_clean(self):
        script = (PROJECT_ROOT / "push.ps1").read_text(encoding="utf-8")

        self.assertIn("No changes to commit.", script)
        self.assertIn("Auto update", script)
        self.assertNotIn("git reset --hard", script)
        self.assertNotIn("git clean -fd", script)


if __name__ == "__main__":
    unittest.main()
