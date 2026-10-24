# Kairo OS: Status

Diese Datei trennt **vorbereitete** Dateien von **tatsächlich getesteten**
Builds. Ein Eintrag wird erst grün, wenn der Test wirklich gelaufen ist, mit
Datum, Umgebung und Ergebnis im Protokoll unten.

Legende: ⬜ offen · 🟨 vorbereitet (Dateien da, nie echt gebaut) ·
🟩 Teilprüfung bestanden (siehe Protokoll) · ✅ gebaut **und** Boot-Test bestanden

| Komponente | Status | Was genau geprüft ist |
| --- | --- | --- |
| Statische Tests (`tests/run-all.sh`) | 🟩 | 27 Tests, shellcheck; lokal bestanden |
| ISO-Profil-Assembly | 🟩 | Gegen echtes releng aus archiso v91 zusammengebaut und geprüft |
| ISO-Build mit `mkarchiso` | ✅ | GitHub Actions (`iso.yml`), archiso 91, siehe Protokoll |
| ISO bootet in QEMU (UEFI/BIOS) | ✅ | Automatisch per `scripts/boot-test.py` in GitHub Actions: UEFI 13/13, BIOS 12/12. ping nur per HTTPS ersetzt (siehe Protokoll) |
| `scripts/run-qemu.sh` | 🟩 | QEMU + UEFI-Firmware starten, CD wird erkannt, KVM→TCG-Fallback (Dummy-ISO) |
| GNOME-Live-System (GDM, Autologin, NetworkManager) | 🟩 | `iso.yml` uefi 18/18, bios 17/17 (0.2 und 1.0) |
| Kairo-Design (Logo, Hintergrund, Bootmenü, Anmeldebildschirm, Boot-Animation) | ✅ | Screenshots im Lauf 39992597552 |
| `kairo-install` auf leere Festplatte (Btrfs, mit/ohne LUKS2) | ✅ | 44/44 und 44/44, Lauf 39992597552 |
| Installiertes System startet, erster Start lädt alle Apps | ✅ | dito |
| Native ChatGPT-Desktop-App (Web-Starter nur als Ersatz) | 🟨 | Umgebaut nach rotem VM-Test (siehe Protokoll 2026-10-24); neuer ISO-Test läuft |
| Snapshots und Zurückrollen (`kairo-rollback`) | ✅ | dito, inkl. Neustart nach dem Zurückrollen |
| Kairo Update (Prüfung, Timer) | ✅ | dito; Update-Fenster selbst nur von Hand testbar |
| Grafischer Installer (`kairo-install-gui`) | 🟩 | Ablauf mit nachgebauten Fenstern getestet (`tests/test_gui_installer.py`), echte Fenster nur von Hand |
| Release v1.0 (Download-Seite) | ✅ | https://github.com/kr511/Linux/releases/tag/v1.0, Lauf 40013204531, alle Tests grün |
| Installation auf deinem echten PC | ⬜ | Erst nach grünem Installationstest |
| `linux-kairo` PKGBUILD | 🟨 | Von echtem `makepkg --printsrcinfo` gelesen; **nie gebaut** |
| `kairo.config` (47 Optionen) | 🟩 | Gegen echten Kconfig-Code 7.2.12 aufgelöst und verifiziert |
| `scripts/kernel-smoke-test.sh` | 🟩 | Mit Testkernel (defconfig + kairo.config) bestanden, Gegenprobe korrekt |
| `linux-kairo`-Paket bootet | ⬜ | Das echte Paket (Arch-Basis-Config) wurde noch nie gebaut |
| `linux-kairo` in der ISO | ⬜ | Erst nach erfolgreichem Einzeltest (Kairo 0.3) |

## Testprotokoll

### 2026-10-24: SSD-Schutz, Firewall und echter Entsperrtest vorbereitet

- Arbeitsbranch `kairo-ssd-kernel`, Ziel v1.0.1 mit `linux-zen` als Standard.
  Der dreistufige Plan steht in `docs/plan-ssd-und-linux-kairo.md`.
- Laufwerksidentität und Belegung vor dem Löschen prüfen; GUI zeigt
  Seriennummer und reicht die gewählte Identität weiter. Verschlüsselung ist
  vorausgewählt, Abbrechen bleibt ein Abbruch. Kein globales `swapoff -a`.
