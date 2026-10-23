#!/usr/bin/env bash
#
# Erzeugt alle Kairo-Bilder (PNG) aus den Vorlagen in branding/.
# Die PNGs liegen fertig im Repo, damit der ISO-Build kein Grafikprogramm
# braucht. Nur nach Änderungen an branding/*.svg neu ausführen.
#
# Braucht: rsvg-convert (Arch: librsvg, Debian/Ubuntu: librsvg2-bin)
#
# Aufruf:
#   scripts/render-branding.sh

set -euo pipefail

repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
src="${repo_dir}/branding"
dst="${repo_dir}/iso/airootfs/usr/local/share/kairo/branding"

command -v rsvg-convert >/dev/null || { echo "FEHLER: rsvg-convert fehlt" >&2; exit 1; }
mkdir -p -- "${dst}"

# Desktop-Hintergrund (4K, skaliert GNOME selbst herunter)
rsvg-convert -w 3840 -h 2160 "${src}/kairo-wallpaper.svg" -o "${dst}/wallpaper.png"
# Anmeldebildschirm (GDM): heller Schriftzug unten in der Mitte
rsvg-convert -h 72 "${src}/kairo-wordmark-light.svg" -o "${dst}/gdm-logo.png"
# Boot-Animation (Plymouth): Logo über dem Ladekreis
rsvg-convert -w 160 "${src}/kairo-logo.svg" -o "${dst}/plymouth-watermark.png"
# Bootmenü im BIOS-Modus (syslinux), muss genau 640x480 sein
rsvg-convert -w 640 -h 480 "${src}/syslinux-splash.svg" -o "${repo_dir}/iso/syslinux/splash.png"
# Vektor-Dateien für Symbole (os-release LOGO, Über-Dialog)
cp -- "${src}/kairo-logo.svg" "${src}/kairo-wordmark-light.svg" "${src}/kairo-wordmark-dark.svg" "${dst}/"

echo "==> Fertig: ${dst}"
