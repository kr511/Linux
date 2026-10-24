"""Test kairo-chatgpt-install without root, downloads or real packages.

pacman and pacman-key are stubs; gpg is real, so the key check is the one
that runs on Kairo. Paths are substituted only in a temporary test copy,
never via runtime environment variables.
"""

import os
import base64
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "iso/airootfs/usr/local/share/kairo/target"
HELPER = TARGET / "usr/local/bin/kairo-chatgpt-install"
KEY = TARGET / "usr/local/share/kairo/openai-chatgpt.gpg"
FINGERPRINT = "3BFA0E4AE8B8CC16A2D9BA684A3B4A566C4660E4"
# Must stay byte-identical to what OpenAI's installer and package write,
# otherwise they treat the file as an administrator edit and stop updating it
REPO_CONF = """### THIS FILE IS AUTOMATICALLY CONFIGURED ###
# Remove it and its Include line to opt out of automatic package updates.
[openai-chatgpt]
SigLevel = Required DatabaseRequired TrustedOnly
Server = https://persistent.oaistatic.com/codex-app-prod/linux/arch/$arch
"""

STUBS = {
    "id": '#!/bin/sh\nprintf "%s\\n" "$TEST_UID"\n',
    "pacman-key": '#!/bin/sh\necho "PACMAN-KEY $*" >> "$LOG"\n',
    "pacman": '''#!/bin/sh
echo "PACMAN $*" >> "$LOG"
case "$1" in
    -Q) test -f "$STATE" ;;
    -Syu) [ "$PACMAN_FAIL" = 0 ] || exit 1; touch "$STATE" ;;
esac
''',
    "chatgpt": "#!/bin/sh\nexit 0\n",
}


def primary_fingerprints(key, home):
    out = subprocess.run(["gpg", "--homedir", str(home), "--batch", "--show-keys",
                          "--with-colons", str(key)],
                         capture_output=True, text=True, check=True).stdout
    result, primary = [], False
    for fields in (line.split(":") for line in out.splitlines()):
        if fields[0] in ("pub", "sub"):
            primary = fields[0] == "pub"
        elif fields[0] == "fpr" and primary:
            result.append(fields[9])
            primary = False
    return result


