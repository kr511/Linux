#!/usr/bin/env bash
#
# Stufe-1-Test für linux-kairo: Startet der Kernel überhaupt?
#
# Bootet den Kernel in QEMU OHNE Festplatte und OHNE Initramfs. Erwartet wird:
#   1. "Linux version <ver>-kairo" erscheint  -> Kernel wurde geladen und läuft
#   2. "VFS: Unable to mount root fs"          -> Kernel ist bis zum Punkt
#      gekommen, an dem er sein Root-Dateisystem sucht. Dass er keins findet,
#      ist hier RICHTIG, wir geben ihm ja keins.
#
# Das prüft nicht alles (keine Module, kein amdgpu), aber es fängt die
# schlimmsten Fehler ab, bevor man Zeit in größere Tests steckt.
# Installiert nichts, fasst keine Datenträger an.
#
# Aufruf:
#   scripts/kernel-smoke-test.sh                 # neuestes Paket aus kernel/linux-kairo/
#   scripts/kernel-smoke-test.sh <paket.pkg.tar.zst>
#   scripts/kernel-smoke-test.sh --kernel <bzImage/vmlinuz>   # rohes Kernel-Image

set -euo pipefail

repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
die() { printf 'FEHLER: %s\n' "$*" >&2; exit 1; }

command -v qemu-system-x86_64 >/dev/null || die "QEMU fehlt: sudo pacman -S --needed qemu-desktop"

tmp="$(mktemp -d -t kairo-smoke.XXXXXX)"
trap 'rm -rf -- "${tmp}"' EXIT
trap 'exit 130' INT TERM

if [[ "${1:-}" == "--kernel" ]]; then
    kernel="${2:?--kernel braucht eine Datei}"
else
    pkg="${1:-}"
    if [[ -z "${pkg}" ]]; then
        # shellcheck disable=SC2012  # Dateinamen erzeugt makepkg, keine Sonderzeichen
        pkg="$(ls -t -- "${repo_dir}"/kernel/linux-kairo/linux-kairo-[0-9]*.pkg.tar.zst 2>/dev/null | head -1)" || true
    fi
    [[ -n "${pkg}" && -f "${pkg}" ]] || die "Kein Paket gefunden. Erst scripts/build-kernel.sh ausführen."
    command -v bsdtar >/dev/null || die "bsdtar fehlt (Paket libarchive)"
    # Nur den Kernel aus dem Paket auspacken, in einen Temp-Ordner
    bsdtar -xf "${pkg}" -C "${tmp}" --include='usr/lib/modules/*/vmlinuz'
    kernel="$(find "${tmp}/usr/lib/modules" -name vmlinuz | head -1)"
fi
[[ -f "${kernel}" ]] || die "Kernel-Image nicht gefunden: ${kernel}"

log="${tmp}/boot.log"
printf '==> Boote %s (Abbruch nach spätestens 5 Minuten)\n' "${kernel}"
# -nographic         keine Grafik, Ausgabe der seriellen Konsole ins Terminal
# console=ttyS0      Kernel schreibt auf die serielle Konsole
# panic=-1 + -no-reboot  bei Kernel-Panik sofort beenden statt neu starten
timeout 300 qemu-system-x86_64 \
    -accel kvm -accel tcg \
    -cpu max -m 1024 -nographic -no-reboot \
    -kernel "${kernel}" \
    -append "console=ttyS0 panic=-1" \
    > "${log}" 2>&1 || true

version_line="$(grep -a -m1 'Linux version' "${log}" || true)"
if [[ "${version_line}" == *-kairo* ]] && grep -aq 'VFS: Unable to mount root fs' "${log}"; then
    printf '==> BESTANDEN\n    %s\n' "${version_line#*] }"
    printf '    Kernel lief bis zur Suche nach dem Root-Dateisystem.\n'
    exit 0
fi

printf '==> NICHT BESTANDEN. Letzte 40 Zeilen der Bootausgabe:\n'
tail -40 "${log}"
exit 1
