"""Test the signed-installer boundary without root, downloads or real packages."""

import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
HELPER = ROOT / "iso/airootfs/usr/local/share/kairo/target/usr/local/bin/kairo-chatgpt-install"
# The digest is substituted only in a temporary test copy, never via runtime env.
INSTALLER = '''#!/usr/bin/env bash
set -euo pipefail
read -r answer
[[ "$answer" == y ]]
echo EXECUTED >> "$LOG"
[[ "$INSTALL_FAIL" == 0 ]] || exit 23
touch "$STATE"
'''


class ChatGPTInstallerTest(unittest.TestCase):
    def run_installer(self, *, modified=False, download_fail=False,
                      install_fail=False, installed=False, root=True):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            bindir, tempdir = directory / "bin", directory / "temp"
            bindir.mkdir()
            tempdir.mkdir()
            fixture = directory / "download"
            fixture.write_text(INSTALLER + ("\necho MODIFIED\n" if modified else ""))
            state = directory / "installed"
            if installed:
                state.touch()
            scripts = {
                "id": '#!/bin/sh\nprintf "%s\\n" "$TEST_UID"\n',
                "curl": '''#!/bin/sh
echo DOWNLOAD >> "$LOG"
[ "$DOWNLOAD_FAIL" = 0 ] || exit 22
while [ "$#" -gt 0 ]; do
    if [ "$1" = --output ]; then cp "$FIXTURE" "$2"; exit 0; fi
    shift
done
exit 1
''',
                "pacman": '#!/bin/sh\necho "PACMAN $*" >> "$LOG"\ntest -f "$STATE"\n',
                "chatgpt": '#!/bin/sh\nexit 0\n',
            }
            for name, text in scripts.items():
                path = bindir / name
                path.write_text(text)
                path.chmod(0o755)
            helper = directory / "helper.sh"
            digest = hashlib.sha256(INSTALLER.encode()).hexdigest()
            helper.write_text(re.sub(r"(?m)^installer_sha256=[a-f0-9]{64}$",
                                     f"installer_sha256={digest}", HELPER.read_text()))
            env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}",
                       TMPDIR=str(tempdir), LOG=str(directory / "log"),
                       FIXTURE=str(fixture), STATE=str(state),
                       TEST_UID="0" if root else "1000",
                       DOWNLOAD_FAIL=str(int(download_fail)),
                       INSTALL_FAIL=str(int(install_fail)))
            result = subprocess.run(["/bin/bash", str(helper)], env=env,
                                    capture_output=True, text=True, timeout=10)
            log = (directory / "log").read_text() if (directory / "log").exists() else ""
            self.assertEqual(list(tempdir.iterdir()), [], "Temporary download was not removed")
            return result, log, state.exists()

    def test_verified_installer_receives_confirmation(self):
        result, log, installed = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("EXECUTED", log)
        self.assertTrue(installed)

    def test_changed_download_is_never_executed(self):
        result, log, installed = self.run_installer(modified=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("geändert", result.stderr)
        self.assertNotIn("EXECUTED", log)
        self.assertFalse(installed)

    def test_download_failure_is_not_success(self):
        result, log, installed = self.run_installer(download_fail=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("EXECUTED", log)
        self.assertFalse(installed)

    def test_upstream_failure_is_propagated(self):
        result, log, installed = self.run_installer(install_fail=True)
        self.assertEqual(result.returncode, 23)
        self.assertIn("EXECUTED", log)
        self.assertFalse(installed)

    def test_installed_app_is_not_downloaded_again(self):
        result, log, installed = self.run_installer(installed=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("DOWNLOAD", log)
        self.assertTrue(installed)

    def test_requires_root(self):
        result, log, installed = self.run_installer(root=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("DOWNLOAD", log)
        self.assertFalse(installed)
