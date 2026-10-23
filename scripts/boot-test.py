#!/usr/bin/env python3
"""Automatischer Test einer Kairo-ISO in QEMU, ohne Bildschirm.

Für Rechner, auf denen man kein QEMU-Fenster bedienen kann (z. B. die
GitHub-CI). Zwei Modi:

Live-Test (Standard), wie docs/05-checkliste, Teil C und D:
  1. ISO in QEMU starten (nur die ISO als CD, keine Festplatte)
  2. Screenshots vom Bootmenü, vom GNOME-Desktop und von der Konsole
  3. Auf der Notfall-Konsole (tty5) die Prüfbefehle per virtueller Tastatur
     eintippen, ihre Ausgabe über /dev/ttyS0 (serial.log) mitlesen
  4. poweroff tippen und prüfen, ob die VM sauber herunterfährt

Installationstest (--install), nur UEFI:
  1. ISO plus leere virtuelle Festplatte (40 GiB) starten
  2. kairo-install ohne Rückfragen laufen lassen (KAIRO_SELFTEST=1)
  3. Von der Festplatte starten. Dort meldet kairo-selftest nach dem
     ersten Start (inkl. Nachladen der Flatpaks) alles über /dev/ttyS0
     und schaltet die VM aus

Ergebnis: Screenshots (*.png), serial*.log und summary.md im Ausgabeordner.
Exit-Code 0 nur, wenn alle Prüfungen bestanden sind.

Aufruf:
  scripts/boot-test.py [--bios | --install] [--out DIR] ISO

Nur Python-Standardbibliothek. Ändert nichts außerhalb von --out.
"""

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# UEFI-Firmware: Arch (edk2-ovmf) oder Debian/Ubuntu (ovmf)
OVMF_CANDIDATES = [
    ("/usr/share/edk2/x64/OVMF_CODE.4m.fd", "/usr/share/edk2/x64/OVMF_VARS.4m.fd"),
    ("/usr/share/OVMF/OVMF_CODE_4M.fd", "/usr/share/OVMF/OVMF_VARS_4M.fd"),
]

# Dieser Befehl wird im Live-System eingetippt. Alles landet zusätzlich auf
# /dev/ttyS0, das QEMU in serial.log schreibt. Muss eine Zeile bleiben.
# Die Live-Shell ist zsh: Dort ist ein Wort mit "=" am Anfang eine Pfadsuche
# ("zsh: ==BEGIN not found"), darum die Markierungen in Anführungszeichen.
CHECK_CMD = (
    "export SYSTEMD_PAGER=; { echo '===BEGIN'; whoami; cat /etc/hostname; "
    "cat /etc/motd; cat /etc/os-release; hostnamectl; bootctl status; "
    "echo HOOKS: $(ls /etc/pacman.d/hooks/); ping -c 3 -w 20 archlinux.org; "
    "curl -sSI -m 30 https://archlinux.org | head -1; "
    "echo GDM=$(systemctl is-active gdm); echo NM=$(systemctl is-active NetworkManager); "
    "echo LIVEUSER=$(id -nG kairo); loginctl list-sessions --no-legend; "
    "test -x /usr/local/bin/kairo-install && echo INSTALLER=ok; "
    "fastfetch --pipe --logo none; echo '===END'; } 2>&1 | tee /dev/ttyS0"
)

# Nur für den Installationstest: Festplatte /dev/vda, Testbenutzer
INSTALL_CMD = ("KAIRO_DISK=/dev/vda KAIRO_USER=tester KAIRO_PASSWORD=kairotest "
               "KAIRO_YES=1 KAIRO_SELFTEST=1 kairo-install")

# Tastenbelegung US (Standard der Live-Konsole): Zeichen -> QEMU-Tastencode
KEYS = {" ": "spc", "-": "minus", "=": "equal", "/": "slash", ".": "dot",
        ",": "comma", ";": "semicolon", "'": "apostrophe", "\\": "backslash",
        "[": "bracket_left", "]": "bracket_right", "`": "grave_accent",
        "\n": "ret"}
SHIFT_KEYS = {"!": "1", "@": "2", "#": "3", "$": "4", "%": "5", "^": "6",
              "&": "7", "*": "8", "(": "9", ")": "0", "_": "minus",
              "+": "equal", "|": "backslash", ">": "dot", "<": "comma",
              ":": "semicolon", '"': "apostrophe", "?": "slash",
              "{": "bracket_left", "}": "bracket_right", "~": "grave_accent"}


def log(msg):
    print(f"==> {msg}", flush=True)