- Persistente nftables-Firewall für IPv4/IPv6 vorbereitet. Der VM-Prüfclient
  läuft in einem eigenen Netzwerk-Namespace und enthält eine positive
  Kontrollmessung. Ausgehendes HTTPS wird ebenfalls geprüft.
- VM-Testschlüssel im Initramfs entfernt; der Test sucht den sichtbaren
  Passwortdialog per OCR und tippt ein falsches sowie das richtige
  Testpasswort über QMP mit deutscher Tastaturbelegung ein.
- Lokal: shellcheck und 60 unittest-Fälle durchgelaufen, davon 58 bestanden
  und 2 mangels Kernelquellen übersprungen. Echte archiso-v91-Profiltests
  eingeschlossen. Fremdschlüsseltest verwendet einen festen öffentlichen
  Debian-Schlüssel, damit kein GPG-Agent für Schlüsselerzeugung nötig ist.
- Noch nicht nachgewiesen: neue ISO, neue Firewall-/Entsperrprüfungen in QEMU
  und echte Hardware. Keine Freigabe allein aufgrund dieser lokalen Tests.

### 2026-10-24: ChatGPT-Installation repariert und umgebaut

- ISO-Test von PR #11 (Lauf 40068021246): ISO, UEFI, BIOS grün; install und
  install-crypt je 45/48. `chatgpt-bin` fehlte, erster Start nicht fertig.
- Ursache per neuem Diagnose-Ausdruck im Selbsttest (Journal von
  kairo-firstboot, Lauf 40076492030): pacman fragt auf Deutsch
  `Installation fortsetzen? [J/n]`, `yes` antwortet `y`, das gilt als Nein.
  pacman bricht vor dem Download ab. In den Tests lief alles auf Englisch.
- Zweites Problem: OpenAIs `install-arch.sh` enthält die Liste der aktuellen
  Versionen und wird mit jedem Release neu veröffentlicht (zuletzt
  2026-10-23 19:28 UTC). Die feste Prüfsumme hätte nach dem nächsten Release
  jede Installation blockiert.
- Umbau: `kairo-chatgpt-install` führt das Skript nicht mehr aus. Kairo liefert
  OpenAIs Signaturschlüssel mit (byte-gleich mit
  `codex-app-prod/linux/repository-signing-key.gpg`, Fingerprint
  `3BFA0E4A…6C4660E4`), prüft ihn, trägt das Repository mit demselben Inhalt
  wie OpenAIs Installer ein und installiert mit
  `pacman -Syu --needed --noconfirm chatgpt-bin` (sprachunabhängig, lehnt
  Rückfragen wie "Paket entfernen?" ab statt sie zu bestätigen).
- `kairo-install` installiert ChatGPT schon im chroot; kairo-firstboot holt es
  nur nach, falls das scheitert. Bis dahin bleibt der Web-Starter als Ersatz
  im Dock, er wird nach erfolgreicher Installation gelöscht.
- `chatgpt.desktop` meldet sich für http/https an: `/etc/xdg/mimeapps.list`
  setzt Firefox als Standardbrowser. `paccache` behält 2 statt 3 Versionen
  (ChatGPT: über 500 MB pro Version).
- Arch-Container (podman): Schlüssel geprüft und lokal signiert, Repo-Datenbank
  besteht `DatabaseRequired TrustedOnly`, `chatgpt-bin 26.1021.22027` samt
  Abhängigkeiten auflösbar (`--print`, ohne 520-MB-Download); zweiter Lauf
  trägt nichts doppelt ein; fremder Schlüssel wird abgelehnt.
- Gefunden vor dem ISO-Test: `pacman-key` lässt gpg-agent laufen. Im chroot
  von kairo-install hätte er die Festplatte beim Aushängen blockiert. Das
  Skript beendet ihn jetzt; im Container geprüft (ohne Änderung bleibt ein
  gpg-agent übrig, mit Änderung keiner).
- `tests/run-all.sh`: shellcheck, 50 Tests bestanden (8 neue für den Installer,
  echtes gpg), 2 Kernel-Tests übersprungen. Neue VM-Prüfungen: OpenAI-Repo
  eingetragen, Web-Starter entfernt, Firefox Standardbrowser.

### 2026-10-24: Native ChatGPT-App integrieren (noch kein ISO-Test)

