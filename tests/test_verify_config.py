"""Tests für kernel/linux-kairo/verify-config.py (ohne Kernel-Quellcode)."""

import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "kernel" / "linux-kairo" / "verify-config.py"

# Das Skript hat einen Bindestrich im Namen, darum per importlib laden
_spec = importlib.util.spec_from_file_location("verify_config", SCRIPT)
verify_config = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verify_config)


class VerifyConfigTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text):
        path = self.dir / name
        path.write_text(text, encoding="utf-8")
        return str(path)

    def run_check(self, actual, wanted):
        a = self.write("actual", actual)
        w = self.write("wanted", wanted)
        # Ausgabe des Skripts schlucken, damit die Testausgabe lesbar bleibt
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            return verify_config.main(["verify-config.py", a, w])

    def test_alles_erfuellt(self):
        self.assertEqual(self.run_check("CONFIG_A=y\nCONFIG_B=m\n",
                                        "CONFIG_A=y\nCONFIG_B=m\n"), 0)

    def test_eingebaut_statt_modul_ist_ok(self):
        self.assertEqual(self.run_check("CONFIG_A=y\n", "CONFIG_A=m\n"), 0)

    def test_modul_statt_eingebaut_ist_fehler(self):
        self.assertEqual(self.run_check("CONFIG_A=m\n", "CONFIG_A=y\n"), 1)

    def test_fehlende_option_ist_fehler(self):
        self.assertEqual(self.run_check("CONFIG_A=y\n", "CONFIG_B=y\n"), 1)

    def test_not_set_wird_als_aus_erkannt(self):
        self.assertEqual(self.run_check("# CONFIG_A is not set\n",
                                        "CONFIG_A=y\n"), 1)

    def test_text_werte(self):
        self.assertEqual(self.run_check('CONFIG_LOCALVERSION=""\n',
                                        'CONFIG_LOCALVERSION=""\n'), 0)

    def test_leeres_fragment_ist_fehler(self):
        self.assertEqual(self.run_check("CONFIG_A=y\n", "# nur Kommentar\n"), 1)


class KairoFragmentTest(unittest.TestCase):
    """Formale Prüfung der echten kernel/linux-kairo/kairo.config."""

    def test_jede_zeile_ist_gueltig(self):
        fragment = REPO / "kernel" / "linux-kairo" / "kairo.config"
        for nr, line in enumerate(fragment.read_text().splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            with self.subTest(zeile=nr):
                self.assertRegex(line, verify_config.SET_RE)

    def test_keine_doppelten_optionen(self):
        fragment = REPO / "kernel" / "linux-kairo" / "kairo.config"
        names = [l.split("=")[0] for l in fragment.read_text().splitlines()
                 if l.startswith("CONFIG_")]
        self.assertEqual(len(names), len(set(names)))


if __name__ == "__main__":
    unittest.main()
