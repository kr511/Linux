#!/usr/bin/env bash
#
# Führt alle statischen Prüfungen aus. Dasselbe macht die CI.
# Ändert nichts, lädt nichts herunter, braucht kein root.
#
# Aufruf:
#   tests/run-all.sh
#
# Optional (sonst werden diese Tests übersprungen):
#   KAIRO_RELENG_DIR=<pfad zu archiso/configs/releng>
#   KAIRO_KERNEL_SRC=<pfad zum Linux-Quellbaum passend zu pkgver>

set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."

echo "==> shellcheck: Skripte"
shellcheck -x scripts/*.sh tests/*.sh iso/profiledef.kairo.sh \
    iso/airootfs/usr/local/bin/* \
    iso/airootfs/usr/local/share/kairo/target/usr/local/bin/* \
    iso/airootfs/usr/local/share/kairo/selftest/kairo-selftest

echo "==> shellcheck: PKGBUILD"
# Ausnahmen, weil makepkg diese Variablen setzt bzw. weil wir bewusst nah am
# offiziellen Arch-PKGBUILD bleiben:
#   SC2034 Variable "unbenutzt" (liest makepkg)
#   SC2154 Variable nicht gesetzt (setzt makepkg, z. B. $pkgdir, $STRIP_*)
#   SC2164 cd ohne || exit (makepkg bricht bei Fehlern ohnehin ab)
#   SC2086 $STRIP_* absichtlich ungequotet (mehrere Optionen)
#   SC2155 export mit $(...) wie im Arch-PKGBUILD
#   SC2295 ${_p#$pkgbase} wie im Arch-PKGBUILD, pkgbase hat keine Sonderzeichen
shellcheck -s bash -e SC2034,SC2154,SC2164,SC2086,SC2155,SC2295 \
    kernel/linux-kairo/PKGBUILD

echo "==> Python-Tests"
python3 -m unittest discover -s tests -v

echo "==> Alle Prüfungen bestanden."