- Offiziellen Arch-Installer von OpenAI gelesen und SHA-256 auf
  `a21f493780ad124547a3fb64524cc7909370caf1ecea08a143e1f6c271775ccb`
  festgelegt. Der Installer prüft Schlüssel und Signaturen und richtet das
  signierte OpenAI-Repository für `chatgpt-bin` ein.
- `KAIRO_RELENG_DIR=<archiso v91>/configs/releng tests/run-all.sh`:
  shellcheck bestanden, 46 Tests bestanden, 2 Kernel-Quellcode-Tests mangels
  `KAIRO_KERNEL_SRC` übersprungen.
- Sechs neue Tests prüfen die Installationsgrenze mit nachgebauten Befehlen:
  bestätigte Installation, geänderter Download, Downloadfehler,
  Installationsfehler, Wiederholung und fehlende root-Rechte.
- Web-Starter entfernt; Dock und Willkommen verwenden `chatgpt.desktop` aus
  dem nativen Paket. VM-Selbsttest prüft zusätzlich Paket, Programmdatei und
  Desktop-Eintrag. Das prüft noch keinen GUI-Start oder Kontologin.
- Keine echte ChatGPT-Installation auf dem lokalen Debian-System; keine neue
  ISO gebaut. Die grünen früheren VM-Ergebnisse gelten weiterhin nur für den
  damaligen Stand mit Web-App.

Neue Einträge oben anfügen. Format:

```
### JJJJ-MM-TT: <was>
- Umgebung: <z. B. WSL2 Arch, archiso 91, QEMU 10.x>
- Befehl: <exakt>
- Ergebnis: <bestanden / fehlgeschlagen + Fehlermeldung>
```

### 2026-10-23: Kairo 1.0, alle Tests bestanden (GitHub Actions)

- Umgebung: wie unten, Lauf 39992597552 (Branch `kairo-1.0`)
- Ergebnis: Live UEFI 18/18, Live BIOS 17/17, Installation 44/44,
  Installation mit Verschlüsselung 44/44: bestanden
- Behoben seit dem ersten Installationstest: UEFI-Starteintrag
  (`efibootmgr`), Claude Code unter npm 12 (`kairo-claude-code` führt das
  Installationsskript des Pakets aus), Codex als Arch-Paket, GDM-Logo
  (`/etc/dconf/profile/gdm`), Testauswertung (Steuerzeichen, `ls -1`)
- Nicht automatisch getestet: die Fenster von `kairo-install-gui`,
  `kairo-update` und `kairo-restore` (die Logik dahinter schon), der
  Passwort-Dialog beim Start mit Verschlüsselung (der Test entsperrt mit
  einer Schlüsseldatei), echte AMD-Hardware

### 2026-10-23: Erster Installationstest (0.2 und 1.0, GitHub Actions)

- Umgebung: GitHub Actions, QEMU mit KVM, OVMF (Ubuntu), virtuelle
  40-GiB-Festplatte (virtio)
- Befehl: `scripts/boot-test.py --install [--encrypt]`, Läufe 39938809843
  (0.2) und 39953094056 (1.0)
- Ergebnis Live-Test: bestanden (UEFI 18/18, BIOS 17/17), auch mit neuem Design
- Ergebnis Installation: `kairo-install` läuft durch, auch mit Btrfs,
  Subvolumes und LUKS2-Verschlüsselung (1.0)
- **Fehlgeschlagen:** Start von der Festplatte. Die Firmware landet in der
  EFI-Shell. Ursache: `bootctl install` überspringt im `arch-chroot` die
  UEFI-Variablen ("Not booted with EFI or running in a container"), der
  Fallback-Eintrag stand hinter PXE und EFI-Shell. Behoben: `kairo-install`
  legt den Starteintrag jetzt mit `efibootmgr` aus dem Live-System an.
- Gefunden im Code-Review: `npm install -g @openai/codex` kann Erfolg melden,
  obwohl das Linux-Teilpaket fehlt. Codex kommt jetzt aus dem Arch-Paket
  `openai-codex`, Claude Code wird nach der Installation mit `--version` geprüft.

### 2026-10-23: Boot-Test mit HTTPS-Netzwerkprüfung (GitHub Actions)

- Umgebung: wie unten, Lauf 39827915217
- Ergebnis Build: bestanden, SHA-256
  `749bad7fb643b64c36790774b96eeed13852bdea59bff5ce29a645eda06d315f`
