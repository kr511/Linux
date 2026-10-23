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

# Projektversion plus Build-Datum, z. B. 1.0-2026.10.23
iso_version="1.0-$(date --date="@${SOURCE_DATE_EPOCH:-$(date +%s)}" +%Y.%m.%d)"

# install_dir bleibt absichtlich "arch" (Standard von releng). Der Ordnername
# ist für Nutzer unsichtbar; ihn zu ändern bringt in 0.1 nur Risiko.

# Dateirechte für Kairo-Dateien. mkarchiso kopiert das Overlay ohne die
# Rechte aus Git, darum müssen ausführbare und geheime Dateien hier stehen.
# (+= ergänzt die Liste aus releng, statt sie zu ersetzen)
file_permissions+=(
  ["/etc/sudoers.d/kairo-live"]="0:0:440"
  ["/usr/local/bin/kairo-install"]="0:0:755"
  ["/usr/local/bin/kairo-install-gui"]="0:0:755"
  ["/usr/local/bin/kairo-rollback"]="0:0:755"
  ["/usr/local/bin/kairo-welcome"]="0:0:755"
)
