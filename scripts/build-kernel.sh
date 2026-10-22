#!/usr/bin/env bash
#
# Baut die Pakete linux-kairo und linux-kairo-headers mit makepkg.
#
# Läuft nur auf Arch Linux, als normaler Benutzer (makepkg verweigert root).
# Installiert NICHTS am Kernel deines Systems. Ergebnis sind nur Paketdateien:
#   kernel/linux-kairo/linux-kairo-<ver>-x86_64.pkg.tar.zst
#   kernel/linux-kairo/linux-kairo-headers-<ver>-x86_64.pkg.tar.zst
#
# Dauer: mit der Arch-Config grob 1-3 Stunden, je nach CPU.
#
# Aufruf:
#   scripts/build-kernel.sh

set -euo pipefail

repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
pkg_dir="${repo_dir}/kernel/linux-kairo"

die() { printf 'FEHLER: %s\n' "$*" >&2; exit 1; }

[[ -f /etc/arch-release ]] || die "Kein Arch Linux."
(( EUID != 0 )) || die "Nicht als root starten, makepkg verweigert das."
case "${repo_dir}" in
    /mnt/*) die "Repo liegt auf einem Windows-Laufwerk. Nach ~/ in WSL klonen." ;;
esac
[[ -f "${pkg_dir}/config.arch-base" ]] \
    || die "config.arch-base fehlt. Erst scripts/kernel-import-arch-config.sh ausführen."
gpg --list-keys 647F28654894E3BD457199BE38DBBDC86092693E >/dev/null 2>&1 \
    || die "Signaturschlüssel fehlt: gpg --locate-keys gregkh@kernel.org"

cd -- "${pkg_dir}"
# --syncdeps    fehlende Build-Abhängigkeiten per pacman installieren (fragt nach)
# --cleanbuild  src/ vorher löschen, damit jeder Build frisch startet
# Ausgabe zusätzlich in build.log für die Fehlersuche
makepkg --syncdeps --cleanbuild 2>&1 | tee build.log

printf '==> Fertig. Pakete:\n'
ls -1 -- "${pkg_dir}"/*.pkg.tar.zst