- Ergebnis: UEFI 13/13, BIOS 12/12 bestanden. ping weiterhin 0 Antworten
  (ICMP geblockt), `curl -sSI https://archlinux.org`: `HTTP/2 200`.

### 2026-10-22: Erster ISO-Build und Boot-Test (GitHub Actions)

- Umgebung: GitHub Actions ubuntu-24.04, Build in `archlinux:latest`
  (privilegierter Docker-Container, Build als normaler Benutzer),
  archiso 91-1, QEMU 8.2 mit KVM, OVMF aus Ubuntu
- Befehl: Workflow `.github/workflows/iso.yml`, Lauf 39825569740
  (`scripts/build-iso.sh`, danach `scripts/boot-test.py [--bios]`)
- Ergebnis Build: bestanden, `kairo-0.1-2026.10.22-x86_64.iso`,
  SHA-256 `808bf8f01eb87914973c4de1d47f25be5bb3dacf72a1b196400f305f48617e3b`
- Ergebnis UEFI: Bootmenü "Kairo OS Live (x86_64, UEFI)", Login `root@kairo`,
  Begrüßung, os-release (`NAME="Kairo OS"`, `ID=kairo`, `ID_LIKE=arch`,
  `IMAGE_VERSION=0.1-2026.10.22`), hostnamectl, `Firmware: UEFI`, fastfetch
  "Kairo OS", Hook entfernt, sauberes poweroff: bestanden
- Ergebnis BIOS: Bootmenü "Kairo OS Live (x86_64, BIOS)", sonst wie UEFI:
  bestanden
- **Fehlgeschlagen:** `ping -c 3 archlinux.org`, 0 Antworten. DNS-Auflösung
  klappt (209.126.35.79), GitHub-Runner blocken aber ICMP nach außen. Ab jetzt
  prüft der Test zusätzlich per HTTPS. Ein echter ping-Test steht noch aus
  (lokale VM).
- Nebenbefund: Im BIOS-Bootmenü steht noch das Arch-Logo als Hintergrund
  (nicht Teil von 0.1).

### 2026-10-22: Phase-1-Grundlage (Cloud-Entwicklungsumgebung)

Umgebung: Ubuntu 24.04 Container (kein Arch, kein KVM), archlinux:latest
Docker-Image (pacman 7.1.0), QEMU 8.2.2, Netzwerk-Policy sperrt archlinux.org,
kernel.org und Arch-Mirrors. Daher **kein** ISO-Build und **kein** Paket-Build.

- `tests/run-all.sh` mit `KAIRO_RELENG_DIR` = archiso Tag v91 (Commit
  723da192) und `KAIRO_KERNEL_SRC` = Linux v7.2.12 (Commit cc9de5d4):
  27/27 bestanden.
- `scripts/assemble-iso-profile.sh --base <releng v91>`: Profil korrekt,
  `bootmodes=bios.syslinux uefi.systemd-boot`, 131 Pakete, alle Menütitel
  umbenannt.
- `makepkg --printsrcinfo` im Arch-Container: PKGBUILD gültig, Pakete
  `linux-kairo` und `linux-kairo-headers`.
- `x86_64_defconfig` + `kairo.config` → `olddefconfig` → `verify-config.py`:
  alle 47 Optionen erfüllt. Gegenprobe mit erfundener Option und kaputter
  Abhängigkeit: korrekt als Fehler erkannt.
- `scripts/run-qemu.sh --vnc <dummy.iso>` mit Ubuntu-OVMF: QEMU fällt von KVM
  auf TCG zurück, UEFI startet und erkennt "QEMU CD-ROM". Temp-Ordner wird bei
  SIGTERM aufgeräumt.
- Testkernel 7.2.12 aus `x86_64_defconfig` + `kairo.config` gebaut (gcc 13.3,
  12 min, 4 Kerne). **Nicht** das linux-kairo-Paket, nur Nachweis, dass das
  Fragment einen bootfähigen Kernel ergibt. `scripts/kernel-smoke-test.sh
  --kernel bzImage`: BESTANDEN (`Linux version 7.2.12-1-kairo-smoketest`,
  bis `VFS: Unable to mount root fs`). Paket-Pfad mit nachgebautem
  `.pkg.tar.zst`: BESTANDEN. Gegenprobe mit Zufallsdaten: korrekt NICHT
  BESTANDEN.
- `scripts/build-iso.sh` im Arch-Container: bricht als root und ohne
  mkarchiso mit verständlicher Meldung ab.
