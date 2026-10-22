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
| ISO-Build mit `mkarchiso` | 🟨 | **Nie ausgeführt** (Arch-Mirrors in der Entwicklungsumgebung gesperrt) |
| ISO bootet in QEMU (UEFI/BIOS) | ⬜ | |
| `scripts/run-qemu.sh` | 🟩 | QEMU + UEFI-Firmware starten, CD wird erkannt, KVM→TCG-Fallback (Dummy-ISO) |
| `linux-kairo` PKGBUILD | 🟨 | Von echtem `makepkg --printsrcinfo` gelesen; **nie gebaut** |
| `kairo.config` (47 Optionen) | 🟩 | Gegen echten Kconfig-Code 7.2.12 aufgelöst und verifiziert |
| `scripts/kernel-smoke-test.sh` | 🟩 | Mit Testkernel (defconfig + kairo.config) bestanden, Gegenprobe korrekt |
| `linux-kairo`-Paket bootet | ⬜ | Das echte Paket (Arch-Basis-Config) wurde noch nie gebaut |
| `linux-kairo` in der ISO | ⬜ | Erst nach erfolgreichem Einzeltest (Kairo 0.3) |

## Testprotokoll

Neue Einträge oben anfügen. Format:

```
### JJJJ-MM-TT: <was>
- Umgebung: <z. B. WSL2 Arch, archiso 91, QEMU 10.x>
- Befehl: <exakt>
- Ergebnis: <bestanden / fehlgeschlagen + Fehlermeldung>
```

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
