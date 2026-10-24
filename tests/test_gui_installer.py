"""Tests für kairo-install-gui ohne Bildschirm.

Die Fenster (zenity) und sudo werden durch kleine Skripte ersetzt, die
vorgegebene Antworten geben und protokollieren, was ankommt. So lässt sich
prüfen, dass die Eingaben aus den Fenstern richtig bei kairo-install landen,
ohne dass irgendetwas installiert wird.
"""

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GUI = REPO / "iso/airootfs/usr/local/bin/kairo-install-gui"

ZENITY = r'''#!/usr/bin/env bash
echo "ZENITY $*" >> "$LOG"
case "$*" in
  *--progress*) cat >/dev/null; exit 0 ;;
  *--list*"Festplatte verschlüsseln"*)
    [[ "$CANCEL_CRYPT" == 1 ]] && exit 1
    if [[ -n "$CRYPT_PW" ]]; then echo "Verschlüsseln"; else echo "Nicht verschlüsseln"; fi ;;
  *--list*) echo "/dev/vda" ;;
  *--forms*Verschlüsselung*) printf '%s\x1f%s\n' "$CRYPT_PW" "$CRYPT_PW" ;;
  *--forms*) printf 'pw1\x1fpw1\n' ;;
  *--entry*LÖSCHEN*) echo "$CONFIRM" ;;
  *--entry*) echo "elias" ;;
  *"Festplatte verschlüsseln"*) [[ -n "$CRYPT_PW" ]] || exit 1 ;;
  *"Kairo ist installiert"*) exit 1 ;;
esac
exit 0
'''

SUDO = r'''#!/usr/bin/env bash
if [[ "$*" == *--list-disks* ]]; then printf '/dev/vda\t40\tQEMU HARDDISK\tKAIRO-VM-SSD\tidentity123\n'; exit 0; fi
echo "SUDO $*" >> "$LOG"
for a in "$@"; do
  case "$a" in
    KAIRO_PASSWORD_FILE=*) echo "PW=$(cat "${a#*=}")" >> "$LOG" ;;
    KAIRO_CRYPT_PASSWORD_FILE=*) echo "CRYPT=$(cat "${a#*=}")" >> "$LOG" ;;
  esac
done
echo "==> Fertig"; echo "@@PROGRESS 100"
'''


class GuiInstallerTest(unittest.TestCase):

    def run_gui(self, crypt_pw="", confirm="LÖSCHEN", cancel_crypt=False):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            bindir, runtime = d / "bin", d / "run"
            bindir.mkdir()
            runtime.mkdir()
            stubs = {"zenity": ZENITY, "sudo": SUDO, "curl": "#!/bin/sh\nexit 0\n",
                     "lsblk": "#!/bin/sh\necho QEMU\n", "systemctl": "#!/bin/sh\nexit 0\n"}
            for name, text in stubs.items():
                path = bindir / name
                path.write_text(text)
                path.chmod(path.stat().st_mode | stat.S_IXUSR)
            env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}", LOG=str(d / "log"),
                       XDG_RUNTIME_DIR=str(runtime), CRYPT_PW=crypt_pw, CONFIRM=confirm,
                       CANCEL_CRYPT=str(int(cancel_crypt)))
            result = subprocess.run(["bash", str(GUI)], env=env, capture_output=True, text=True)
            log = (d / "log").read_text() if (d / "log").exists() else ""
            leftovers = list(runtime.iterdir())
        return result.returncode, log, leftovers

    def test_ohne_verschluesselung(self):
        code, log, leftovers = self.run_gui()
        self.assertEqual(code, 0)
        sudo = next(l for l in log.splitlines() if l.startswith("SUDO "))
        for part in ["KAIRO_DISK=/dev/vda", "KAIRO_USER=elias", "KAIRO_YES=1",
                     "/usr/local/bin/kairo-install"]:
            self.assertIn(part, sudo)
        self.assertIn("KAIRO_ENCRYPT=0", sudo)
        self.assertIn("KAIRO_DISK_ID=identity123", sudo)
        self.assertIn("PW=pw1", log)
        # Passwörter nie in der Befehlszeile, Dateien danach gelöscht
        self.assertNotIn("pw1", sudo)
        self.assertEqual(leftovers, [])

    def test_verschluesselungsdialog_abbrechen_installiert_nichts(self):
        code, log, leftovers = self.run_gui(cancel_crypt=True)
        self.assertEqual(code, 0)
        self.assertNotIn("SUDO ", log)
        self.assertEqual(leftovers, [])

    def test_mit_verschluesselung(self):
        code, log, leftovers = self.run_gui(crypt_pw="geheim123")
        self.assertEqual(code, 0)
        sudo = next(l for l in log.splitlines() if l.startswith("SUDO "))
        self.assertIn("KAIRO_ENCRYPT=1", sudo)
        self.assertIn("CRYPT=geheim123", log)
        self.assertNotIn("geheim123", sudo)
        self.assertEqual(leftovers, [])

    def test_ohne_loeschen_wird_nichts_installiert(self):
        code, log, leftovers = self.run_gui(confirm="ja")
        self.assertEqual(code, 0)
        self.assertNotIn("SUDO ", log)
        self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
