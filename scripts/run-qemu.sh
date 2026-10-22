#!/usr/bin/env bash
#
# Startet eine Kairo-ISO in einer virtuellen Maschine (QEMU).
#
# Die VM bekommt NUR die ISO als schreibgeschütztes CD-Laufwerk. Es wird keine
# Festplatte, weder echt noch virtuell, eingebunden. Dein PC bleibt unberührt.
#
# Angelehnt an das offizielle 'run_archiso' aus dem archiso-Paket, aber:
#   - läuft auch ohne /dev/kvm (run_archiso erzwingt -enable-kvm)
#   - VNC lauscht nur auf localhost (run_archiso: alle Netzwerkschnittstellen)
#
# Aufruf:
#   scripts/run-qemu.sh [--bios] [--vnc] [ISO]
#
#   --bios  alter BIOS-Modus statt UEFI
#   --vnc   kein Fenster, stattdessen VNC auf 127.0.0.1:5900
#   ISO     Pfad zur ISO (Standard: neueste in out/)
#
# Voraussetzungen (Arch): sudo pacman -S --needed qemu-desktop edk2-ovmf

set -euo pipefail

repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
die() { printf 'FEHLER: %s\n' "$*" >&2; exit 1; }

# UEFI-Firmware aus dem Arch-Paket edk2-ovmf. Auf anderen Distributionen
# liegen die Dateien woanders, dann per Umgebungsvariable angeben.
ovmf_code="${KAIRO_OVMF_CODE:-/usr/share/edk2/x64/OVMF_CODE.4m.fd}"
ovmf_vars="${KAIRO_OVMF_VARS:-/usr/share/edk2/x64/OVMF_VARS.4m.fd}"

boot=uefi
display=(-display sdl)   # wie run_archiso
iso=""
while (( $# )); do
    case "$1" in
        --bios) boot=bios; shift ;;
        --vnc)  display=(-display none -vnc 127.0.0.1:0); shift ;;
        -h|--help) sed -n '2,20p' "${BASH_SOURCE[0]}"; exit 0 ;;
        -*) die "Unbekannte Option: $1" ;;
        *)  iso="$1"; shift ;;
    esac
done

if [[ -z "${iso}" ]]; then
    # Neueste ISO nach Datum. ls ist hier ok: Die Dateinamen erzeugen wir selbst.
    # shellcheck disable=SC2012
    iso="$(ls -t -- "${repo_dir}"/out/kairo-*-x86_64.iso 2>/dev/null | head -1)" || true
fi
[[ -n "${iso}" && -f "${iso}" ]] || die "Keine ISO gefunden. Erst scripts/build-iso.sh ausführen."

command -v qemu-system-x86_64 >/dev/null || die "QEMU fehlt: sudo pacman -S --needed qemu-desktop"

qemu=(
    qemu-system-x86_64
    # KVM wenn möglich, sonst Software-Emulation (langsam, aber es läuft)
    -accel kvm -accel tcg
    -machine q35
    -cpu max
    -smp 4
    -m 3072
    -vga virtio
    "${display[@]}"
    # ISO als schreibgeschütztes CD-Laufwerk, sonst KEINE Laufwerke
    -device 'virtio-scsi-pci,id=scsi0'
    -device 'scsi-cd,bus=scsi0.0,drive=cdrom0'
    -drive "id=cdrom0,if=none,format=raw,media=cdrom,read-only=on,file=${iso}"
    # Netzwerk per NAT über deinen PC; die VM ist von außen nicht erreichbar
    -device 'virtio-net-pci,netdev=net0'
    -netdev 'user,id=net0'
    # Kernel-/Bootmeldungen der seriellen Konsole zusätzlich im Terminal
    -serial stdio
    -no-reboot
)

tmp=""
if [[ "${boot}" == uefi ]]; then
    [[ -f "${ovmf_code}" && -f "${ovmf_vars}" ]] \
        || die "UEFI-Firmware fehlt: sudo pacman -S --needed edk2-ovmf"
    # Die UEFI-Variablen werden beschrieben, darum eine temporäre Kopie
    tmp="$(mktemp -d -t kairo-qemu.XXXXXX)"
    # Beim Beenden (auch per Strg+C) die Kopie wieder löschen
    trap 'rm -rf -- "${tmp}"' EXIT
    trap 'exit 130' INT TERM
    cp -- "${ovmf_vars}" "${tmp}/OVMF_VARS.fd"
    qemu+=(
        -drive "if=pflash,format=raw,unit=0,file=${ovmf_code},read-only=on"
        -drive "if=pflash,format=raw,unit=1,file=${tmp}/OVMF_VARS.fd"
    )
fi

[[ -w /dev/kvm ]] || printf 'HINWEIS: Kein nutzbares /dev/kvm. Die VM läuft per Software-Emulation\n          und ist deutlich langsamer (Boot kann mehrere Minuten dauern).\n' >&2
[[ "${display[*]}" == *vnc* ]] && printf 'VNC: mit einem VNC-Viewer auf 127.0.0.1:5900 verbinden\n'

printf '==> Starte %s (%s)\n' "${iso}" "${boot^^}"
"${qemu[@]}"
