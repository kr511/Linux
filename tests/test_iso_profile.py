"""Tests für das Kairo-ISO-Overlay und scripts/assemble-iso-profile.sh.

Die Assembly-Tests brauchen ein echtes releng-Profil von archiso. Gesucht wird:
  1. in der Umgebungsvariable KAIRO_RELENG_DIR (so macht es die CI), sonst
  2. unter /usr/share/archiso/configs/releng (wenn archiso installiert ist).
Fehlt beides, werden diese Tests übersprungen (nicht als bestanden gezählt).
"""

import configparser
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ISO = REPO / "iso"
RELENG = Path(os.environ.get("KAIRO_RELENG_DIR",
                             "/usr/share/archiso/configs/releng"))
HAVE_RELENG = (RELENG / "profiledef.sh").is_file()

# Erlaubte Zeichen in Arch-Paketnamen (siehe man PKGBUILD, "pkgname")
PKGNAME_RE = re.compile(r"^[a-z0-9@_+][a-z0-9@._+-]*$")


def read_package_list(path):
    lines = (l.split("#", 1)[0].strip() for l in path.read_text().splitlines())
    return [l for l in lines if l]


class OverlayFilesTest(unittest.TestCase):
    """Prüfungen, die nur unsere eigenen Dateien brauchen."""

    def test_paketnamen_gueltig(self):
        for pkg in read_package_list(ISO / "packages.kairo.x86_64"):
            with self.subTest(paket=pkg):
                self.assertRegex(pkg, PKGNAME_RE)

    def test_hostname(self):
        self.assertEqual((ISO / "airootfs/etc/hostname").read_text().strip(),
                         "kairo")

    def test_os_release(self):
        text = (ISO / "airootfs/usr/local/share/kairo/os-release").read_text()
        values = dict(l.split("=", 1) for l in text.splitlines() if "=" in l)
        self.assertEqual(values["ID"], "kairo")
        self.assertEqual(values["ID_LIKE"], "arch")
        self.assertEqual(values["NAME"], '"Kairo OS"')

    def test_pacman_hook(self):
        hook = ISO / "airootfs/etc/pacman.d/hooks/kairo-os-release.hook"
        text = hook.read_text()
        # Ohne diese Markierung bliebe der Hook im Live-System aktiv
        self.assertTrue(text.startswith("# remove from airootfs!"))
        # Muss alphabetisch VOR dem releng-Aufräum-Hook laufen
        self.assertLess(hook.name, "zzzz99-remove-custom-hooks-from-airootfs.hook")
        # pacman-Hooks dürfen Schlüssel mehrfach haben (Operation), darum strict=False
        ini = configparser.ConfigParser(strict=False)
        ini.read_string(text)
        self.assertEqual(ini["Trigger"]["Target"], "filesystem")
        self.assertEqual(ini["Action"]["When"], "PostTransaction")
        src = ini["Action"]["Exec"].split()[-2]
        self.assertTrue((ISO / "airootfs" / src.lstrip("/")).is_file(),
                        f"Hook kopiert {src}, die Datei fehlt im Overlay")


