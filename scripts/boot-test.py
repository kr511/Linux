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

Installationstest (--install [--encrypt]), nur UEFI:
  1. ISO plus leere virtuelle Festplatte (40 GiB) starten
  2. kairo-install ohne Rückfragen laufen lassen (KAIRO_SELFTEST=1)
  3. Von der Festplatte starten. Dort meldet kairo-selftest nach dem
     ersten Start (inkl. Nachladen der Flatpaks) alles über /dev/ttyS0,
     testet dann kairo-rollback und startet neu
  4. Dritter Start: Ist das System wirklich zurückgesetzt?

Grafischer Installationstest (--install --gui [--encrypt]): wie oben, aber
Schritt 2 läuft über die echten Fenster: Willkommensfenster -> Installieren ->
kairo-install-gui. Der Test liest den Bildschirm per OCR (tesseract), klickt
mit einem virtuellen Grafiktablett auf die Knöpfe und tippt wie eine echte
deutsche Tastatur. Nur die Datei /run/kairo-selftest (legt der Test als root
an) sorgt dafür, dass zusätzlich der Selbsttest installiert wird.

Ergebnis: Screenshots (*.png), serial*.log und summary.md im Ausgabeordner.
Exit-Code 0 nur, wenn alle Prüfungen bestanden sind.

Aufruf:
  scripts/boot-test.py [--bios | --install [--gui] [--encrypt]] [--out DIR] ISO

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
    "curl -sSI -m 30 https://geo.mirror.pkgbuild.com | head -1; "
    "echo GDM=$(systemctl is-active gdm); echo NM=$(systemctl is-active NetworkManager); "
    "echo LIVEUSER=$(id -nG kairo); loginctl list-sessions --no-legend; "
    "echo GDM_LOGO=$(DCONF_PROFILE=gdm dconf read /org/gnome/login-screen/logo); "
    "test -x /usr/local/bin/kairo-install && echo INSTALLER=ok; kairo-hwcheck --text; "
    "fastfetch --pipe --logo none; echo '===END'; } 2>&1 | tee /dev/ttyS0"
)

# Nur für den Installationstest: Festplatte /dev/vda, Testbenutzer.
# Mit --encrypt kommt KAIRO_ENCRYPT dazu (beim Start entsperrt eine
# Schlüsseldatei, die kairo-install nur im Testmodus anlegt).
INSTALL_CMD = ("KAIRO_DISK=/dev/vda KAIRO_USER=tester KAIRO_PASSWORD=kairotest "
               "KAIRO_YES=1 KAIRO_SELFTEST=1 kairo-install")
CRYPT_PASSWORD = "Kairo-yz_19!"
INSTALL_CMD_CRYPT = f"KAIRO_ENCRYPT=1 KAIRO_CRYPT_PASSWORD='{CRYPT_PASSWORD}' " + INSTALL_CMD

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

    def click(self, x, y, width, height):
        """Linksklick an Bildschirmpunkt (x, y) über das virtuelle Grafiktablett."""
        # Kein "device" bei input-send-event: Das wäre die Grafikkarte. QEMU gibt
        # absolute Koordinaten von selbst an das Tablett.
        def scale(v, size):
            return max(0, min(0x7FFF, round(v * 0x7FFF / max(size - 1, 1))))
        self.cmd("input-send-event", events=[
            {"type": "abs", "data": {"axis": "x", "value": scale(x, width)}},
            {"type": "abs", "data": {"axis": "y", "value": scale(y, height)}}])
        time.sleep(0.3)
        for down in (True, False):
            self.cmd("input-send-event", events=[
                {"type": "btn", "data": {"down": down, "button": "left"}}])
            time.sleep(0.15)

    def type_german(self, text):
        # Physical QEMU keys interpreted by de-latin1, not pasted US text.
        for ch in text:
            if ch in "yYzZ":
                code = {"y": "z", "z": "y"}[ch.lower()]
                self.keys(*(["shift", code] if ch.isupper() else [code]))
            elif ch == "_":
                self.keys("shift", "slash")
            elif ch == "!":
                self.keys("shift", "1")
            elif ch == "-":
                self.keys("slash")
            else:
                self.type(ch)


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

    def __init__(self, tmp, serial, iso=None, disk=None, uefi=True, tablet=False):
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
        if tablet:
            # Absolute Mauskoordinaten: Klicks landen genau dort, wo OCR den Knopf sieht
            cmd += ["-device", "qemu-xhci,id=xhci", "-device", "usb-tablet,id=tablet0,bus=xhci.0"]
        if iso:
            cmd += ["-device", "virtio-scsi-pci,id=scsi0",
                    "-device", "scsi-cd,bus=scsi0.0,drive=cdrom0",
                    "-drive", f"id=cdrom0,if=none,format=raw,media=cdrom,read-only=on,file={iso}"]
        if disk:
            # Die Seriennummer gehört ans Gerät, nicht ans qcow2-Format: QEMU lehnt
            # "-drive ...,format=qcow2,serial=..." ab ("does not support the option 'serial'").
            cmd += ["-drive", f"file={disk},if=none,id=vmdisk,format=qcow2",
                    "-device", "virtio-blk-pci,drive=vmdisk,serial=KAIRO-VM-SSD"]
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