@unittest.skipUnless(shutil.which("gpg"), "gpg fehlt")
class ChatGPTInstallerTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.bindir, self.tempdir = self.dir / "bin", self.dir / "temp"
        self.bindir.mkdir()
        self.tempdir.mkdir()
        for name, text in STUBS.items():
            (self.bindir / name).write_text(text)
            (self.bindir / name).chmod(0o755)
        self.key = self.dir / "key.gpg"
        shutil.copy(KEY, self.key)
        self.repo_conf = self.dir / "openai-chatgpt.conf"
        self.pacman_conf = self.dir / "pacman.conf"
        self.pacman_conf.write_text("[options]\n\n[core]\nInclude = /etc/pacman.d/mirrorlist\n")
        self.web_starter = self.dir / "kairo-chatgpt.desktop"
        self.web_starter.write_text("[Desktop Entry]\n")
        self.state = self.dir / "installed"
        self.log = self.dir / "log"
        text = HELPER.read_text()
        for var, path in [("key_file", self.key), ("repo_conf", self.repo_conf),
                          ("pacman_conf", self.pacman_conf), ("web_starter", self.web_starter)]:
            text, n = re.subn(rf"(?m)^{var}=.*$", f"{var}={path}", text)
            self.assertEqual(n, 1, var)
        self.helper = self.dir / "helper.sh"
        self.helper.write_text(text)

    def run_helper(self, root=True, pacman_fail=False):
        self.log.unlink(missing_ok=True)
        env = dict(os.environ, PATH=f"{self.bindir}:{os.environ['PATH']}",
                   TMPDIR=str(self.tempdir), LOG=str(self.log), STATE=str(self.state),
                   TEST_UID="0" if root else "1000", PACMAN_FAIL=str(int(pacman_fail)))
        # stdin leer: Es darf nichts auf eine Antwort warten (früher "yes" -> "[J/n]")
        result = subprocess.run(["/bin/bash", str(self.helper)], env=env, text=True,
                                stdin=subprocess.DEVNULL, capture_output=True, timeout=60)
        self.assertEqual(list(self.tempdir.iterdir()), [], "Temporäres gpg-Verzeichnis blieb liegen")
        return result, self.log.read_text() if self.log.exists() else ""

    def test_fresh_install_sets_up_repository_and_installs(self):
        result, log = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PACMAN-KEY --init", log)
        self.assertIn(f"PACMAN-KEY --add {self.key}", log)
        self.assertIn(f"PACMAN-KEY --lsign-key {FINGERPRINT}", log)
        self.assertIn("PACMAN -Syu --needed --noconfirm chatgpt-bin", log)
        self.assertEqual(self.repo_conf.read_text(), REPO_CONF)
        self.assertEqual(self.pacman_conf.read_text().splitlines()[-1],
                         f"Include = {self.repo_conf}")
        self.assertTrue(self.state.exists())
        self.assertFalse(self.web_starter.exists(), "Web-Starter muss weg, wenn die App da ist")

    def test_repeat_does_nothing_twice(self):
        self.run_helper()
        self.web_starter.write_text("[Desktop Entry]\n")
        result, log = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("PACMAN-KEY", log)
        self.assertNotIn("-Syu", log)
        self.assertEqual(self.pacman_conf.read_text().count("openai-chatgpt.conf"), 1)
        self.assertFalse(self.web_starter.exists())

    def test_retry_keeps_existing_configuration(self):
        # Erster Versuch scheiterte nach dem Einrichten (z. B. kein Internet),
        # oder OpenAIs Paket hat die Datei inzwischen selbst angepasst
        self.repo_conf.write_text("# von OpenAI geändert\n")
        self.pacman_conf.write_text(self.pacman_conf.read_text()
                                    + f"\nInclude = {self.repo_conf}\n")
        result, log = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.repo_conf.read_text(), "# von OpenAI geändert\n")
        self.assertEqual(self.pacman_conf.read_text().count("openai-chatgpt.conf"), 1)
        self.assertIn("-Syu", log)

    def test_foreign_key_is_never_trusted(self):
        # Debian 12 public release key, a real foreign key. No private key or
        # socket/agent is needed to test rejection by fingerprint.
        self.key.write_bytes(base64.b64decode(
            "mDMEY865UxYJKwYBBAHaRw8BAQdAd7Z0srwuhlB6JKFkcf4HU4SSS/xcRfwEQWzrcrf6AEq0"
            "SURlYmlhbiBTdGFibGUgUmVsZWFzZSBLZXkgKDEyL2Jvb2t3b3JtKSA8ZGViaWFuLXJlbGVh"
            "c2VAbGlzdHMuZGViaWFuLm9yZz6IlgQTFggAPhYhBE1k/sEZwgKQZ9bnkfjSWFuHg9SBBQJj"
            "zrlTAhsDBQkPCZwABQsJCAcCBhUKCQgLAgQWAgMBAh4BAheAAAoJEPjSWFuHg9SBSgwBAP9q"
            "peO5z1s5m4D4z3TcqDo1wez6DNya27QWWoG/4oBsAQCEN8Z00DXagPHbwrvsY2t9BCsT+Pgn"
            "Sn9biobwX7bDDg=="))
        result, log = self.run_helper()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Fingerprint", result.stderr)
        self.assertNotIn("PACMAN-KEY", log)
        self.assertNotIn("-Syu", log)
        self.assertFalse(self.repo_conf.exists())

    def test_broken_key_file_is_not_success(self):
        self.key.write_bytes(b"kein Schluessel")
        result, log = self.run_helper()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("PACMAN-KEY", log)

    def test_pacman_failure_keeps_web_starter(self):
        result, log = self.run_helper(pacman_fail=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("-Syu", log)
        self.assertTrue(self.web_starter.exists(), "Ohne native App bleibt die Web-App")

    def test_requires_root(self):
        result, log = self.run_helper(root=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(log, "")
        self.assertFalse(self.repo_conf.exists())


@unittest.skipUnless(shutil.which("gpg"), "gpg fehlt")
class ShippedKeyTest(unittest.TestCase):
    def test_shipped_key_is_exactly_the_pinned_one(self):
        with tempfile.TemporaryDirectory() as home:
            self.assertEqual(primary_fingerprints(KEY, home), [FINGERPRINT])
        self.assertIn(f"key_fingerprint={FINGERPRINT}\n", HELPER.read_text())


if __name__ == "__main__":
    unittest.main()