class Qmp:
    """Minimaler Client für das QEMU Machine Protocol (Steuerung per Socket)."""

    def __init__(self, path, timeout=60):
        deadline = time.monotonic() + timeout
        while True:
            try:
                self.sock = socket.socket(socket.AF_UNIX)
                self.sock.connect(str(path))
                break
            except OSError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.5)
        self.file = self.sock.makefile("rw")
        self._read()  # Begrüßung
        self.cmd("qmp_capabilities")

    def _read(self):
        while True:
            msg = json.loads(self.file.readline())
            if "event" not in msg:  # Ereignisse (z. B. RESET) überspringen
                return msg

    def cmd(self, name, **args):
        self.file.write(json.dumps({"execute": name, "arguments": args}) + "\n")
        self.file.flush()
        reply = self._read()
        if "error" in reply:
            raise RuntimeError(f"QMP {name}: {reply['error']}")
        return reply.get("return")

    def keys(self, *codes):
        self.cmd("send-key", keys=[{"type": "qcode", "data": c} for c in codes])
        time.sleep(0.03)

    def type(self, text):
        for ch in text:
            if ch.isascii() and (ch.islower() or ch.isdigit()):
                self.keys(ch)
            elif ch.isascii() and ch.isupper():
                self.keys("shift", ch.lower())
            elif ch in KEYS:
                self.keys(KEYS[ch])
            elif ch in SHIFT_KEYS:
                self.keys("shift", SHIFT_KEYS[ch])
            else:
                raise ValueError(f"Kein Tastencode für {ch!r}")

    def screenshot(self, path):
        self.cmd("screendump", filename=str(path), format="png")
        log(f"Screenshot: {path.name}")


def wait_for(path, needles, timeout, poke=None, every=10, first_poke=0):
    """Wartet, bis einer der Texte in der Datei steht, und gibt ihn zurück.

    poke() wird ab first_poke alle `every` Sekunden aufgerufen.
    """
    if isinstance(needles, str):
        needles = [needles]
    deadline = time.monotonic() + timeout
    next_poke = time.monotonic() + first_poke
    while time.monotonic() < deadline:
        if poke and time.monotonic() >= next_poke:
            poke()
            next_poke = time.monotonic() + every
        if path.exists():
            text = path.read_text(errors="replace")
            for needle in needles:
                if needle in text:
                    return needle
        time.sleep(1)
    return None


class Vm:
    """Eine QEMU-VM ohne Fenster, gesteuert über QMP."""

    def __init__(self, tmp, serial, iso=None, disk=None, uefi=True):
        self.serial = serial
        serial.unlink(missing_ok=True)
        qmp_path = tmp / f"qmp-{serial.stem}.sock"
        accel = "kvm" if os.access("/dev/kvm", os.W_OK) else "tcg"
        if accel == "tcg":
            log("Kein nutzbares /dev/kvm: Software-Emulation, das dauert")
        # Gleiche Geräte wie scripts/run-qemu.sh, nur ohne Fenster
        cmd = [
            "qemu-system-x86_64", "-accel", accel,
            "-machine", "q35", "-cpu", "max", "-smp", "2", "-m", "4096",
            "-vga", "virtio", "-display", "none",
            "-device", "virtio-net-pci,netdev=net0", "-netdev", "user,id=net0",
            "-serial", f"file:{serial}",
            "-qmp", f"unix:{qmp_path},server=on,wait=off",
            "-no-reboot",
        ]
        if iso:
            cmd += ["-device", "virtio-scsi-pci,id=scsi0",
                    "-device", "scsi-cd,bus=scsi0.0,drive=cdrom0",
                    "-drive", f"id=cdrom0,if=none,format=raw,media=cdrom,read-only=on,file={iso}"]
        if disk:
            cmd += ["-drive", f"file={disk},if=virtio,format=qcow2"]
        if uefi:
            code, varsf = next(((c, v) for c, v in OVMF_CANDIDATES
                                if Path(c).is_file() and Path(v).is_file()), (None, None))
            if code is None:
                sys.exit("FEHLER: UEFI-Firmware (OVMF) nicht gefunden")
            # Eine Kopie pro Testlauf, über beide Starts hinweg dieselbe:
            # Der Installer trägt dort den Bootloader ein
            vars_copy = tmp / "OVMF_VARS.fd"
            if not vars_copy.exists():
                shutil.copy(varsf, vars_copy)
            cmd += ["-drive", f"if=pflash,format=raw,unit=0,file={code},read-only=on",
                    "-drive", f"if=pflash,format=raw,unit=1,file={vars_copy}"]
        self.proc = subprocess.Popen(cmd)
        self.qmp = Qmp(qmp_path)

    def wait_exit(self, timeout):
        """True, wenn die VM von selbst sauber ausgeht."""
        try:
            return self.proc.wait(timeout=timeout) == 0
        except subprocess.TimeoutExpired:
            return False

    def kill(self):
        if self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait()

    def console(self, timeout, first_poke=45):
        """Wechselt auf die root-Konsole tty5 und wartet, bis sie bereit ist."""
        def poke():
            # Strg+C leert eine halb getippte Zeile, falls die Konsole noch nicht stand
            self.qmp.keys("ctrl", "alt", "f5")
            time.sleep(0.5)
            self.qmp.keys("ctrl", "c")
            self.qmp.type("echo KAIRO_READY > /dev/ttyS0\n")
        # Erst tippen, wenn das Bootmenü sicher weg ist: Tasten wie "e" würden
        # dort den Eintrag-Editor öffnen statt zu booten.
        return wait_for(self.serial, "KAIRO_READY", timeout, poke, first_poke=first_poke)