# Terminal-Steuerzeichen (Farben, Cursor), z. B. "\x1b[?25l" vor pacman-Ausgaben
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def section(serial, begin, end=None):
    text = serial.read_text(errors="replace").replace("\r", "") if serial.exists() else ""
    text = ANSI_RE.sub("", text)
    text = text.split(begin, 1)[-1] if begin in text else ""
    return text.split(end, 1)[0] if end else text


def has(output, pattern):
    return re.search(pattern, output, re.MULTILINE) is not None



# --- Grafischer Installationstest: Bildschirm lesen und klicken -------------------

# Befehle als Live-Benutzer kairo (uid 1000) in dessen GNOME-Sitzung
AS_LIVE_USER = ("runuser -u kairo -- env DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus "
                "XDG_RUNTIME_DIR=/run/user/1000 ")
GUI_USER_PASSWORD = "kairotest"


class GuiError(RuntimeError):
    pass


def png_size(path):
    head = Path(path).read_bytes()[:24]
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


def ocr_words(path):
    """Erkannte Wörter mit Position: [(text, links, oben, breite, höhe), ...]"""
    out = subprocess.run(["tesseract", str(path), "stdout", "-l", "deu+eng", "--psm", "11", "tsv"],
                         check=True, capture_output=True, text=True).stdout
    words = []
    for line in out.splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) == 12 and parts[11].strip():
            words.append((parts[11].strip(), *map(int, parts[6:10])))
    return words


