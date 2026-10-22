# 03: Kairo-ISO in QEMU testen

QEMU simuliert einen kompletten PC. Die Kairo-ISO bootet darin wie auf echter
Hardware, aber in einer abgeschotteten Kiste: Die VM sieht **nur** die
ISO-Datei (schreibgeschützt), keine deiner Festplatten.

## Starten

```bash
scripts/run-qemu.sh
```
Startet die neueste ISO aus `out/` im **UEFI-Modus** (wie dein echter PC).

```bash
scripts/run-qemu.sh --bios
```
Dasselbe im alten BIOS-Modus. Die ISO kann beides; teste beides einmal.

```bash
scripts/run-qemu.sh out/kairo-0.1-2026.10.22-x86_64.iso
```
Eine bestimmte ISO starten.

```bash
scripts/run-qemu.sh --vnc
```
Ohne Fenster, stattdessen VNC auf `127.0.0.1:5900` (nur von deinem PC aus
erreichbar). Für Windows 10 ohne WSLg: VNC-Viewer unter Windows öffnen und mit
`localhost:5900` verbinden.

Beenden: in der VM `poweroff`, oder im Terminal `Strg+C`.

## Was das Skript genau startet

`scripts/run-qemu.sh` ist angelehnt an das offizielle `run_archiso` aus dem
archiso-Paket. Zwei Dinge macht es bewusst anders: `run_archiso` erzwingt KVM
(ohne `/dev/kvm` bricht es ab) und öffnet VNC auf allen Netzwerkschnittstellen.
Der eigentliche Aufruf (UEFI-Modus):

```bash
qemu-system-x86_64 \
  -accel kvm -accel tcg \
  -machine q35 -cpu max -smp 4 -m 3072 -vga virtio -display sdl \
  -device virtio-scsi-pci,id=scsi0 \
  -device scsi-cd,bus=scsi0.0,drive=cdrom0 \
  -drive id=cdrom0,if=none,format=raw,media=cdrom,read-only=on,file=<deine ISO> \
  -device virtio-net-pci,netdev=net0 -netdev user,id=net0 \
  -serial stdio -no-reboot \
  -drive if=pflash,format=raw,unit=0,file=/usr/share/edk2/x64/OVMF_CODE.4m.fd,read-only=on \
  -drive if=pflash,format=raw,unit=1,file=<temporäre Kopie von OVMF_VARS.4m.fd>
```

| Teil | Bedeutung |
| --- | --- |
| `-accel kvm -accel tcg` | Erst KVM (schnell) versuchen, sonst Software-Emulation (langsam) |
| `-machine q35 -cpu max` | moderner virtueller PC, alle CPU-Funktionen, die QEMU kann |
| `-smp 4 -m 3072` | 4 CPU-Kerne, 3 GiB RAM für die VM |
| `scsi-cd ... read-only=on` | die ISO als CD-Laufwerk, schreibgeschützt. **Das einzige Laufwerk** |
| `-netdev user` | Internet über deinen PC (NAT), die VM ist von außen nicht erreichbar |
| `-serial stdio` | Meldungen der seriellen Konsole erscheinen zusätzlich im Terminal |
| `-no-reboot` | bei Neustart beendet sich QEMU, statt neu zu booten |
| `if=pflash ... OVMF_CODE` | UEFI-Firmware (schreibgeschützt) |
| `if=pflash ... OVMF_VARS` | UEFI-Einstellungen, eine **temporäre Kopie**, wird danach gelöscht |

Im BIOS-Modus (`--bios`) fallen die beiden `pflash`-Zeilen weg; QEMU nutzt
dann sein eingebautes BIOS (SeaBIOS).

## Was du prüfen solltest

1. **Bootmenü** erscheint und heißt "Kairo OS Live (x86_64, UEFI)".
2. Nach dem Boot: automatischer Login als `root`, Prompt `root@kairo`.
3. Der Begrüßungstext ("Willkommen bei Kairo OS 0.1") erscheint.
4. Diese Befehle in der VM eingeben:

```bash
cat /etc/os-release
```
Erwartet: `NAME="Kairo OS"`, `ID=kairo`, `ID_LIKE=arch` und unten
`IMAGE_ID=kairo`, `IMAGE_VERSION=0.1-...` (das fügt mkarchiso selbst hinzu).

```bash
hostnamectl
```
Erwartet: `Static hostname: kairo`, `Operating System: Kairo OS`.

```bash
uname -r
```
Erwartet in 0.1: eine Version mit `-arch` am Ende (offizieller Arch-Kernel).

```bash
bootctl status 2>/dev/null | head -5
```
Zeigt im UEFI-Modus `Firmware: UEFI ...`. Im BIOS-Modus kommt eine Meldung,
dass kein EFI-System vorliegt. Das ist dort korrekt.

```bash
ping -c 3 archlinux.org
```
Prüft, ob Netzwerk in der VM geht.

```bash
fastfetch
```
Zeigt Systeminfos. Steht dort "Kairo OS", hat das Branding geklappt.

```bash
ls /etc/pacman.d/hooks/
```
Erwartet: **leer** bzw. keine `kairo-os-release.hook`. Der Build-Hook hat sich
wie geplant selbst entfernt.

5. Herunterfahren: `poweroff`

Trag das Ergebnis in [`STATUS.md`](../STATUS.md) ein, auch wenn etwas schief
ging. Ein dokumentierter Fehlschlag ist wertvoller als ein vergessener Erfolg.

## Probleme

| Problem | Lösung |
| --- | --- |
| Kein Fenster erscheint (Windows 10, kein WSLg) | `scripts/run-qemu.sh --vnc`, dann VNC-Viewer auf `localhost:5900` |
| Sehr langsam | Kein KVM. Siehe [01, Abschnitt KVM](01-entwicklungsumgebung.md#3-optional-kvm-für-schnelle-vms) |
| Hängt bei "Booting..." | Erst `--bios` probieren. Unterschied notieren, das ist ein wichtiger Hinweis |
| Bootmenü heißt noch "Arch Linux" | Profil nicht neu gebaut. `scripts/build-iso.sh` erneut ausführen |

## Und auf dem echten PC?

**Noch nicht in Phase 1.** Dafür müsstest du die ISO auf einen USB-Stick
schreiben, und das löscht den Stick komplett. Wird in Phase 2 mit eigener
Anleitung und Sicherheitsprüfungen behandelt. Bis dahin: nur QEMU.