def section(serial, begin, end=None):
    text = serial.read_text(errors="replace").replace("\r", "") if serial.exists() else ""
    text = text.split(begin, 1)[-1] if begin in text else ""
    return text.split(end, 1)[0] if end else text


def has(output, pattern):
    return re.search(pattern, output, re.MULTILINE) is not None


def evaluate_live(output, boot, powered_off):
    """Prüft die Ausgabe gegen docs/05-checkliste-kairo-0.1.md (plus GNOME)."""
    hooks = re.search(r"^HOOKS:(.*)$", output, re.MULTILINE)
    checks = [
        ("Login als root, Hostname kairo (Prompt root@kairo)",
         has(output, r"^root\s*$") and has(output, r"^kairo\s*$")),
        ('Begrüßung "Willkommen bei Kairo OS 0.2"', has(output, r"Willkommen bei Kairo OS 0\.2")),
        ('os-release: NAME="Kairo OS"', has(output, r'^NAME="Kairo OS"')),
        ("os-release: ID=kairo", has(output, r"^ID=\"?kairo\"?\s*$")),
        ("os-release: ID_LIKE=arch", has(output, r"^ID_LIKE=\"?arch\"?\s*$")),
        ("os-release: IMAGE_VERSION=0.2-<datum>",
         has(output, r"^IMAGE_VERSION=\"?0\.2-\d{4}\.\d\d\.\d\d")),
        ("hostnamectl: Static hostname: kairo", has(output, r"Static hostname: kairo\b")),
        ("hostnamectl: Operating System: Kairo OS", has(output, r"Operating System: Kairo OS")),
        # GitHub-Runner (Azure) lassen kein ICMP nach außen durch, ping bekommt
        # dort nie Antworten. Darum zählt auch eine HTTPS-Antwort von
        # archlinux.org als "Netzwerk geht".
        ("Netzwerk: archlinux.org antwortet (ping oder HTTPS)",
         has(output, r"\b[1-9]\d* received") or has(output, r"^HTTP/\S+ [23]\d\d")),
        ("Desktop: GDM läuft", has(output, r"^GDM=active")),
        ("Desktop: GNOME-Sitzung des Live-Benutzers kairo", has(output, r"^\s*\d+\s+1000\s+kairo\b")),
        ("Live-Benutzer kairo ist Administrator (wheel)", has(output, r"^LIVEUSER=.*\bwheel\b")),
        ("Netzwerk: NetworkManager läuft (WLAN im Desktop)", has(output, r"^NM=active")),
        ("Installer kairo-install vorhanden", has(output, r"^INSTALLER=ok")),
        ('fastfetch zeigt "Kairo OS"', has(output, r"OS: Kairo OS")),
        ("Build-Hooks wurden aus dem Live-System entfernt",
         hooks is not None and "kairo-" not in hooks.group(1)),
        ("poweroff fährt die VM sauber herunter", powered_off),
    ]
    if boot == "uefi":
        checks.insert(8, ("bootctl status: Firmware: UEFI", has(output, r"Firmware: UEFI")))
    return checks