class KairoDesktopTest(unittest.TestCase):
    """Kairo 0.2: GNOME-Live-System und Installer."""

    AIROOTFS = ISO / "airootfs"
    SHARE = ISO / "airootfs/usr/local/share/kairo"

    def test_paketliste_installation(self):
        pkgs = read_package_list(self.SHARE / "packages.target")
        self.assertEqual(len(pkgs), len(set(pkgs)), "doppelte Pakete")
        for pkg in pkgs:
            with self.subTest(paket=pkg):
                self.assertRegex(pkg, PKGNAME_RE)
        # Was der Nutzer ausdrücklich wollte: AMD, GNOME, Gaming, Apps
        for pkg in ["linux-zen", "amd-ucode", "vulkan-radeon", "lib32-vulkan-radeon",
                    "gnome", "gdm", "steam", "discord", "firefox", "chromium",
                    "zram-generator", "gamemode", "flatpak", "nodejs", "npm",
                    "btrfs-progs", "snapper", "snap-pac", "cryptsetup", "plymouth",
                    "zenity", "libnotify", "terminus-font", "openai-codex",
                    "arch-install-scripts"]:  # kairo-rollback ruft arch-chroot auf
            with self.subTest(pflicht=pkg):
                self.assertIn(pkg, pkgs)

    def test_flatpaks(self):
        apps = read_package_list(self.SHARE / "flatpaks.target")
        self.assertEqual(set(apps), {"org.vinegarhq.Sober", "com.spotify.Client",
                                     "com.visualstudio.code"})

    def test_netzwerk_und_desktop_dienste(self):
        system = self.AIROOTFS / "etc/systemd/system"
        # releng-Netzwerk (networkd/iwd) ist maskiert, NetworkManager übernimmt
        for unit in ["systemd-networkd.service", "systemd-networkd.socket",
                     "systemd-networkd-wait-online.service", "iwd.service"]:
            with self.subTest(maskiert=unit):
                self.assertEqual(os.readlink(system / unit), "/dev/null")
        self.assertEqual(os.readlink(system / "display-manager.service"),
                         "/usr/lib/systemd/system/gdm.service")
        self.assertEqual(os.readlink(system / "default.target"),
                         "/usr/lib/systemd/system/graphical.target")
        wants = system / "multi-user.target.wants"
        self.assertTrue(os.readlink(wants / "NetworkManager.service").endswith("/NetworkManager.service"))
        self.assertTrue((system / "kairo-live-user.service").is_file())

    def test_build_hooks_werden_entfernt(self):
        for hook in (self.AIROOTFS / "etc/pacman.d/hooks").glob("*.hook"):
            with self.subTest(hook=hook.name):
                self.assertTrue(hook.read_text().startswith("# remove from airootfs!"))
                self.assertLess(hook.name, "zzzz99-remove-custom-hooks-from-airootfs.hook")

    def test_installiertes_system_behaelt_os_release_hook(self):
        hook = self.SHARE / "target/etc/pacman.d/hooks/kairo-os-release.hook"
        self.assertFalse(hook.read_text().startswith("# remove from airootfs!"))

    def test_desktop_eintraege(self):
        files = [*(self.AIROOTFS / "usr/share/applications").glob("*.desktop"),
                 *(self.SHARE / "target/usr/local/share/applications").glob("*.desktop")]
        # 7 = Live-System und Kairo-Starter, inkl. ChatGPT-Web-Ersatz (bis die App da ist)
        self.assertEqual(len(files), 7)
        icon_dirs = [base / "usr/local/share/icons/hicolor/scalable/apps"
                     for base in (self.SHARE / "target", self.AIROOTFS)]
        for f in files:
            with self.subTest(datei=f.name):
                ini = configparser.ConfigParser(interpolation=None)
                ini.optionxform = str
                ini.read_string(f.read_text())
                entry = ini["Desktop Entry"]
                self.assertEqual(entry["Type"], "Application")
                self.assertTrue(entry["Name"] and entry["Exec"])
                if entry["Icon"].startswith("kairo-"):
                    # exists() folgt Symlinks: das Ziel muss es wirklich geben
                    self.assertTrue(any((d / f"{entry['Icon']}.svg").exists() for d in icon_dirs))

    def test_design_dateien(self):
        branding = self.SHARE / "branding"
        for name in ["kairo-logo.svg", "wallpaper.png", "gdm-logo.png",
                     "plymouth-watermark.png", "fastfetch-logo.txt"]:
            with self.subTest(datei=name):
                self.assertTrue((branding / name).is_file())
        # syslinux zeigt nur Bilder in genau 640x480 an
        png = (ISO / "syslinux/splash.png").read_bytes()
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual((int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")),
                         (640, 480))
        # Das Symbol "kairo-logo" (os-release LOGO) zeigt auf das Logo
        for base in [self.AIROOTFS, self.SHARE / "target"]:
            icon = base / "usr/local/share/icons/hicolor/scalable/apps/kairo-logo.svg"
            with self.subTest(symbol=str(icon.relative_to(ISO))):
                self.assertTrue(icon.is_symlink())
                link = os.path.normpath(icon.parent / os.readlink(icon))
                self.assertEqual(Path(link).relative_to(self.AIROOTFS) if base == self.AIROOTFS
                                 else Path(link).relative_to(self.SHARE / "target"),
                                 Path("usr/local/share/kairo/branding/kairo-logo.svg"))
        for db in [self.AIROOTFS / "etc/dconf/db/local.d/00-kairo-live",
                   self.SHARE / "target/etc/dconf/db/local.d/00-kairo"]:
            with self.subTest(dconf=db.name):
                text = db.read_text()
                self.assertIn("/usr/local/share/kairo/branding/wallpaper.png", text)
                self.assertIn("accent-color='green'", text)

    def test_gdm_profil_fuer_logo(self):
        """Ohne /etc/dconf/profile/gdm ignoriert GDM das Kairo-Logo."""
        for base in [self.AIROOTFS, self.SHARE / "target"]:
            with self.subTest(base=str(base.relative_to(ISO))):
                profile = (base / "etc/dconf/profile/gdm").read_text()
                self.assertIn("system-db:gdm", profile)
                self.assertIn("gdm-logo.png", (base / "etc/dconf/db/gdm.d/01-kairo").read_text())

    def test_wiederherstellen_auch_vom_usb_stick(self):
        """kairo-rollback muss im Live-System liegen (Kairo startet nicht mehr)
        und wird vom Installer ins neue System kopiert."""
        self.assertTrue((self.AIROOTFS / "usr/local/bin/kairo-rollback").is_file())
        self.assertIn("/usr/local/bin/kairo-rollback",
                      (self.AIROOTFS / "usr/local/bin/kairo-install").read_text())

    def test_polkit_regeln_passen_zu_den_skripten(self):
        policy = (self.SHARE / "target/usr/share/polkit-1/actions/org.kairo.policy").read_text()
        for path in re.findall(r'exec.path">([^<]+)<', policy):
            with self.subTest(pfad=path):
                name = Path(path).name
                self.assertTrue((self.SHARE / "target/usr/local/bin" / name).is_file()
                                or (self.AIROOTFS / "usr/local/bin" / name).is_file())

    def test_selbsttest_nicht_im_normalen_ziel(self):
        """Der Selbsttest schaltet den PC aus, er darf nie normal mitkommen."""
        target = self.SHARE / "target"
        self.assertEqual(list(target.rglob("*selftest*")), [])


@unittest.skipUnless(HAVE_RELENG, f"kein releng-Profil unter {RELENG}")
class AssembledProfileTest(unittest.TestCase):
    """Baut das Profil wirklich zusammen und prüft das Ergebnis."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "profile"
        subprocess.run(
            [str(REPO / "scripts/assemble-iso-profile.sh"),
             "--base", str(RELENG), "--out", str(cls.out)],
            check=True, capture_output=True, text=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def profiledef(self, *names):
        """Liest profiledef.sh so ein, wie mkarchiso es tut (per bash source)."""
        script = ("declare -A file_permissions; source profiledef.sh; "
                  + "; ".join(f'printf "%s\\n" "${{{n}}}"' for n in names))
        result = subprocess.run(["bash", "-c", script], cwd=self.out,
                                check=True, capture_output=True, text=True)
        return result.stdout.splitlines()

    def test_iso_metadaten(self):
        name, label, version, app = self.profiledef(
            "iso_name", "iso_label", "iso_version", "iso_application")
        self.assertEqual(name, "kairo")
        self.assertRegex(label, r"^KAIRO_\d{6}$")
        self.assertLessEqual(len(label), 32)
        self.assertRegex(version, r"^1\.0\.1-\d{4}\.\d{2}\.\d{2}$")
        self.assertEqual(app, "Kairo OS Live")

    def test_bootmodi_von_releng_geerbt(self):
        (ours,) = self.profiledef("bootmodes[*]")
        result = subprocess.run(
            ["bash", "-c", "declare -A file_permissions; source profiledef.sh; "
                           'printf "%s\\n" "${bootmodes[*]}"'],
            cwd=RELENG, check=True, capture_output=True, text=True)
        self.assertEqual(ours, result.stdout.strip())
        self.assertIn("uefi", ours)

    def test_paketliste(self):
        pkgs = (self.out / "packages.x86_64").read_text().split()
        self.assertEqual(len(pkgs), len(set(pkgs)), "doppelte Pakete")
        for pkg in ["linux", "base", "mkinitcpio-archiso", "amd-ucode",
                    "linux-firmware-amdgpu", *read_package_list(ISO / "packages.kairo.x86_64")]:
            with self.subTest(paket=pkg):
                self.assertIn(pkg, pkgs)
        # Zu groß für die 2-GiB-Grenze, siehe iso/packages.remove.x86_64
        for pkg in read_package_list(ISO / "packages.remove.x86_64"):
            with self.subTest(entfernt=pkg):
                self.assertNotIn(pkg, pkgs)
        # Kein eigener Kernel im Live-System, erst nach separatem Boot-Test
        self.assertNotIn("linux-kairo", pkgs)

    def test_dateirechte_fuer_skripte(self):
        """mkarchiso übernimmt keine Rechte aus Git: jedes Skript in
        /usr/local/bin braucht einen Eintrag in file_permissions."""
        cmd = ('declare -A file_permissions; source profiledef.sh; '
               'for k in "${!file_permissions[@]}"; do '
               'printf "%s=%s\\n" "$k" "${file_permissions[$k]}"; done')
        result = subprocess.run(["bash", "-c", cmd], cwd=self.out,
                                check=True, capture_output=True, text=True)
        perms = dict(l.split("=", 1) for l in result.stdout.splitlines())
        for script in (ISO / "airootfs/usr/local/bin").iterdir():
            with self.subTest(skript=script.name):
                self.assertEqual(perms.get(f"/usr/local/bin/{script.name}"), "0:0:755")
        self.assertEqual(perms.get("/etc/sudoers.d/kairo-live"), "0:0:440")
        # Die Einträge aus releng bleiben erhalten
        self.assertEqual(perms.get("/etc/shadow"), "0:0:400")

    def test_bootmenue_umbenannt(self):
        for sub in ["efiboot", "syslinux", "grub"]:
            for f in (self.out / sub).rglob("*"):
                if f.suffix in {".conf", ".cfg"}:
                    with self.subTest(datei=str(f.relative_to(self.out))):
                        self.assertNotIn("Arch Linux install medium", f.read_text())
        entry = next((self.out / "efiboot/loader/entries").glob("01-*.conf"))
        self.assertIn("Kairo OS Live", entry.read_text())

    def test_overlay_dateien_vorhanden(self):
        self.assertEqual((self.out / "airootfs/etc/hostname").read_text().strip(),
                         "kairo")
        self.assertTrue((self.out / "airootfs/etc/pacman.d/hooks/"
                         "kairo-os-release.hook").is_file())

    def test_releng_original_unveraendert(self):
        """Das Skript darf das Upstream-Profil nur lesen, nie ändern."""
        self.assertIn('iso_name="archlinux"', (RELENG / "profiledef.sh").read_text())

    def test_verweigert_fremden_nichtleeren_ordner(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "wichtig.txt").write_text("nicht löschen")
            result = subprocess.run(
                [str(REPO / "scripts/assemble-iso-profile.sh"),
                 "--base", str(RELENG), "--out", d],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue((Path(d) / "wichtig.txt").exists())


class RollbackPreflightTest(unittest.TestCase):
    """kairo-rollback darf nichts verändern, bevor feststeht, dass es fertig werden kann."""

    SCRIPT = (ISO / "airootfs/usr/local/bin/kairo-rollback").read_text()

    def test_werkzeuge_werden_vor_dem_austausch_von_at_geprueft(self):
        check = self.SCRIPT.index('command -v "${tool}"')
        first_change = self.SCRIPT.index('mv "${top}/@"')
        self.assertLess(check, first_change)

    def test_arch_chroot_ist_im_installierten_system(self):
        pkgs = read_package_list(ISO / "airootfs/usr/local/share/kairo/packages.target")
        self.assertIn("arch-chroot", self.SCRIPT)
        self.assertIn("arch-install-scripts", pkgs)


if __name__ == "__main__":
    unittest.main()
