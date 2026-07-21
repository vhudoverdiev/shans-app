import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DeployScriptTests(unittest.TestCase):
    def test_windows_launcher_only_runs_server_side_github_deploy(self):
        script = (PROJECT_ROOT / "deploy.ps1").read_text(encoding="utf-8")

        self.assertNotIn("git -C", script)
        self.assertNotIn("git push", script)
        self.assertNotIn("SkipPush", script)
        self.assertIn("& ssh @SshArguments", script)
        self.assertIn("./deploy.sh", script)

    def test_cmd_wrapper_allows_dot_slash_deploy_command(self):
        wrapper = (PROJECT_ROOT / "deploy.cmd").read_text(encoding="utf-8")

        self.assertIn("deploy.ps1", wrapper)
        self.assertIn("exit /b %ERRORLEVEL%", wrapper)

    def test_server_deploy_is_safe_and_verified(self):
        script = (PROJECT_ROOT / "deploy.sh").read_text(encoding="utf-8")

        self.assertIn("git merge --ff-only", script)
        self.assertNotIn("git clean -fd", script)
        self.assertIn("backup_database", script)
        self.assertIn("unittest discover", script)
        self.assertIn("wait_for_health", script)
        self.assertIn("rollback_on_error", script)


if __name__ == "__main__":
    unittest.main()
