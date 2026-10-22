"""Tests für das linux-kairo PKGBUILD und das Kairo-Config-Fragment.

Der Fragment-Test gegen echten Kernel-Quellcode läuft nur, wenn die
Umgebungsvariable KAIRO_KERNEL_SRC auf einen Linux-Quellbaum zeigt
(die CI klont dafür die passende Version). Sonst wird er übersprungen.
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PKG = REPO / "kernel" / "linux-kairo"
KSRC = os.environ.get("KAIRO_KERNEL_SRC")


def pkgbuild_vars(*expressions):
    """Liest Werte aus dem PKGBUILD, indem bash es einliest.

    Das ist sicher: Auf oberster Ebene setzt das PKGBUILD nur Variablen,
    die Build-Funktionen werden dabei nicht ausgeführt.
    """
    script = "source PKGBUILD; " + "; ".join(
        f'printf "%s\\n" "{e}"' for e in expressions)
    result = subprocess.run(["bash", "-c", script], cwd=PKG,
                            check=True, capture_output=True, text=True)
    return result.stdout.splitlines()


class PkgbuildTest(unittest.TestCase):
    def test_paketnamen(self):
        (names,) = pkgbuild_vars("${pkgname[*]}")
        self.assertEqual(names.split(), ["linux-kairo", "linux-kairo-headers"])

    def test_pruefsummen_passen_zu_quellen(self):
        n_src, n_sum = pkgbuild_vars("${#source[@]}", "${#sha256sums[@]}")
        self.assertEqual(n_src, n_sum)

    def test_lokale_quellen_existieren(self):
        (sources,) = pkgbuild_vars("${source[*]}")
        for src in sources.split():
            if "://" in src or src == "config.arch-base":
                # config.arch-base wird erst auf Arch importiert, siehe README
                continue
            with self.subTest(datei=src):
                self.assertTrue((PKG / src).is_file())

    def test_quelle_ist_kernel_org_mit_signatur(self):
        (sources,) = pkgbuild_vars("${source[*]}")
        urls = [s for s in sources.split() if "://" in s]
        self.assertTrue(all(u.startswith("https://cdn.kernel.org/") for u in urls))
        self.assertTrue(any(u.endswith(".tar.sign") for u in urls))

    def test_keine_patches_in_0_1(self):
        """Phase 1: unveränderter Upstream-Kernel."""
        (sources,) = pkgbuild_vars("${source[*]}")
        self.assertFalse([s for s in sources.split() if s.endswith(".patch")])


@unittest.skipUnless(KSRC, "KAIRO_KERNEL_SRC nicht gesetzt")
class FragmentGegenKernelQuellenTest(unittest.TestCase):
    """x86_64_defconfig + kairo.config wie in prepare(), dann verify-config.py."""

    def test_version_passt(self):
        result = subprocess.run(["make", "-s", "kernelversion"], cwd=KSRC,
                                check=True, capture_output=True, text=True)
        (pkgver,) = pkgbuild_vars("${pkgver}")
        self.assertEqual(result.stdout.strip(), pkgver)

    def test_fragment_wird_erfuellt(self):
        with tempfile.TemporaryDirectory() as out:
            # O=... hält den Quellbaum sauber, alles landet im Temp-Ordner
            make = ["make", "-s", f"O={out}"]
            subprocess.run([*make, "x86_64_defconfig"], cwd=KSRC, check=True)
            subprocess.run(["scripts/kconfig/merge_config.sh", "-m", "-O", out,
                            f"{out}/.config", str(PKG / "kairo.config")],
                           cwd=KSRC, check=True, capture_output=True)
            subprocess.run([*make, "olddefconfig"], cwd=KSRC, check=True)
            result = subprocess.run(
                ["python3", str(PKG / "verify-config.py"), f"{out}/.config",
                 str(PKG / "kairo.config")], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == "__main__":
    unittest.main()
