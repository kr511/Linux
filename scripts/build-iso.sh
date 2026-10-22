#!/usr/bin/env bash
#
# Baut die Kairo-Live-ISO mit dem offiziellen Archiso-Werkzeug mkarchiso.
#
# Läuft nur auf Arch Linux (z. B. WSL2 mit dem offiziellen Arch-Image).
# Läuft als NORMALER Benutzer, nicht mit sudo: archiso ab Version 89 nutzt
# dafür unshare(1) und User-Namespaces.
#
# Schreibt ausschließlich in build/ und out/ dieses Repos.
# Fasst keine Datenträger an, partitioniert nichts.
#
# Aufruf:
#   scripts/build-iso.sh
#
# Ergebnis:
#   out/kairo-0.1-JJJJ.MM.TT-x86_64.iso

set -euo pipefail

repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../iso/base.conf
source "${repo_dir}/iso/base.conf"

profile_dir="${repo_dir}/build/profile"
work_dir="${repo_dir}/build/work"
out_dir="${repo_dir}/out"

die()  { printf 'FEHLER: %s\n' "$*" >&2; exit 1; }
warn() { printf 'WARNUNG: %s\n' "$*" >&2; }
info() { printf '==> %s\n' "$*"; }

# --- Vorabprüfungen -----------------------------------------------------------

[[ -f /etc/arch-release ]] \
    || die "Kein Arch Linux. Siehe docs/01-entwicklungsumgebung.md (WSL2 + Arch)."

(( EUID != 0 )) \
    || die "Bitte NICHT als root/sudo starten. archiso >= 89 baut als normaler Benutzer."

command -v mkarchiso >/dev/null \
    || die "mkarchiso fehlt. Installieren mit: sudo pacman -S --needed archiso"

# Unter WSL liegt C:\ unter /mnt/c. Das Windows-Dateisystem kennt keine
# Linux-Dateirechte, der Build würde kaputte Rechte erzeugen oder scheitern.
case "${repo_dir}" in
    /mnt/*) die "Das Repo liegt auf einem Windows-Laufwerk (${repo_dir}). Klone es nach ~/ in WSL." ;;
esac

installed="$(pacman -Q archiso | awk '{print $2}')"
installed_major="${installed%%-*}"
if [[ "${installed_major}" != "${KAIRO_ARCHISO_VERSION}" ]]; then
    warn "archiso ${installed} installiert, Overlay wurde gegen ${KAIRO_ARCHISO_VERSION} geschrieben."
    warn "Meist ok. Bei Fehlern zuerst CHANGELOG von archiso lesen."
fi

# Ein Build braucht grob 5-10 GiB (Pakete + Arbeitsordner + ISO).
free_kib="$(df --output=avail -k -- "${repo_dir}" | tail -1)"
(( free_kib > 15 * 1024 * 1024 )) \
    || die "Weniger als 15 GiB frei unter ${repo_dir}."

# Prüfen, ob alle Kairo-Zusatzpakete in den offiziellen Repos existieren.
# Nutzt die lokale Paketdatenbank; ggf. vorher 'sudo pacman -Syu' ausführen.
missing=()
while read -r pkg; do
    pacman -Si -- "${pkg}" >/dev/null 2>&1 || missing+=("${pkg}")
done < <(sed -e 's/#.*//' -e 's/[[:space:]]//g' "${repo_dir}/iso/packages.kairo.x86_64" | awk NF)
(( ${#missing[@]} == 0 )) \
    || die "Nicht in den Repos gefunden: ${missing[*]} (Tippfehler? 'sudo pacman -Syu' gemacht?)"

# --- Profil zusammenbauen -------------------------------------------------------

"${repo_dir}/scripts/assemble-iso-profile.sh" --out "${profile_dir}"

# --- ISO bauen ----------------------------------------------------------------------
# Ein alter Arbeitsordner wird gelöscht, damit jeder Build sauber startet.
# Er liegt immer unter build/, siehe work_dir oben.
if [[ -d "${work_dir}" ]]; then
    info "Lösche alten Arbeitsordner ${work_dir}"
    rm -rf -- "${work_dir}"
fi
mkdir -p -- "${out_dir}"

info "Starte mkarchiso (dauert je nach Internet 10-30 Minuten)"
# -v  ausführliche Ausgabe
# -w  Arbeitsordner (temporär, groß)
# -o  Ausgabeordner für die fertige ISO
mkarchiso -v -w "${work_dir}" -o "${out_dir}" "${profile_dir}"

# Neueste ISO nach Datum. ls ist hier ok: Die Dateinamen erzeugen wir selbst.
# shellcheck disable=SC2012
iso="$(ls -t -- "${out_dir}"/kairo-*-x86_64.iso | head -1)"
info "Fertig: ${iso}"
info "Prüfsumme (für STATUS.md):"
sha256sum -- "${iso}"
info "Nächster Schritt: scripts/run-qemu.sh ${iso#"${repo_dir}"/}"