def evaluate_install(installed, output, powered_off):
    """Prüft, was kairo-selftest nach dem ersten Start gemeldet hat."""
    pkgs = ["steam", "discord", "firefox", "chromium", "gnome-shell", "amd-ucode",
            "vulkan-radeon", "lib32-vulkan-radeon", "gamemode", "mangohud"]
    flatpaks = re.search(r"^FLATPAKS:(.*)$", output, re.MULTILINE)
    flatpaks = flatpaks.group(1) if flatpaks else ""
    checks = [
        ("kairo-install ist durchgelaufen", installed),
        ("Startet von der Festplatte mit systemd-boot", has(output, r"Product: systemd-boot")),
        ('os-release: NAME="Kairo OS"', has(output, r'^NAME="Kairo OS"')),
        ("Kernel linux-zen", has(output, r"^KERNEL=\S*zen")),
        ("Desktop: GDM läuft", has(output, r"^GDM=active")),
        ("Netzwerk: NetworkManager läuft", has(output, r"^NM=active")),
        *((f"Paket {p} installiert", has(output, rf"^{re.escape(p)} \S+")) for p in pkgs),
        ("Erster Start: Apps nachgeladen (kairo-firstboot)", has(output, r"^FIRSTBOOT_DONE=ja")),
        ("Roblox (Sober) installiert", "org.vinegarhq.Sober" in flatpaks),
        ("Spotify installiert", "com.spotify.Client" in flatpaks),
        ("VS Code installiert", "com.visualstudio.code" in flatpaks),
        ("Claude Code installiert", has(output, r"^CLAUDE=/\S+")),
        ("Web-Apps Claude und ChatGPT im Menü",
         has(output, r"^kairo-claude\.desktop") and has(output, r"^kairo-chatgpt\.desktop")),
        ("zram-Swap aktiv", has(output, r"^SWAP:.*zram")),
        ("multilib (32 Bit für Steam) aktiv", has(output, r"^MULTILIB=an")),
        ("Sprache Deutsch, Tastatur deutsch",
         has(output, r"^LANG=de_DE\.UTF-8") and has(output, r"^KEYMAP=de-latin1")),
        ("Hostname kairo", has(output, r"^kairo\s*$")),
        ("Benutzer ist Administrator (wheel)", has(output, r"^GRUPPEN:.*\bwheel\b")),
        ("VM fährt nach dem Test sauber herunter", powered_off),
    ]
    return checks


def write_summary(out, title, checks):
    lines = [f"## {title}", "", "| Prüfung | Ergebnis |", "| --- | --- |"]
    lines += [f"| {name} | {'✅' if ok else '❌'} |" for name, ok in checks]
    passed = sum(ok for _, ok in checks)
    lines += ["", f"{passed}/{len(checks)} bestanden", ""]
    summary = "\n".join(lines)
    (out / "summary.md").write_text(summary)
    print(summary)
    return passed == len(checks)


def run_live(args, tmp):
    boot = "bios" if args.bios else "uefi"
    serial = args.out / "serial.log"
    log(f"Starte {args.iso} ({boot.upper()})")
    vm = Vm(tmp, serial, iso=args.iso, uefi=not args.bios)
    shot = lambda name: vm.qmp.screenshot(args.out / f"{boot}-{name}.png")
    powered_off = False
    try:
        # Bootmenü steht 15 s da (Timeout in releng), mehrere Bilder zur Sicherheit
        for i, delay in enumerate((3, 3, 4), start=1):
            time.sleep(delay)
            shot(f"1-bootmenue-{i}")

        log("Warte auf das Live-System (root-Konsole tty5)")
        if not vm.console(args.boot_timeout):
            shot("2-timeout")
            sys.exit(f"FEHLER: Keine Konsole nach {args.boot_timeout} s, siehe Screenshot")

        # GNOME mit Begrüßungsfenster. Auf welchem tty die Sitzung läuft, hängt
        # von der GDM-Version ab: beide Bilder machen
        time.sleep(15)
        for tty in (1, 2):
            vm.qmp.keys("ctrl", "alt", f"f{tty}")
            time.sleep(4)
            shot(f"2-desktop-tty{tty}")
        vm.qmp.keys("ctrl", "alt", "f5")
        time.sleep(2)

        log("Tippe Prüfbefehle aus der Checkliste")
        vm.qmp.keys("ctrl", "l")
        vm.qmp.type(CHECK_CMD + "\n")
        if not wait_for(serial, "===END", 180):
            log("WARNUNG: Prüfbefehle nicht rechtzeitig fertig")
        time.sleep(1)
        shot("3-pruefung")

        # Begrüßung und fastfetch sind oben aus dem Bild gerollt: eigenes Bild
        vm.qmp.keys("ctrl", "l")
        vm.qmp.type("cat /etc/motd; fastfetch\n")
        time.sleep(5)
        shot("4-fastfetch")

        log("poweroff")
        vm.qmp.type("poweroff\n")
        powered_off = vm.wait_exit(120)
    finally:
        vm.kill()

    checks = evaluate_live(section(serial, "===BEGIN"), boot, powered_off)
    return write_summary(args.out, f"Live-Test {boot.upper()}: `{args.iso.name}`", checks)


