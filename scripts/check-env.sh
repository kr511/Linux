#!/usr/bin/env bash
#
# Prüft, ob diese Umgebung Kairo bauen und testen kann.
# Liest nur, ändert nichts. Kein root nötig.
#
# Aufruf:
#   scripts/check-env.sh

set -uo pipefail

repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ok=0 bad=0

# check "<was gut ist>" "<was fehlt>" <Befehl...>
# Führt den Befehl aus: Erfolg = [OK], Fehlschlag = [FEHLT]
check() {
    local good="$1" missing="$2"
    shift 2
    if "$@" >/dev/null 2>&1; then
        printf '  [OK]    %s\n' "${good}"; ok=$((ok + 1))
    else
        printf '  [FEHLT] %s\n' "${missing}"; bad=$((bad + 1))
    fi
}
note() { printf '  [INFO]  %s\n' "$*"; }

free_gib=$(( $(df --output=avail -k -- "${repo_dir}" | tail -1) / 1024 / 1024 ))
mem_gib=$(( $(awk '/MemTotal/ {print $2}' /proc/meminfo) / 1024 / 1024 ))

echo "System"
check "Arch Linux" "Kein Arch Linux (ISO/Kernel-Build nicht möglich, Tests schon)" \
    test -f /etc/arch-release
grep -qi microsoft /proc/version 2>/dev/null && note "Läuft in WSL"
check "x86_64" "Architektur $(uname -m), gebraucht x86_64" test "$(uname -m)" = x86_64
check "Normaler Benutzer" "Läuft als root. Bitte als normaler Benutzer arbeiten" \
    test "${EUID}" -ne 0

echo "Speicherort"
check "Repo im Linux-Dateisystem (${repo_dir})" \
    "Repo liegt auf Windows-Laufwerk (${repo_dir}). Nach ~/ klonen" \
    test "${repo_dir#/mnt/}" = "${repo_dir}"
check "${free_gib} GiB frei" "Nur ${free_gib} GiB frei (40 GiB empfohlen)" \
    test "${free_gib}" -ge 40
check "${mem_gib} GiB RAM" "Nur ${mem_gib} GiB RAM (mind. 8 empfohlen)" \
    test "${mem_gib}" -ge 8

echo "Werkzeuge"
for t in git shellcheck python3 gpg mkarchiso makepkg updpkgsums qemu-system-x86_64; do
    check "$t" "$t" command -v "$t"
done
check "UEFI-Firmware OVMF" "OVMF (Paket edk2-ovmf)" test -f /usr/share/edk2/x64/OVMF_VARS.4m.fd

echo "Virtualisierung"
if [[ -w /dev/kvm ]]; then
    note "/dev/kvm nutzbar: VMs laufen schnell"
elif [[ -e /dev/kvm ]]; then
    note "/dev/kvm da, aber kein Zugriff: sudo usermod -aG kvm \$USER, dann neu anmelden"
else
    note "Kein /dev/kvm: QEMU läuft trotzdem, aber langsam"
fi

echo
echo "Ergebnis: ${ok} OK, ${bad} fehlen"
(( bad == 0 ))