class Screen:
    """Liest den VM-Bildschirm per OCR und klickt auf erkannte Wörter."""

    def __init__(self, vm, out):
        self.vm, self.out, self.n = vm, out, 0
        self.words, self.size, self.text = [], (1, 1), ""

    def read(self, path):
        self.vm.qmp.cmd("screendump", filename=str(path), format="png")
        self.words = ocr_words(path)
        self.size = png_size(path)
        self.text = " ".join(w[0] for w in self.words)
        return self.text

    def wait(self, name, pattern, timeout=180):
        """Wartet, bis `pattern` (Regex) am Bildschirm steht. Bild: gui-NN-<name>.png"""
        self.n += 1
        path = self.out / f"gui-{self.n:02d}-{name}.png"
        deadline = time.monotonic() + timeout
        while True:
            if re.search(pattern, self.read(path), re.I):
                log(f"GUI {name}: erkannt ({path.name})")
                return self.text
            if time.monotonic() > deadline:
                raise GuiError(f"{name}: {pattern!r} nicht am Bildschirm, OCR sah {self.text[:300]!r}")
            time.sleep(5)

    def find(self, pattern):
        """Das unterste Wort, das ganz auf `pattern` passt (Knöpfe sind unten)."""
        hits = [w for w in self.words if re.fullmatch(pattern, w[0], re.I)]
        if not hits:
            raise GuiError(f"{pattern!r} nicht gefunden, OCR sah {self.text[:300]!r}")
        return max(hits, key=lambda w: w[2])

    def click_at(self, x, y):
        self.vm.qmp.click(x, y, *self.size)

    def click(self, pattern):
        _, left, top, width, height = self.find(pattern)
        self.click_at(left + width / 2, top + height / 2)
        time.sleep(3)

    def type_into_entry(self, prompt, button, text, check_visible=True):
        """Klickt in das Eingabefeld zwischen Fragetext und Knopfzeile und tippt.

        zenity --entry: Text oben, darunter das Feld, darunter die Knöpfe. OCR sieht
        das leere Feld nicht, darum mehrere Höhen probieren, bis der getippte Text
        zu lesen ist.
        """
        _, p_left, p_top, _, p_height = self.find(prompt)
        _, b_left, b_top, b_width, _ = self.find(button)
        # Nur Wörter im Fenster (zwischen Fragetext und Knopf), nicht Dock oder Leiste
        text_bottom = max(w[2] + w[4] for w in self.words
                          if p_top - 5 <= w[2] < b_top - 30
                          and p_left - 60 <= w[1] <= b_left + b_width + 60)
        x = (p_left + b_left + b_width) / 2
        # Nicht zu tief: ein Klick auf die Knopfzeile würde das Fenster abschicken
        for frac in (0.45, 0.3, 0.6, 0.2):
            self.click_at(x, text_bottom + (b_top - text_bottom) * frac)
            time.sleep(1)
            self.vm.qmp.keys("ctrl", "a")
            self.vm.qmp.type_german(text)
            time.sleep(2)
            if not check_visible or re.search(re.escape(text), self.read(self.out / "gui-eingabe.png"), re.I):
                return
        raise GuiError(f"Eingabe {text!r} nicht im Feld gelandet, OCR sah {self.text[:300]!r}")

    def fill_passwords(self, password):
        """zenity --forms mit zwei Passwortfeldern: Feld rechts neben der Beschriftung."""
        again = self.find(r"Wiederholen:?")
        _, a_left, a_top, a_width, a_height = again
        # Beschriftung "Passwort" in derselben Spalte direkt über "Wiederholen"
        labels = [w for w in self.words if re.fullmatch(r"Passwort:?", w[0], re.I)
                  and abs(w[1] - a_left) < 40 and w[2] < a_top]
        if not labels:
            raise GuiError(f"Beschriftung Passwort nicht gefunden, OCR sah {self.text[:300]!r}")
        first = max(labels, key=lambda w: w[2])
        x = a_left + a_width + 90
        for _, _, top, _, height in (first, again):
            self.click_at(x, top + height / 2)
            time.sleep(1)
            self.vm.qmp.type_german(password)
            time.sleep(1)

def unlock(vm, args, prefix):
    """Exercise the visible Plymouth dialog; never install a test unlock key."""
    if not args.encrypt:
        return

    def dialog(name):
        path = args.out / f"{prefix}-{name}.png"
        vm.qmp.screenshot(path)
        result = subprocess.run(["tesseract", str(path), "stdout", "-l", "eng+deu",
                                 "--psm", "11"], check=True, capture_output=True, text=True)
        seen["text"] = " ".join(result.stdout.split())
        # OCR schneidet Wörter manchmal ab ("Please enter passphr: isk Kairo")
        return re.search(r"passw|passph|entsperr|unlock", result.stdout, re.I)

    seen = {"text": ""}
    deadline = time.monotonic() + args.boot_timeout
    attempt = 0
    while time.monotonic() < deadline:
        if dialog("passwortdialog"):
            break
        attempt += 1
        # Ohne diese Zeile sieht man im CI-Log nicht, was der Test auf dem Bildschirm erkennt
        if attempt in (1, 2, 3) or attempt % 6 == 0:
            log(f"Dialog nicht erkannt, OCR sieht: {seen['text'][:200]!r}")
        time.sleep(10)
    else:
        raise RuntimeError("Kein sichtbarer Verschlüsselungsdialog; OCR sah zuletzt: "
                           f"{seen['text'][:300]!r}; siehe Screenshot")
    vm.qmp.type_german("Falsch-yz_19!\n")
    time.sleep(20)
    if "===SELFTEST_BEGIN" in vm.serial.read_text(errors="replace") or not dialog("falsches-passwort"):
        raise RuntimeError("Falsches Passwort wurde nicht nachweisbar abgewiesen")
    vm.qmp.type_german(CRYPT_PASSWORD + "\n")
    log("Passwort am echten Dialog eingegeben (deutsche Belegung, y/z, Sonderzeichen)")


