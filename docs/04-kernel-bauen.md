# 04: linux-kairo bauen und testen

> Das ist das Ziel von **Kairo 0.2**, nicht von 0.1. Fang erst damit an, wenn
> die ISO mit dem Arch-Kernel bootet ([Checkliste](05-checkliste-kairo-0.1.md)).

## Was ein "eigener Kernel" hier bedeutet

`linux-kairo` ist **derselbe Quellcode** wie bei jedem anderen Linux, direkt
von kernel.org, unverändert. Eigen ist:

1. die **Konfiguration**: welche Treiber und Funktionen eingebaut werden,
2. der **Name**: `uname -r` zeigt z. B. `7.2.12-1-kairo`,
3. später eventuell **Patches** (erst nach erfolgreichen Boot-Tests).

Als Basis dient die Arch-Config. Die ist auf tausenden PCs erprobt. Darauf
legen wir `kairo.config` mit 47 Pflichtoptionen für deine Hardware:

| Bereich | Wichtigste Optionen | Wofür |
| --- | --- | --- |
| Ryzen 5 4500 (Zen 2) | `X86_AMD_PSTATE`, `AMD_IOMMU`, `SENSORS_K10TEMP` | Taktsteuerung, Geräte-Isolation, Temperatur |
| RX 6500 XT (RDNA2) | `DRM_AMDGPU`, `DRM_AMD_DC`, `HSA_AMD` | Grafiktreiber, Bildausgabe, Compute |
| Speicher | `BLK_DEV_NVME`, `SATA_AHCI` | NVMe-SSDs und SATA-Platten |
| USB | `USB_XHCI_HCD`, `USB_STORAGE`, `USB_UAS` | USB 3, USB-Sticks |
| Dateisysteme | `EXT4_FS`, `BTRFS_FS`, `VFAT_FS`, `NTFS3_FS`, `SQUASHFS`, `OVERLAY_FS` | Linux-Partitionen, EFI-Partition, Windows lesen, Live-ISO |
| Virtualisierung | `KVM_AMD`, `VIRTIO_*`, `DRM_VIRTIO_GPU` | Selbst VMs hosten und in QEMU getestet werden |

Alle Optionen sind gegen den echten Kconfig-Code von 7.2.12 geprüft. Die CI
wiederholt das bei jedem Push (Job `kernel-config`).

**Wichtig zur GPU:** Der Treiber `amdgpu` braucht Firmware-Dateien für deine
Karte (Codename "beige_goby"). Die kommen aus dem Paket `linux-firmware`,
nicht aus dem Kernel. Ohne sie: schwarzer Bildschirm.

## Schritt 1: Basis-Config importieren (einmalig)

```bash
sudo pacman -S --needed linux-headers
```
Installiert die Header des offiziellen Arch-Kernels. Darin steckt dessen
komplette Config. Das sind nur Dateien in `/usr/lib/modules/`, in WSL wird
davon nichts gebootet.

```bash
scripts/kernel-import-arch-config.sh
```
Kopiert diese Config nach `kernel/linux-kairo/config.arch-base` und schreibt
oben hinein, aus welcher Version sie stammt.

Warum nicht `/proc/config.gz`? In WSL ist das die Config des
**Microsoft-Kernels**, auf dem WSL läuft. Die passt nicht zu Arch.

## Schritt 2: Signaturschlüssel und Prüfsummen

```bash
gpg --locate-keys gregkh@kernel.org
```
Holt den Schlüssel von Greg Kroah-Hartman über kernel.org (per HTTPS
abgesichert). Er signiert alle Stable-Releases wie 7.2.12. `makepkg` prüft
damit, dass der heruntergeladene Quellcode echt ist.

Vergleiche den Fingerprint mit dem im PKGBUILD:
```bash
gpg --fingerprint gregkh@kernel.org
```
Erwartet: `647F 2865 4894 E3BD 4571  99BE 38DB BDC8 6092 693E`.

