#!/usr/bin/env bash
#
# Importiert die offizielle Arch-Kernel-Konfiguration als Basis für linux-kairo.
#
# Quelle ist das signierte Arch-Paket 'linux-headers'. Es enthält unter
# /usr/lib/modules/<version>/build/.config genau die Konfiguration, mit der
# Arch seinen Kernel 'linux' baut.
#
# NICHT /proc/config.gz verwenden: In WSL ist das die Konfiguration des
# Microsoft-WSL-Kernels, nicht die von Arch.
#
# Schreibt nur: kernel/linux-kairo/config.arch-base
#
# Aufruf:
#   sudo pacman -S --needed linux-headers   # einmalig, installiert nur Dateien
#   scripts/kernel-import-arch-config.sh

set -euo pipefail

repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
pkg_dir="${repo_dir}/kernel/linux-kairo"
target="${pkg_dir}/config.arch-base"

die()  { printf 'FEHLER: %s\n' "$*" >&2; exit 1; }
warn() { printf 'WARNUNG: %s\n' "$*" >&2; }

[[ -f /etc/arch-release ]] || die "Kein Arch Linux."
pacman -Q linux-headers >/dev/null 2>&1 \
    || die "Paket linux-headers fehlt: sudo pacman -S --needed linux-headers"

headers_ver="$(pacman -Q linux-headers | awk '{print $2}')"
src="$(pacman -Qlq linux-headers | grep -E '/build/\.config$' | head -1)"
[[ -n "${src}" && -f "${src}" ]] || die "Keine .config im Paket linux-headers gefunden."

# pkgver aus dem PKGBUILD lesen, ohne das PKGBUILD auszuführen
kairo_ver="$(sed -n 's/^pkgver=//p' "${pkg_dir}/PKGBUILD")"

# Vergleich der Serie (z. B. 7.2), kleine Unterschiede löst olddefconfig
arch_series="$(cut -d. -f1,2 <<< "${headers_ver}")"
kairo_series="$(cut -d. -f1,2 <<< "${kairo_ver}")"
if [[ "${arch_series}" != "${kairo_series}" ]]; then
    warn "Arch-Config ist von ${headers_ver}, linux-kairo baut ${kairo_ver}."
    warn "Funktioniert meist, aber 'diff' in prepare() genau ansehen."
fi

{
    printf '# Basis: offizielle Arch-Kernel-Konfiguration\n'
    printf '# Quelle: Paket linux-headers %s (%s)\n' "${headers_ver}" "${src}"
    printf '# Importiert mit scripts/kernel-import-arch-config.sh\n'
    printf '# NICHT von Hand bearbeiten. Kairo-Änderungen gehören in kairo.config.\n'
    cat -- "${src}"
} > "${target}"

printf '==> Gespeichert: %s\n' "${target#"${repo_dir}"/}"
printf '==> Nächste Schritte:\n'
printf '    cd kernel/linux-kairo && updpkgsums   # Prüfsummen eintragen\n'
printf '    git add config.arch-base PKGBUILD && git commit\n'