def run_install(args, tmp):
    disk = tmp / "disk.qcow2"
    subprocess.run(["qemu-img", "create", "-q", "-f", "qcow2", str(disk), "40G"], check=True)

    # --- Phase 1: vom USB-Stick (ISO) auf die leere Festplatte installieren ---
    serial1 = args.out / "serial-install.log"
    log(f"Starte {args.iso} mit leerer 40-GiB-Festplatte")
    vm = Vm(tmp, serial1, iso=args.iso, disk=disk)
    try:
        if not vm.console(args.boot_timeout):
            vm.qmp.screenshot(args.out / "install-1-timeout.png")
            sys.exit("FEHLER: Live-System nicht bereit")
        time.sleep(15)
        vm.qmp.keys("ctrl", "alt", "f1")
        time.sleep(4)
        vm.qmp.screenshot(args.out / "install-1-live-desktop.png")
        vm.qmp.keys("ctrl", "alt", "f5")
        time.sleep(2)

        log("Starte kairo-install (ohne Rückfragen)")
        vm.qmp.type(INSTALL_CMD + "\n")
        started = time.monotonic()
        result = None
        while result is None and time.monotonic() - started < args.install_timeout:
            result = wait_for(serial1, ["KAIRO_INSTALL_DONE", "KAIRO_INSTALL_FAILED"], 300)
            minutes = int((time.monotonic() - started) / 60)
            vm.qmp.screenshot(args.out / "install-2-fortschritt.png")
            log(f"... {minutes} min")
        installed = result == "KAIRO_INSTALL_DONE"
        if not installed:
            # Protokoll für die Fehlersuche auf die serielle Schnittstelle
            vm.qmp.type("tail -n 150 /tmp/kairo-install.log > /dev/ttyS0\n")
            time.sleep(5)
            log("FEHLER: Installation fehlgeschlagen oder Zeit abgelaufen")
        vm.qmp.screenshot(args.out / "install-3-fertig.png")
        vm.qmp.type("poweroff\n")
        vm.wait_exit(120)
    finally:
        vm.kill()

    if not installed:
        write_summary(args.out, f"Installationstest: `{args.iso.name}`",
                      evaluate_install(False, "", False))
        return False

    # --- Phase 2: ohne USB-Stick von der Festplatte starten -------------------
    serial2 = args.out / "serial-erster-start.log"
    log("Starte installiertes Kairo von der Festplatte (erster Start)")
    vm = Vm(tmp, serial2, disk=disk)
    powered_off = False
    try:
        time.sleep(8)
        vm.qmp.screenshot(args.out / "install-4-bootmenue.png")
        # kairo-selftest wartet auf kairo-firstboot (Flatpaks laden)
        if wait_for(serial2, "===SELFTEST_END", args.install_timeout):
            vm.qmp.screenshot(args.out / "install-5-anmeldung.png")
        else:
            vm.qmp.screenshot(args.out / "install-5-timeout.png")
            log("FEHLER: Selbsttest nicht rechtzeitig fertig")
        powered_off = vm.wait_exit(180)
    finally:
        vm.kill()

    checks = evaluate_install(True, section(serial2, "===SELFTEST_BEGIN", "===SELFTEST_END"),
                              powered_off)
    return write_summary(args.out, f"Installationstest: `{args.iso.name}`", checks)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("iso", type=Path)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--bios", action="store_true", help="Live-Test im BIOS- statt UEFI-Modus")
    mode.add_argument("--install", action="store_true",
                      help="Installationstest auf virtueller Festplatte (UEFI)")
    ap.add_argument("--out", type=Path, default=Path("boot-test"))
    ap.add_argument("--boot-timeout", type=int, default=600,
                    help="Sekunden bis zur Konsole (ohne KVM deutlich mehr nötig)")
    ap.add_argument("--install-timeout", type=int, default=5400,
                    help="Sekunden für Installation bzw. ersten Start")
    args = ap.parse_args()

    if not args.iso.is_file():
        sys.exit(f"FEHLER: ISO nicht gefunden: {args.iso}")
    args.out.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="kairo-boot-test."))
    try:
        ok = run_install(args, tmp) if args.install else run_live(args, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
