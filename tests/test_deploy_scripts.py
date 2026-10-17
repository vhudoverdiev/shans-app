import unittest
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DeployScriptTests(unittest.TestCase):
    def test_server_downloads_lfs_before_checks_and_reports_missing_client(self):
        script = (PROJECT_ROOT / 'deploy.sh').read_text()
        functions = script.rsplit("trap 'rollback_on_error", 1)[0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.gitattributes').write_text('*.mp4 filter=lfs diff=lfs merge=lfs -text\n')
            fake_git = root / 'git'
            fake_git.write_text('''#!/bin/sh
echo "$*" >> "$DEPLOY_TEST_LOG"
case "$*" in
  show*) echo '*.mp4 filter=lfs diff=lfs merge=lfs -text' ;;
  'lfs version') [ "$DEPLOY_TEST_MISSING" = 0 ] ;;
esac
''')
            fake_git.chmod(0o755)
            log = root / 'calls.log'
            env = {**os.environ, 'PATH': str(root) + os.pathsep + os.environ['PATH'],
                   'DEPLOY_TEST_LOG': str(log), 'DEPLOY_TEST_MISSING': '0'}
            code = functions + '\nprepare_lfs\ndownload_lfs_media\n'
            harness = root / 'deploy-test.sh'
            harness.write_text(code)
            result = subprocess.run(['bash', str(harness)], cwd=root, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            calls = log.read_text()
            self.assertIn('lfs install --local', calls)
            self.assertIn('lfs pull --include= --exclude= origin', calls)
            self.assertLess(calls.index('lfs pull'), calls.index('lfs fsck'))
            log.write_text('')
            env['DEPLOY_TEST_MISSING'] = '1'
            result = subprocess.run(['bash', str(harness)], cwd=root, env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('установите git-lfs', result.stderr)
            self.assertNotIn('lfs pull', log.read_text())
        self.assertLess(script.index('  prepare_lfs\n'), script.index('git merge --ff-only'))
        self.assertLess(script.index('  download_lfs_media\n'), script.index('  install_dependencies\n', script.index('main()')))

    @unittest.skipUnless(shutil.which('zsh'), 'zsh is required for the local launcher')
    def test_local_launcher_pushes_existing_commits_and_rejects_large_blobs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copy(PROJECT_ROOT / 'deployshans', root / 'deployshans')
            fake_git = root / 'git'
            fake_git.write_text('''#!/bin/sh
echo "$*" >> "$DEPLOY_TEST_LOG"
case "$*" in
  'branch --show-current') echo main ;;
  'remote get-url origin'|'remote get-url --push --all origin') echo "${DEPLOY_TEST_REMOTE:-https://github.com/vhudoverdiev/shans-app}" ;;
  'cat-file --batch-check='*)
    cat >/dev/null
    if [ "$DEPLOY_TEST_LARGE" = 1 ]; then echo 'blob 104857601 movie.mp4'; fi ;;
esac
''')
            fake_git.chmod(0o755)
            log = root / 'calls.log'
            env = {**os.environ, 'PATH': str(root) + os.pathsep + os.environ['PATH'],
                   'DEPLOY_TEST_LOG': str(log), 'DEPLOY_TEST_LARGE': '0'}
            result = subprocess.run(['zsh', str(root / 'deployshans')], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('push origin HEAD:refs/heads/main', log.read_text())
            self.assertNotIn('commit ', log.read_text())
            log.write_text('')
            env['DEPLOY_TEST_LARGE'] = '1'
            result = subprocess.run(['zsh', str(root / 'deployshans')], env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('movie.mp4', result.stdout)
            self.assertNotIn('push origin', log.read_text())
            log.write_text('')
            env['DEPLOY_TEST_REMOTE'] = 'https://github.com/other/project'
            result = subprocess.run(['zsh', str(root / 'deployshans')], env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn('fetch ', log.read_text())

    def test_windows_launcher_only_runs_server_side_github_deploy(self):
        script = (PROJECT_ROOT / "deploy.ps1").read_text(encoding="utf-8")

        self.assertNotIn("git -C", script)
        self.assertNotIn("git push", script)
        self.assertNotIn("SkipPush", script)
        self.assertIn("& ssh @SshArguments", script)
        self.assertIn("./deploy.sh", script)
        self.assertIn('[string]$Server = "root@135.106.176.36"', script)
        self.assertNotIn("80.249.146.211", script)

    def test_cmd_wrapper_allows_dot_slash_deploy_command(self):
        wrapper = (PROJECT_ROOT / "deploy.cmd").read_text(encoding="utf-8")

        self.assertIn("deploy.ps1", wrapper)
        self.assertIn("exit /b %ERRORLEVEL%", wrapper)

    def test_server_deploy_is_safe_and_verified(self):
        script = (PROJECT_ROOT / "deploy.sh").read_text(encoding="utf-8")

        self.assertIn('readlink -f -- "${BASH_SOURCE[0]}"', script)
        self.assertIn('/usr/local/bin/deploy', script)
        self.assertIn('install_deploy_command', script)
        self.assertIn("git merge --ff-only", script)
        self.assertNotIn("git clean -fd", script)
        self.assertIn("backup_database", script)
        self.assertIn("unittest discover", script)
        self.assertIn("wait_for_health", script)
        self.assertIn("rollback_on_error", script)


if __name__ == "__main__":
    unittest.main()
