# 01: Entwicklungsumgebung einrichten (Windows + WSL2 + Arch)

Kairo wird unter **Arch Linux** gebaut. Unter Windows bekommst du Arch am
einfachsten über WSL2. Arch stellt dafür ein **offizielles** Image bereit
(siehe [ArchWiki: Install Arch Linux on WSL](https://wiki.archlinux.org/title/Install_Arch_Linux_on_WSL)).

WSL2 ist eine leichte virtuelle Maschine. Das Arch darin hat eine eigene
virtuelle Festplatte (eine Datei). Deine Windows-Partitionen werden dabei nicht
verändert.

## 1. WSL2 und Arch installieren (PowerShell)

PowerShell öffnen (Startmenü → "PowerShell"):

```powershell
wsl --version
```
Zeigt, ob WSL installiert ist und welche Version. Erscheint ein Fehler, zuerst
`wsl --install` ausführen (braucht einmalig Admin-Rechte und einen Neustart).

```powershell
wsl --install archlinux
```
Lädt das offizielle Arch-Image von Microsoft/Arch und richtet es ein.

```powershell
wsl -d archlinux
```
Startet Arch. Du bist jetzt in einer Linux-Shell, zunächst als `root`.

## 2. Arch vorbereiten (in der Arch-Shell, als root)

```bash
pacman -Syu
```
`-S` = installieren/synchronisieren, `-y` = Paketlisten neu laden,
`-u` = alles aktualisieren. Bei Arch immer zuerst machen.
Meckert pacman über Schlüssel: `pacman-key --init` und danach
`pacman-key --populate archlinux`, dann nochmal `pacman -Syu`.

```bash
pacman -S --needed base-devel git sudo nano archiso qemu-desktop edk2-ovmf pacman-contrib shellcheck python
```
| Paket | Wofür |
| --- | --- |
| `base-devel` | Compiler und `makepkg` (für den Kernel) |
| `git` | Repository klonen |
| `sudo`, `nano` | Admin-Befehle als normaler Benutzer, einfacher Editor |
| `archiso` | `mkarchiso` (baut die ISO) |
| `qemu-desktop` | QEMU mit grafischem Fenster |
| `edk2-ovmf` | UEFI-Firmware für QEMU |
| `pacman-contrib` | `updpkgsums` (Prüfsummen im PKGBUILD) |
| `shellcheck`, `python` | für `tests/run-all.sh` |

`--needed` überspringt Pakete, die schon installiert sind.

### Eigenen Benutzer anlegen

Bauen als `root` ist schlechte Praxis (ein Fehler im Skript kann dann alles
kaputt machen), `makepkg` verweigert es sogar.

```bash
useradd -m -G wheel kairo
```
Legt Benutzer `kairo` an (`-m` mit Home-Ordner, `-G wheel` in die Admin-Gruppe).
Den Namen kannst du frei wählen.

```bash
passwd kairo
```
Passwort setzen (wird bei `sudo` abgefragt).

```bash
EDITOR=nano visudo -f /etc/sudoers.d/wheel
```
Öffnet eine neue sudo-Regeldatei. `visudo` prüft die Syntax beim Speichern,
damit du dich nicht aussperrst. Schreibe genau diese Zeile hinein, speichere
mit `Strg+O`, `Enter`, beende mit `Strg+X`:
```
%wheel ALL=(ALL:ALL) ALL
```

```bash
printf '[user]\ndefault=kairo\n' >> /etc/wsl.conf
```
Sagt WSL, dass es künftig als `kairo` startet.

```bash
exit
```

Zurück in PowerShell, WSL neu starten:
```powershell
wsl --terminate archlinux
wsl -d archlinux
```
`whoami` sollte jetzt `kairo` zeigen.

## 3. Optional: KVM für schnelle VMs

```bash
ls -l /dev/kvm
```
Existiert die Datei, kann QEMU die Hardware-Beschleunigung nutzen. Dann:
```bash
sudo usermod -aG kvm "$USER"
```
(fügt dich der Gruppe `kvm` hinzu; danach WSL wie oben neu starten).
Fehlt `/dev/kvm`, läuft QEMU trotzdem, nur deutlich langsamer.

## 4. Repository klonen

**Wichtig:** in dein Linux-Home (`~`), **nicht** nach `/mnt/c/...`. Das
Windows-Dateisystem kennt keine Linux-Rechte; der ISO-Build würde scheitern
und alles wäre um ein Vielfaches langsamer. Die Skripte brechen dort ab.

```bash
git clone https://github.com/kr511/Linux.git ~/kairo
cd ~/kairo
```

## 5. Prüfen

```bash
scripts/check-env.sh
```
Zeigt für jede Voraussetzung `[OK]` oder `[FEHLT]`. Ändert nichts.

```bash
tests/run-all.sh
```
Führt alle automatischen Tests aus (dasselbe wie die GitHub-CI). Wenn archiso
installiert ist, wird dabei das echte releng-Profil mitgetestet.

Wenn beides grün ist: weiter mit [02: ISO bauen](02-iso-bauen.md).

## Ohne Windows 11 / ohne WSLg

QEMU öffnet ein Fenster über WSLg (in Windows 11 eingebaut). Ohne WSLg kannst
du die VM über VNC ansehen, siehe [03: QEMU](03-iso-in-qemu-testen.md).
