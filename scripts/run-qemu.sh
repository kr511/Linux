#!/usr/bin/env bash
#
# Startet eine Kairo-ISO in einer virtuellen Maschine (QEMU) im UEFI-Modus.
#
# Nutzt das offizielle Testskript 'run_archiso' aus dem archiso-Paket.
# Die VM bekommt NUR die ISO als virtuelles CD-Laufwerk. Es wird keine
# Festplatte, weder echt noch virtuell, eingebunden. Dein PC bleibt unberührt.
#
# Aufruf:
#   scripts/run-qemu.sh [ISO]       (ohne Angabe: neueste ISO in out/)
#   scripts/run-qemu.sh --bios [ISO]  (alter BIOS-Modus statt UEFI)
#
# Voraussetzungen (Arch): sudo pacman -S --needed archiso qemu-desktop edk2-ovmf

set -euo pipefail

repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
die() { printf 'FEHLER: %s\n' "$*" >&2; exit 1; }

mode="-u"   # -u = UEFI (wie dein echter PC), -b = BIOS
if [[ "${1:-}" == "--bios" ]]; then
    mode="-b"
    shift
fi

iso="${1:-}"
if [[ -z "${iso}" ]]; then
    # Neueste ISO nach Datum. ls ist hier ok: Die Dateinamen erzeugen wir selbst.
    # shellcheck disable=SC2012
    iso="$(ls -t -- "${repo_dir}"/out/kairo-*-x86_64.iso 2>/dev/null | head -1)" \
        || true
fi
[[ -n "${iso}" && -f "${iso}" ]] || die "Keine ISO gefunden. Erst scripts/build-iso.sh ausführen."

command -v run_archiso >/dev/null || die "run_archiso fehlt: sudo pacman -S --needed archiso"
command -v qemu-system-x86_64 >/dev/null || die "QEMU fehlt: sudo pacman -S --needed qemu-desktop"
[[ "${mode}" == "-b" || -f /usr/share/edk2/x64/OVMF_VARS.4m.fd ]] \
    || die "UEFI-Firmware fehlt: sudo pacman -S --needed edk2-ovmf"

if [[ ! -w /dev/kvm ]]; then
    printf 'HINWEIS: Kein /dev/kvm. Die VM läuft ohne Hardware-Beschleunigung\n' >&2
    printf '         und ist deutlich langsamer (Boot kann Minuten dauern).\n' >&2
fi

printf '==> Starte %s (%s)\n' "${iso}" "$([[ ${mode} == -u ]] && echo UEFI || echo BIOS)"
# -i  ISO-Datei
exec run_archiso "${mode}" -i "${iso}"
