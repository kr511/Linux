#!/usr/bin/env python3
"""Automatischer Boot-Test einer Kairo-ISO in QEMU, ohne Bildschirm.

Für Rechner, auf denen man kein QEMU-Fenster bedienen kann (z. B. die
GitHub-CI). Das Skript macht dasselbe, was du sonst von Hand machst
(docs/05-checkliste-kairo-0.1.md, Teil C und D):

  1. ISO in QEMU starten (nur die ISO als CD, keine Festplatte)
  2. Screenshots vom Bootmenü und nach dem Login speichern
  3. Die Prüfbefehle aus der Checkliste per virtueller Tastatur eintippen
  4. Ihre Ausgabe über die serielle Schnittstelle (/dev/ttyS0) mitlesen
  5. poweroff tippen und prüfen, ob die VM sauber herunterfährt

Ergebnis: screenshots (*.png), serial.log und summary.md im Ausgabeordner.
Exit-Code 0 nur, wenn alle Prüfungen bestanden sind.

Aufruf:
  scripts/boot-test.py [--bios] [--out DIR] ISO

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
    "echo HOOKS: $(ls /etc/pacman.d/hooks/); ping -c 3 -w 60 archlinux.org; "
    "fastfetch --pipe --logo none; echo '===END'; } 2>&1 | tee /dev/ttyS0"
)

# Tastenbelegung US (Standard im Live-System): Zeichen -> QEMU-Tastencode
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


def wait_for(path, needle, timeout, poke=None, every=10, first_poke=0):
    """Wartet, bis needle in der Datei steht. poke() wird alle `every` s aufgerufen."""
    deadline = time.monotonic() + timeout
    next_poke = time.monotonic() + first_poke
    while time.monotonic() < deadline:
        if poke and time.monotonic() >= next_poke:
            poke()
            next_poke = time.monotonic() + every
        if path.exists() and needle in path.read_text(errors="replace"):
            return True
        time.sleep(1)
    return False


def evaluate(output, boot, powered_off):
    """Prüft die Ausgabe gegen docs/05-checkliste-kairo-0.1.md."""
    def has(pattern):
        return re.search(pattern, output, re.MULTILINE) is not None

    hooks = re.search(r"^HOOKS:(.*)$", output, re.MULTILINE)
    checks = [
        ("Login als root, Hostname kairo (Prompt root@kairo)",
         has(r"^root\s*$") and has(r"^kairo\s*$")),
        ('Begrüßung "Willkommen bei Kairo OS 0.1"', has(r"Willkommen bei Kairo OS 0\.1")),
        ('os-release: NAME="Kairo OS"', has(r'^NAME="Kairo OS"')),
        ("os-release: ID=kairo", has(r"^ID=\"?kairo\"?\s*$")),
        ("os-release: ID_LIKE=arch", has(r"^ID_LIKE=\"?arch\"?\s*$")),
        ("os-release: IMAGE_VERSION=0.1-<datum>", has(r"^IMAGE_VERSION=\"?0\.1-\d{4}\.\d\d\.\d\d")),
        ("hostnamectl: Static hostname: kairo", has(r"Static hostname: kairo\b")),
        ("hostnamectl: Operating System: Kairo OS", has(r"Operating System: Kairo OS")),
        ("ping archlinux.org bekommt Antworten", has(r"\b[1-9]\d* received")),
        ('fastfetch zeigt "Kairo OS"', has(r"OS: Kairo OS")),
        ("kairo-os-release.hook wurde aus dem Live-System entfernt",
         hooks is not None and "kairo-os-release.hook" not in hooks.group(1)),
        ("poweroff fährt die VM sauber herunter", powered_off),
    ]
    if boot == "uefi":
        checks.insert(8, ("bootctl status: Firmware: UEFI", has(r"Firmware: UEFI")))
    return checks


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("iso", type=Path)
    ap.add_argument("--bios", action="store_true", help="BIOS statt UEFI")
    ap.add_argument("--out", type=Path, default=Path("boot-test"))
    ap.add_argument("--boot-timeout", type=int, default=600,
                    help="Sekunden bis zum Login (ohne KVM deutlich mehr nötig)")
    args = ap.parse_args()

    boot = "bios" if args.bios else "uefi"
    if not args.iso.is_file():
        sys.exit(f"FEHLER: ISO nicht gefunden: {args.iso}")
    args.out.mkdir(parents=True, exist_ok=True)
    serial = args.out / "serial.log"
    serial.unlink(missing_ok=True)

    tmp = Path(tempfile.mkdtemp(prefix="kairo-boot-test."))
    qmp_path = tmp / "qmp.sock"
    accel = ["-accel", "kvm"] if os.access("/dev/kvm", os.W_OK) else ["-accel", "tcg"]
    if accel[1] == "tcg":
        log("Kein nutzbares /dev/kvm: Software-Emulation, das dauert")

    # Gleiche Geräte wie scripts/run-qemu.sh, nur ohne Fenster
    qemu = [
        "qemu-system-x86_64", *accel,
        "-machine", "q35", "-cpu", "max", "-smp", "2", "-m", "3072",
        "-vga", "virtio", "-display", "none",
        "-device", "virtio-scsi-pci,id=scsi0",
        "-device", "scsi-cd,bus=scsi0.0,drive=cdrom0",
        "-drive", f"id=cdrom0,if=none,format=raw,media=cdrom,read-only=on,file={args.iso}",
        "-device", "virtio-net-pci,netdev=net0", "-netdev", "user,id=net0",
        "-serial", f"file:{serial}",
        "-qmp", f"unix:{qmp_path},server=on,wait=off",
        "-no-reboot",
    ]
    if boot == "uefi":
        code, varsf = next(((c, v) for c, v in OVMF_CANDIDATES
                            if Path(c).is_file() and Path(v).is_file()), (None, None))
        if code is None:
            sys.exit("FEHLER: UEFI-Firmware (OVMF) nicht gefunden")
        shutil.copy(varsf, tmp / "OVMF_VARS.fd")
        qemu += ["-drive", f"if=pflash,format=raw,unit=0,file={code},read-only=on",
                 "-drive", f"if=pflash,format=raw,unit=1,file={tmp / 'OVMF_VARS.fd'}"]

    log(f"Starte {args.iso} ({boot.upper()})")
    proc = subprocess.Popen(qemu)
    powered_off = False
    try:
        qmp = Qmp(qmp_path)

        # Bootmenü steht 15 s da (Timeout in releng), mehrere Bilder zur Sicherheit
        for i, delay in enumerate((3, 3, 4), start=1):
            time.sleep(delay)
            qmp.screenshot(args.out / f"{boot}-1-bootmenue-{i}.png")

        # Strg+C leert eine halb getippte Zeile, falls das Login noch nicht stand
        def poke():
            qmp.keys("ctrl", "c")
            qmp.type("echo KAIRO_READY > /dev/ttyS0\n")

        # Erst tippen, wenn das Bootmenü sicher weg ist: Tasten wie "e" würden
        # dort den Eintrag-Editor öffnen statt zu booten.
        log("Warte auf das Login (root-Autologin auf tty1)")
        if not wait_for(serial, "KAIRO_READY", args.boot_timeout, poke, first_poke=45):
            qmp.screenshot(args.out / f"{boot}-2-timeout.png")
            sys.exit(f"FEHLER: Kein Login nach {args.boot_timeout} s, siehe Screenshot")
        qmp.keys("ctrl", "l")
        time.sleep(1)
        qmp.screenshot(args.out / f"{boot}-2-login.png")

        log("Tippe Prüfbefehle aus der Checkliste")
        qmp.type(CHECK_CMD + "\n")
        if not wait_for(serial, "===END", 180):
            log("WARNUNG: Prüfbefehle nicht rechtzeitig fertig")
        time.sleep(1)
        qmp.screenshot(args.out / f"{boot}-3-pruefung.png")

        # Begrüßung und fastfetch sind oben aus dem Bild gerollt: eigenes Bild
        qmp.keys("ctrl", "l")
        qmp.type("cat /etc/motd; fastfetch\n")
        time.sleep(5)
        qmp.screenshot(args.out / f"{boot}-4-fastfetch.png")

        log("poweroff")
        qmp.type("poweroff\n")
        try:
            powered_off = proc.wait(timeout=120) == 0
        except subprocess.TimeoutExpired:
            powered_off = False
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        shutil.rmtree(tmp, ignore_errors=True)

    text = serial.read_text(errors="replace")
    output = text.split("===BEGIN", 1)[-1].replace("\r", "")
    checks = evaluate(output, boot, powered_off)

    lines = [f"## Boot-Test {boot.upper()}: `{args.iso.name}`", "",
             "| Prüfung | Ergebnis |", "| --- | --- |"]
    lines += [f"| {name} | {'✅' if ok else '❌'} |" for name, ok in checks]
    passed = sum(ok for _, ok in checks)
    lines += ["", f"{passed}/{len(checks)} bestanden", ""]
    summary = "\n".join(lines)
    (args.out / "summary.md").write_text(summary)
    print(summary)
    sys.exit(0 if passed == len(checks) else 1)


if __name__ == "__main__":
    main()
