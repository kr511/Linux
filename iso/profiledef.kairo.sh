# shellcheck shell=bash disable=SC2034
#
# Kairo-Überschreibungen für profiledef.sh
#
# Dieser Block wird ans ENDE der originalen releng/profiledef.sh angehängt.
# Weil profiledef.sh ein Bash-Skript ist, das mkarchiso einliest ("source"),
# gewinnt bei doppelt gesetzten Variablen die letzte Zuweisung. So ändern wir
# nur, was Kairo wirklich anders macht, und erben alles andere (Bootmodi,
# Kompression, Dateirechte) unverändert vom offiziellen Profil.

# Dateiname der ISO: kairo-<iso_version>-x86_64.iso
iso_name="kairo"

# Datenträger-Bezeichnung (max. 32 Zeichen, nur Großbuchstaben/Ziffern/_)
iso_label="KAIRO_$(date --date="@${SOURCE_DATE_EPOCH:-$(date +%s)}" +%Y%m)"

iso_publisher="Kairo OS <https://github.com/kr511/Linux>"
iso_application="Kairo OS Live"

# Projektversion plus Build-Datum, z. B. 0.1-2026.10.22
iso_version="0.1-$(date --date="@${SOURCE_DATE_EPOCH:-$(date +%s)}" +%Y.%m.%d)"

# install_dir bleibt absichtlich "arch" (Standard von releng). Der Ordnername
# ist für Nutzer unsichtbar; ihn zu ändern bringt in 0.1 nur Risiko.