```bash
cd kernel/linux-kairo
updpkgsums
cd ../..
```
Lädt die Quellen und trägt die echten SHA-256-Summen ins PKGBUILD ein (statt
`SKIP`). Danach committen:

```bash
git add kernel/linux-kairo/config.arch-base kernel/linux-kairo/PKGBUILD
git commit -m "linux-kairo: Arch-Basis-Config und Prüfsummen"
```

## Schritt 3: Bauen

```bash
scripts/build-kernel.sh
```
Ruft `makepkg --syncdeps --cleanbuild` auf:
- `--syncdeps` installiert fehlende Build-Werkzeuge (fragt vorher nach),
- `--cleanbuild` startet jedes Mal frisch.

Die Ausgabe landet zusätzlich in `kernel/linux-kairo/build.log`.

Was in `prepare()` passiert, siehst du in der Ausgabe:
1. `Setting config...`: Basis + Fragment zusammenführen, `make olddefconfig`
2. ein `diff` zwischen Arch-Config und Ergebnis: **das sind genau deine
   Kairo-Änderungen.** Lies ihn einmal durch.
3. `Verifying Kairo requirements...` → `OK: alle 47 Kairo-Optionen sind erfüllt.`

Danach kompiliert der Kernel. Mit der Arch-Config (sehr viele Module) dauert
das auf einem Ryzen 5 4500 grob 1 bis 2 Stunden. Ergebnis:

```
kernel/linux-kairo/linux-kairo-7.2.12-1-x86_64.pkg.tar.zst
kernel/linux-kairo/linux-kairo-headers-7.2.12-1-x86_64.pkg.tar.zst
```

## Schritt 4: Smoke-Test (Stufe 1)

```bash
scripts/kernel-smoke-test.sh
```

Packt nur den Kernel aus dem Paket in einen Temp-Ordner aus und bootet ihn in
QEMU, **ohne Festplatte und ohne Initramfs**. Ergebnis `BESTANDEN` heißt:

- der Kernel lädt, entpackt sich und läuft (`Linux version 7.2.12-1-kairo ...`),
- er kommt bis zur Suche nach dem Root-Dateisystem
  (`VFS: Unable to mount root fs`). Dass er keins findet, ist hier **richtig**,
  wir geben ihm ja keins.

Das ist ein Minimaltest: Module, amdgpu und Dateisysteme werden dabei nicht
geprüft. Aber er fängt die groben Fehler (falsche Architektur, kaputtes Image)
in einer Minute statt nach einer Stunde Fehlersuche.

## Schritt 5: Voller Test (Stufe 2, Plan für 0.2)

Noch nicht ausgearbeitet, damit 0.1 klein bleibt. Der Plan:

1. In QEMU eine Test-VM mit einer **virtuellen** Festplatte (eine
   `.qcow2`-Datei in `build/`) anlegen und dort Arch installieren.
2. `linux-kairo` per `pacman -U` **in der VM** installieren und davon booten.
3. Prüfen: `uname -r`, `lsmod`, Dateisysteme mounten, `dmesg` ohne Fehler.
4. Erst danach: `linux-kairo` in die ISO (Kairo 0.3) und auf echter Hardware
   die RX 6500 XT testen.

## Version aktualisieren

1. Neue Version auf [kernel.org](https://www.kernel.org) nachsehen.
2. Im PKGBUILD `pkgver` ändern, `pkgrel=1` setzen.
3. Ggf. Basis-Config neu importieren (Schritt 1), `updpkgsums` (Schritt 2).
4. `tests/run-all.sh`, bauen, Smoke-Test, `STATUS.md` aktualisieren.

Für eine x.y.0-Version (z. B. 7.3) brauchst du zusätzlich den Schlüssel von
Linus Torvalds: `gpg --locate-keys torvalds@kernel.org`, Fingerprint mit
[kernel.org/signature.html](https://www.kernel.org/signature.html) vergleichen
und in `validpgpkeys` eintragen.