def evaluate_live(output, boot, powered_off):
    """Prüft die Ausgabe gegen docs/05-checkliste-kairo-0.1.md (plus GNOME)."""
    hooks = re.search(r"^HOOKS:(.*)$", output, re.MULTILINE)
    checks = [
        ("Login als root, Hostname kairo (Prompt root@kairo)",
         has(output, r"^root\s*$") and has(output, r"^kairo\s*$")),
        ('Begrüßung "Willkommen bei Kairo OS 1.0"', has(output, r"Willkommen bei Kairo OS 1\.0\.1")),
        ('os-release: NAME="Kairo OS"', has(output, r'^NAME="Kairo OS"')),
        ("os-release: ID=kairo", has(output, r"^ID=\"?kairo\"?\s*$")),
        ("os-release: ID_LIKE=arch", has(output, r"^ID_LIKE=\"?arch\"?\s*$")),
        ("os-release: IMAGE_VERSION=1.0-<datum>",
         has(output, r"^IMAGE_VERSION=\"?1\.0\.1-\d{4}\.\d\d\.\d\d")),
        ("hostnamectl: Static hostname: kairo", has(output, r"Static hostname: kairo\b")),
        ("hostnamectl: Operating System: Kairo OS", has(output, r"Operating System: Kairo OS")),
        # GitHub-Runner (Azure) lassen kein ICMP nach außen durch, ping bekommt
        # dort nie Antworten. Darum zählt auch eine HTTPS-Antwort von
        # archlinux.org oder dem Arch-Mirror als "Netzwerk geht" (archlinux.org
        # selbst bricht manchmal TLS-Verbindungen ab, Lauf 45679858733).
        ("Netzwerk: archlinux.org oder Arch-Mirror antwortet (ping oder HTTPS)",
         has(output, r"\b[1-9]\d* received") or has(output, r"^HTTP/\S+ [23]\d\d")),
        ("Desktop: GDM läuft", has(output, r"^GDM=active")),
        ("Desktop: GNOME-Sitzung des Live-Benutzers kairo", has(output, r"^\s*\d+\s+1000\s+kairo\b")),
        ("Live-Benutzer kairo ist Administrator (wheel)", has(output, r"^LIVEUSER=.*\bwheel\b")),
        ("Netzwerk: NetworkManager läuft (WLAN im Desktop)", has(output, r"^NM=active")),
        ("Installer kairo-install vorhanden", has(output, r"^INSTALLER=ok")),
        ("Hardware prüfen: erkennt Grafik, Prozessor, Internet",
         has(output, r"^\w+\|Grafik\|") and has(output, r"^OK\|Prozessor\|")
         and has(output, r"^OK\|Internet\|")),
        ("Anmeldebildschirm zeigt das Kairo-Logo",
         has(output, r"^GDM_LOGO='/usr/local/share/kairo/branding/gdm-logo\.png'")),
        ('fastfetch zeigt "Kairo OS"', has(output, r"OS: Kairo OS")),
        ("Build-Hooks wurden aus dem Live-System entfernt",
         hooks is not None and "kairo-" not in hooks.group(1)),
        ("poweroff fährt die VM sauber herunter", powered_off),
    ]
    if boot == "uefi":
        checks.insert(8, ("bootctl status: Firmware: UEFI", has(output, r"Firmware: UEFI")))
        checks.insert(9, ("Hardware prüfen: erkennt UEFI", has(output, r"^OK\|Start-Modus\|UEFI")))
    return checks


