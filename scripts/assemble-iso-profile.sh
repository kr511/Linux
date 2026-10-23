#!/usr/bin/env bash
#
# Baut das fertige Kairo-Archiso-Profil zusammen:
#
#   offizielles releng-Profil  +  Kairo-Overlay aus iso/  =  build/profile/
#
# Das Skript ändert NUR Dateien im Ausgabeordner. Es lädt nichts herunter,
# braucht kein root und fasst keine Datenträger an.
#
# Aufruf:
#   scripts/assemble-iso-profile.sh [--base DIR] [--out DIR]
#
#   --base DIR  Ordner des Upstream-Profils
#               (Standard: /usr/share/archiso/configs/<KAIRO_BASE_PROFILE>)
#   --out DIR   Zielordner (Standard: build/profile im Repo).
#               Muss leer bzw. nicht vorhanden sein, ODER unter build/ liegen.

set -euo pipefail

repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
iso_dir="${repo_dir}/iso"

# shellcheck source=../iso/base.conf
source "${iso_dir}/base.conf"

base_dir="/usr/share/archiso/configs/${KAIRO_BASE_PROFILE}"
out_dir="${repo_dir}/build/profile"

die() { printf 'FEHLER: %s\n' "$*" >&2; exit 1; }
info() { printf '==> %s\n' "$*"; }

while (( $# )); do
    case "$1" in
        --base) base_dir="${2:?--base braucht einen Ordner}"; shift 2 ;;
        --out)  out_dir="${2:?--out braucht einen Ordner}"; shift 2 ;;
        -h|--help) sed -n '2,18p' "${BASH_SOURCE[0]}"; exit 0 ;;
        *) die "Unbekannte Option: $1" ;;
    esac
done

[[ -f "${base_dir}/profiledef.sh" ]] \
    || die "Kein Archiso-Profil in '${base_dir}'. Ist das Paket 'archiso' installiert?"

# --- Sicherheitscheck, bevor irgendetwas gelöscht wird -----------------------
# Wir löschen einen alten Ausgabeordner nur, wenn er innerhalb von build/ liegt.
# So kann ein Tippfehler bei --out niemals z. B. dein Home-Verzeichnis leeren.
out_dir="$(realpath -m -- "${out_dir}")"
if [[ -e "${out_dir}" ]]; then
    case "${out_dir}/" in
        "${repo_dir}/build/"?*) rm -rf -- "${out_dir}" ;;
        *) [[ -z "$(ls -A -- "${out_dir}")" ]] \
               || die "'${out_dir}' existiert, ist nicht leer und liegt nicht unter build/. Abbruch." ;;
    esac
fi

# --- 1. Upstream-Profil kopieren ----------------------------------------------
info "Kopiere ${base_dir} -> ${out_dir}"
mkdir -p -- "${out_dir}"
cp -a -- "${base_dir}/." "${out_dir}/"

# --- 2. Kairo-Dateien ins Live-Dateisystem legen -------------------------------
# Gleichnamige Dateien (z. B. etc/hostname, etc/motd) werden überschrieben.
info "Lege Kairo-Overlay iso/airootfs/ darüber"
cp -a -- "${iso_dir}/airootfs/." "${out_dir}/airootfs/"

# Bootmenü-Hintergrund im BIOS-Modus (Kairo-Logo statt Arch-Logo)
info "Lege Kairo-Dateien iso/syslinux/ über syslinux/"
cp -a -- "${iso_dir}/syslinux/." "${out_dir}/syslinux/"

# --- 3. profiledef.sh: Kairo-Werte anhängen ------------------------------------
info "Hänge iso/profiledef.kairo.sh an profiledef.sh an"
{
    printf '\n# ---- Ab hier: Kairo-Overlay (iso/profiledef.kairo.sh) ----\n'
    cat -- "${iso_dir}/profiledef.kairo.sh"
} >> "${out_dir}/profiledef.sh"

# --- 4. Paketliste: releng + Kairo - Entfernte, ohne Duplikate -----------------
# Kommentare und Leerzeilen fliegen raus, die Reihenfolge bleibt erhalten.
info "Ergänze Paketliste um iso/packages.kairo.x86_64, ohne iso/packages.remove.x86_64"
clean_list() { sed -e 's/#.*//' -e 's/[[:space:]]//g' -- "$@" | awk NF; }
cat -- "${out_dir}/packages.x86_64" "${iso_dir}/packages.kairo.x86_64" \
    | sed -e 's/#.*//' -e 's/[[:space:]]//g' \
    | awk 'NF && !seen[$0]++' \
    | grep -vxF -f <(clean_list "${iso_dir}/packages.remove.x86_64") \
    > "${out_dir}/packages.x86_64.new"
mv -- "${out_dir}/packages.x86_64.new" "${out_dir}/packages.x86_64"

# --- 5. Bootmenü-Titel umbenennen ---------------------------------------------
# Nur sichtbare Texte, keine internen IDs oder Pfade.
info "Setze Kairo-Namen in den Bootmenüs (systemd-boot, syslinux, GRUB)"
while IFS= read -r -d '' f; do
    sed -i \
        -e 's/Arch Linux install medium/Kairo OS Live/g' \
        -e 's/Arch Linux live medium/Kairo OS Live/g' \
        -e 's/^MENU TITLE Arch Linux$/MENU TITLE Kairo OS/' \
        -e 's/#9033ccff/#ff4cc38a/' \
        -e 's/Boot the Kairo OS Live on BIOS/Kairo OS Live im BIOS-Modus starten/' \
        -e 's/ with speakup screen reader/ mit Sprachausgabe/' \
        -e 's/It allows you to install Arch Linux or perform system maintenance\./Startet Kairo vom USB-Stick, von dort kannst du Kairo installieren./' \
        -- "$f"
done < <(find "${out_dir}/efiboot" "${out_dir}/syslinux" "${out_dir}/grub" \
              -type f \( -name '*.conf' -o -name '*.cfg' \) -print0 2>/dev/null)

info "Fertig. Profil liegt in: ${out_dir}"
