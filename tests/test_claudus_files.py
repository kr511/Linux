"""Claudus (Windows-Wechsel-Kit): Dateiformate, die Windows braucht.

Die eigentlichen Tests laufen auf echtem Windows in .github/workflows/claudus.yml.
"""

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CLAUDUS = REPO / "windows" / "claudus"


class ClaudusFilesTest(unittest.TestCase):
    def test_ps1_files_have_utf8_bom(self):
        # Windows PowerShell 5.1 liest .ps1 ohne BOM als ANSI: Umlaute kaputt.
        files = sorted(CLAUDUS.rglob("*.ps1"))
        self.assertGreaterEqual(len(files), 4)
        for f in files:
            with self.subTest(f=f.name):
                data = f.read_bytes()
                self.assertTrue(data.startswith(b"\xef\xbb\xbf"), f"{f.name}: UTF-8-BOM fehlt")
                data[3:].decode("utf-8")

    def test_cmd_is_ascii_with_crlf(self):
        data = (CLAUDUS / "Claudus.cmd").read_bytes()
        data.decode("ascii")
        self.assertNotRegex(data, rb"(?<!\r)\n", "Claudus.cmd braucht CRLF")

    def test_raw_disk_access_only_in_lib(self):
        # Rohzugriff auf Platten nur an einer Stelle, die die Tests abdecken.
        for f in CLAUDUS.rglob("*.ps1"):
            if f.name in ("ClaudusLib.ps1", "Test-ClaudusWrite.ps1"):
                continue
            text = f.read_text(encoding="utf-8-sig")
            with self.subTest(f=f.name):
                self.assertNotIn("PhysicalDrive", text)
                self.assertNotRegex(text, r"(?i)\b(Clear-Disk|Format-Volume|diskpart)\b")

    def test_menu_write_checks_before_clearing(self):
        # Claudus.ps1 muss Auswahl prüfen, LÖSCHEN verlangen und die Platte
        # direkt vor dem Schreiben erneut vergleichen.
        text = (CLAUDUS / "Claudus.ps1").read_text(encoding="utf-8-sig")
        body = text[text.index("function Invoke-Write"):text.index("function Invoke-Verify")]
        order = [body.index(s) for s in ("$_.Ok", "LÖSCHEN", "Test-ClaudusSameDisk", "Invoke-ClaudusWriteCore")]
        self.assertEqual(order, sorted(order))


if __name__ == "__main__":
    unittest.main()