def evaluate_install(installed, output, rollback, powered_off, encrypt):
    """Prüft, was kairo-selftest beim ersten und zweiten Start gemeldet hat."""
    pkgs = ["steam", "discord", "firefox", "chromium", "gnome-shell", "amd-ucode",
            "vulkan-radeon", "lib32-vulkan-radeon", "gamemode", "mangohud",
            "snapper", "snap-pac", "plymouth", "openai-codex", "chatgpt-bin"]
    flatpaks = re.search(r"^FLATPAKS:(.*)$", output, re.MULTILINE)
    flatpaks = flatpaks.group(1) if flatpaks else ""
    mounts = re.search(r"^MOUNTS:(.*)$", output, re.MULTILINE)
    mounts = mounts.group(1).split() if mounts else []
    checks = [
        ("kairo-install ist durchgelaufen", installed),
        ("Startet von der Festplatte mit systemd-boot", has(output, r"Product: systemd-boot")),
        ('os-release: NAME="Kairo OS"', has(output, r'^NAME="Kairo OS"')),
        ("Kernel linux-zen", has(output, r"^KERNEL=\S*zen")),
        ("Desktop: GDM läuft", has(output, r"^GDM=active")),
        ("Netzwerk: NetworkManager läuft", has(output, r"^NM=active")),
        ("Firewall aktiv und beim Start aktiviert", has(output, r"^FIREWALL=active enabled$")),
        ("Firewall: externer IPv4/IPv6-Prüfclient, Kontrollmessung und ausgehender Verkehr",
         has(output, r"^FIREWALL_PROBE=ok$")),
        *((f"Paket {p} installiert", has(output, rf"^{re.escape(p)} \S+")) for p in pkgs),
        ("Erster Start: Apps nachgeladen (kairo-firstboot)", has(output, r"^FIRSTBOOT_DONE=ja")),
        ("Roblox (Sober) installiert", "org.vinegarhq.Sober" in flatpaks),
        ("Spotify installiert", "com.spotify.Client" in flatpaks),
        ("VS Code installiert", "com.visualstudio.code" in flatpaks),
        # --version beweist, dass der Befehl wirklich startet (nicht nur da ist)
        ("Claude Code startet", has(output, r"^CLAUDE=/\S+")
         and has(output, r"^CLAUDE_VERSION=\d+\.\d+")),
        ("Codex startet", has(output, r"^CODEX=/\S+")
         and has(output, r"^CODEX_VERSION=\S*\s*\d+\.\d+")),
        ("Native ChatGPT-App und Desktop-Eintrag vorhanden",
         has(output, r"^CHATGPT=/\S+") and has(output, r"^CHATGPT_DESKTOP=ok")),
        # Updates für ChatGPT kommen über pacman (Kairo Update), nicht über Kairo
        ("ChatGPT-Updates: OpenAI-Repository eingetragen", has(output, r"^CHATGPT_REPO=ok")),
        # Der Web-Starter ist nur Ersatz, solange die native App fehlt
        ("ChatGPT-Web-Starter nach der Installation entfernt",
         not has(output, r"^kairo-chatgpt\.desktop")),
        # chatgpt.desktop meldet sich für http/https an, Links sollen in Firefox aufgehen
        ("Firefox ist Standardbrowser", has(output, r"^BROWSER=firefox\.desktop\s*$")),
        ("Claude-Web-App im Menü", has(output, r"^kairo-claude\.desktop")),
        ("Apps Kairo Update, Wiederherstellen und Willkommen im Menü",
         has(output, r"^kairo-update\.desktop") and has(output, r"^kairo-restore\.desktop")
         and has(output, r"^kairo-start\.desktop")),
        ("Willkommens-App startet beim ersten Anmelden", has(output, r"^AUTOSTART=kairo-start")),
        ("Kairo Update: tägliche Prüfung aktiv", has(output, r"^UPDATE_TIMER=enabled")),
        # checkupdates: 0 = Updates da, 2 = keine, 1 = Fehler
        ("Kairo Update: Updateprüfung funktioniert", has(output, r"^UPDATE_CHECK=[02]\s*$")),
        ("Kairo-Design installiert (Hintergrund, Logo)",
         has(output, r"^LOGO:.*\bwallpaper\.png") and has(output, r"^LOGO:.*\bgdm-logo\.png")),
        ("Anmeldebildschirm zeigt das Kairo-Logo",
         has(output, r"^GDM_LOGO='/usr/local/share/kairo/branding/gdm-logo\.png'")),
        ("Boot-Animation: Theme kairo, splash aktiv", has(output, r"^PLYMOUTH=kairo .*\bsplash\b")),
        ("Btrfs, System auf Subvolume @", has(output, r"^ROOTFS=btrfs subvol=/@\s*$")),
        ("Eigene Subvolumes für /home, /.snapshots, /var/log",
         all(m in mounts for m in ["/home", "/.snapshots", "/var/log"])),
        ("Snapshot der frischen Installation vorhanden", has(output, r"^SNAPSHOTS=[1-9]")),
        (("Festplatte verschlüsselt (LUKS)", has(output, r"^CRYPT=1\s*$")) if encrypt else
         ("Keine Verschlüsselung (wie gewählt)", has(output, r"^CRYPT=0\s*$"))),
        ("zram-Swap aktiv", has(output, r"^SWAP:.*zram")),
        ("multilib (32 Bit für Steam) aktiv", has(output, r"^MULTILIB=an")),
        ("Sprache Deutsch, Tastatur deutsch",
         has(output, r"^LANG=de_DE\.UTF-8") and has(output, r"^KEYMAP=de-latin1")),
        ("Hostname kairo", has(output, r"^kairo\s*$")),
        ("Benutzer ist Administrator (wheel)", has(output, r"^GRUPPEN:.*\bwheel\b")),
        ("Zurückrollen: Änderung nach dem Snapshot ist wieder weg",
         has(rollback, r"^ROLLBACK_MARKER=weg")),
        ("Nach dem Zurückrollen startet der Desktop", has(rollback, r"^GDM=active")),
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



def install_via_gui(vm, args, serial):
    """Phase 1 über die echten Fenster, so wie ein Mensch mit Maus und Tastatur.

    Gibt (Ergebnis von kairo-install oder None, zusätzliche Prüfungen) zurück.
    """
    scr = Screen(vm, args.out)
    seen = {"welcome": False, "serial": False, "summary": False, "done": False}
    result = None

    def checks():
        return [
            ("GUI: Willkommensfenster, Knopf Installieren startet den Installer", seen["welcome"]),
            ("GUI: Laufwerksliste zeigt die Seriennummer", seen["serial"]),
            ("GUI: Zusammenfassung zeigt Laufwerk, Seriennummer und Verschlüsselung",
             seen["summary"]),
            ("GUI: Meldung \"Kairo ist installiert\"", seen["done"]),
        ]

    # Als root auf tty5: Markierung für den Selbsttest, größere Schrift für die
    # OCR, dann zum Bildschirm der GNOME-Sitzung wechseln
    vm.qmp.type("touch /run/kairo-selftest; " + AS_LIVE_USER +
                "gsettings set org.gnome.desktop.interface text-scaling-factor 1.25; "
                "echo GNOME_VT=$(loginctl show-session $(loginctl list-sessions --no-legend "
                "| awk '$3 == \"kairo\" {print $1; exit}') -p VTNr --value) > /dev/ttyS0\n")
    wait_for(serial, "GNOME_VT=", 60)
    m = re.search(r"GNOME_VT=(\d+)", serial.read_text(errors="replace"))
    vt = m.group(1) if m else "2"
    vm.qmp.type(f"chvt {vt}\n")
    time.sleep(10)
    try:
        # GNOME startet in der Übersicht: Esc zeigt den Desktop mit dem Fenster.
        # Nur dann Esc, sonst würde Esc das Willkommensfenster schließen.
        for _ in range(3):
            if not re.search(r"Type to search|Zum Suchen", scr.read(args.out / "gui-00-start.png"), re.I):
                break
            vm.qmp.keys("esc")
            time.sleep(5)
        try:
            scr.wait("willkommen", r"Willkommen bei Kairo|ausprobieren", 180)
            scr.click(r"Installieren")
            seen["welcome"] = True
        except GuiError as e:
            # Weitertesten, damit ein Fehler hier nicht den Rest verdeckt
            log(f"FEHLER: {e}")
            vm.qmp.keys("ctrl", "alt", "f5")
            time.sleep(3)
            vm.qmp.type(AS_LIVE_USER + f"systemd-run --user gtk-launch kairo-install; chvt {vt}\n")
            time.sleep(10)

        scr.wait("start", r"ganze\s+Festplatte|Kairo OS installieren", 180)
        scr.click(r"Weiter")

        text = scr.wait("laufwerk", r"Auf welche Festplatte", 180)
        seen["serial"] = bool(re.search(r"KAIRO.?VM.?SSD", text, re.I))
        scr.click(r"Weiter")

        scr.wait("benutzer", r"Benutzername", 120)
        scr.type_into_entry(r"Benutzername", r"_?OK", "tester")
        scr.click(r"_?OK")

        scr.wait("passwort", r"Wiederholen", 120)
        scr.fill_passwords(GUI_USER_PASSWORD)
        scr.click(r"_?OK")

        scr.wait("verschluesselung", r"verschl.sseln\?", 120)
        if args.encrypt:
            # Vorausgewählt ist "Verschlüsseln": nur Weiter. CRYPT=1 im
            # installierten System beweist, dass die Vorauswahl stimmt.
            scr.click(r"Weiter")
            scr.wait("verschluesselung-passwort", r"mindestens 8 Zeichen|Wiederholen", 120)
            scr.fill_passwords(CRYPT_PASSWORD)
            scr.click(r"_?OK")
        else:
            scr.click(r"Nicht")  # Zeile "Nicht verschlüsseln"
            scr.click(r"Weiter")

        text = scr.wait("zusammenfassung", r"Zusammenfassung", 120)
        seen["summary"] = bool(
            re.search(r"/dev/vda", text) and re.search(r"KAIRO.?VM.?SSD", text, re.I)
            and re.search(r"Verschl.sselung:?\s*" + ("ja" if args.encrypt else "nein"), text, re.I))
        scr.type_into_entry(r"eintippen:?", r"Installieren", "LOESCHEN")
        scr.click(r"Installieren")

        log("Installation läuft (Fortschrittsfenster)")
        started = time.monotonic()
        while result is None and time.monotonic() - started < args.install_timeout:
            result = wait_for(serial, ["KAIRO_INSTALL_DONE", "KAIRO_INSTALL_FAILED"], 300)
            scr.read(args.out / "gui-fortschritt.png")
            log(f"... {int((time.monotonic() - started) / 60)} min, OCR: {scr.text[:120]!r}")
        if result == "KAIRO_INSTALL_DONE":
            scr.wait("fertig", r"ist installiert", 180)
            seen["done"] = True
            scr.click(r"Sp.ter")
    except GuiError as e:
        log(f"FEHLER im grafischen Installer: {e}")
    finally:
        vm.qmp.screenshot(args.out / "gui-99-ende.png")
        vm.qmp.keys("ctrl", "alt", "f5")
        time.sleep(3)
    return result, checks()


def run_install(args, tmp):
    disk = tmp / "disk.qcow2"
    subprocess.run(["qemu-img", "create", "-q", "-f", "qcow2", str(disk), "40G"], check=True)

    # --- Phase 1: vom USB-Stick (ISO) auf die leere Festplatte installieren ---
    serial1 = args.out / "serial-install.log"
    log(f"Starte {args.iso} mit leerer 40-GiB-Festplatte")
    vm = Vm(tmp, serial1, iso=args.iso, disk=disk, tablet=args.gui)
    gui_checks = []
    try:
        if not vm.console(args.boot_timeout):
            vm.qmp.screenshot(args.out / "install-1-timeout.png")
            sys.exit("FEHLER: Live-System nicht bereit")
        if args.gui:
            # GNOME braucht nach der Konsole noch etwas, bis der Desktop steht
            time.sleep(30)
            log("Installiere über die Fenster (Willkommen -> kairo-install-gui)")
            result, gui_checks = install_via_gui(vm, args, serial1)
        else:
            time.sleep(15)
            vm.qmp.keys("ctrl", "alt", "f1")
            time.sleep(4)
            vm.qmp.screenshot(args.out / "install-1-live-desktop.png")
            vm.qmp.keys("ctrl", "alt", "f5")
            time.sleep(2)

            log("Starte kairo-install (ohne Rückfragen)")
            vm.qmp.type((INSTALL_CMD_CRYPT if args.encrypt else "KAIRO_ENCRYPT=0 " + INSTALL_CMD) + "\n")
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

    title = (f"{'Grafischer ' if args.gui else ''}Installationstest"
             f"{' mit Verschlüsselung' if args.encrypt else ''}: `{args.iso.name}`")
    if not installed:
        write_summary(args.out, title, gui_checks + evaluate_install(False, "", "", False, args.encrypt))
        return False

    # --- Phase 2: ohne USB-Stick von der Festplatte starten -------------------
    # kairo-selftest wartet auf kairo-firstboot (Flatpaks laden), meldet alles,
    # testet dann das Zurückrollen und startet neu (QEMU beendet sich dabei)
    serial2 = args.out / "serial-erster-start.log"
    log("Starte installiertes Kairo von der Festplatte (erster Start)")
    vm = Vm(tmp, serial2, disk=disk)
    try:
        time.sleep(4)
        vm.qmp.screenshot(args.out / "install-4-bootmenue.png")
        time.sleep(6)
        vm.qmp.screenshot(args.out / "install-4-boot-animation.png")
        unlock(vm, args, "install-4")
        # "Shell>": Die Firmware hat keinen Starteintrag gefunden und ist in
        # der EFI-Shell gelandet. Dann sofort abbrechen statt 90 Minuten warten
        result = wait_for(serial2, ["===SELFTEST_END", "Shell> "], args.install_timeout)
        if result == "===SELFTEST_END":
            vm.qmp.screenshot(args.out / "install-5-anmeldung.png")
        else:
            vm.qmp.screenshot(args.out / "install-5-fehler.png")
            log("FEHLER: Kairo startet nicht von der Festplatte (EFI-Shell)" if result
                else "FEHLER: Selbsttest nicht rechtzeitig fertig")
        if result == "===SELFTEST_END" and not vm.wait_exit(600):
            log("FEHLER: Kein Neustart nach dem Zurückrollen")
    finally:
        vm.kill()

    # --- Phase 3: nach dem Zurückrollen ---------------------------------------
    if result != "===SELFTEST_END":
        write_summary(args.out, title, gui_checks + evaluate_install(
            True, section(serial2, "===SELFTEST_BEGIN", "===SELFTEST_END"), "", False, args.encrypt))
        return False

    serial3 = args.out / "serial-nach-rollback.log"
    log("Starte Kairo nach dem Zurückrollen")
    vm = Vm(tmp, serial3, disk=disk)
    powered_off = False
    try:
        unlock(vm, args, "install-6")
        if wait_for(serial3, "===ROLLBACK_END", 900):
            vm.qmp.screenshot(args.out / "install-6-nach-rollback.png")
        else:
            vm.qmp.screenshot(args.out / "install-6-timeout.png")
            log("FEHLER: Kein Ergebnis nach dem Zurückrollen")
        powered_off = vm.wait_exit(180)
    finally:
        vm.kill()

    checks = gui_checks + evaluate_install(
        True, section(serial2, "===SELFTEST_BEGIN", "===SELFTEST_END"),
        section(serial3, "===ROLLBACK_BEGIN", "===ROLLBACK_END"), powered_off, args.encrypt)
    return write_summary(args.out, title, checks)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("iso", type=Path)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--bios", action="store_true", help="Live-Test im BIOS- statt UEFI-Modus")
    mode.add_argument("--install", action="store_true",
                      help="Installationstest auf virtueller Festplatte (UEFI)")
    ap.add_argument("--encrypt", action="store_true",
                    help="mit --install: mit Verschlüsselung installieren")
    ap.add_argument("--gui", action="store_true",
                    help="mit --install: über die Fenster installieren (OCR, Klicks)")
    ap.add_argument("--out", type=Path, default=Path("boot-test"))
    ap.add_argument("--boot-timeout", type=int, default=600,
                    help="Sekunden bis zur Konsole (ohne KVM deutlich mehr nötig)")
    ap.add_argument("--install-timeout", type=int, default=5400,
                    help="Sekunden für Installation bzw. ersten Start")
    args = ap.parse_args()

    if (args.encrypt or args.gui) and not args.install:
        ap.error("--encrypt und --gui gehen nur zusammen mit --install")
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
