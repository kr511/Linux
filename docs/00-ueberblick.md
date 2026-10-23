# 00: Überblick und Architektur

## Was Kairo OS technisch ist

Kairo OS ist eine **Arch-basierte Distribution**. Das heißt ehrlich gesagt:
Kairo erfindet nicht alles neu, sondern nimmt Arch Linux (Pakete, Paketmanager
`pacman`, Werkzeuge) und legt eigene Teile darüber: eigenes Branding, eigene
Live-ISO, später eigener Kernel und eigener Desktop. So machen es auch
EndeavourOS, Manjaro oder Omarchy. Ein komplett eigenes System ohne Basis
(wie "Linux From Scratch") wäre für den Anfang zehnmal mehr Arbeit für fast
keinen Mehrwert.

## Die drei Bausteine

```
 ┌─────────────────────────────────────────────────────────────┐
 │  Kairo-Live-ISO   (iso/  +  scripts/build-iso.sh)           │
 │                                                             │
 │   Bootloader ─► Kernel ─► Initramfs ─► Live-System          │
 │   (systemd-boot  (0.1: Arch  (findet die   (squashfs mit    │
 │    bzw. syslinux) "linux")    ISO, mountet  allen Paketen)  │
 │                               sie)                          │
 └──────────────────────────▲──────────────────────────────────┘
                            │ erst NACH eigenem Boot-Test
 ┌──────────────────────────┴──────────────────────────────────┐
 │  linux-kairo   (kernel/linux-kairo/PKGBUILD)                │
 │   kernel.org-Quellcode + Arch-Config + kairo.config         │
 └─────────────────────────────────────────────────────────────┘
 ┌─────────────────────────────────────────────────────────────┐
 │  Desktop + Installer (ab 0.2): GNOME, kairo-install         │
 └─────────────────────────────────────────────────────────────┘
```

## Fahrplan

| Version | Ziel | Fertig, wenn ... |
| --- | --- | --- |
| 0.1 ✅ | Live-ISO mit Kairo-Branding, offizieller Arch-Kernel | ISO bootet in QEMU (UEFI), siehe [Checkliste](05-checkliste-kairo-0.1.md) |
| **0.2** | GNOME-Live-System, Installer `kairo-install`, Gaming-Apps, AMD-Optimierung (Kernel `linux-zen`) | Installationstest in der CI grün, dann auf deinem PC, siehe [06: Installieren](06-installieren.md) |
| 0.3 | `linux-kairo` einzeln gebaut und getestet | Kernel bootet in einer VM |
| 0.4 | `linux-kairo` im installierten System | Kernel bootet auf deinem PC |

Immer nur **eine** neue Unbekannte pro Schritt. Wenn ISO und Kernel gleichzeitig
neu sind und es nicht bootet, weißt du nicht, wer schuld ist.

## Wo was gebaut wird

| Was | Wo | Warum |
| --- | --- | --- |
| Tests (`tests/run-all.sh`) | überall, auch GitHub-CI | lesen nur Dateien |
| ISO bauen | Arch Linux (bei dir: WSL2) | `mkarchiso` gibt es nur für Arch |
| Kernel bauen | Arch Linux (WSL2) | `makepkg` ist das Arch-Bauwerkzeug |
| Testen | QEMU (virtuelle Maschine) | kann deinem PC nichts tun |

Die normale CI (`ci.yml`) baut absichtlich **keine** ISO. Das macht der
eigene Workflow `iso.yml` auf einer frischen, einmaligen GitHub-VM, siehe
[02: ISO bauen](02-iso-bauen.md#ohne-eigene-arch-umgebung-in-der-cloud-bauen).

## Sicherheitsregeln

1. **Keine echten Datenträger beim Bauen und Testen.** Alles läuft in Ordnern
   unter `build/` und `out/` oder in QEMU. Kein Build- oder Testskript ruft
   `dd`, `mkfs`, `fdisk` oder Ähnliches auf.
2. **Genau eine Ausnahme: `kairo-install`.** Der Installer (ab 0.2) löscht
   die Festplatte, die du auswählst. Er läuft nur im Live-System, nie von
   selbst, zeigt vorher die Festplatte an und macht erst weiter, wenn du
   `LÖSCHEN` eintippst. Der USB-Stick, von dem Kairo läuft, steht gar nicht
   erst zur Auswahl.
3. **Nichts blind aus dem Internet ausführen.** Kein `curl ... | bash`.
   Pakete kommen aus den signierten Arch-Repos, der Kernel als
   PGP-signierter Tarball von kernel.org.
4. **Vorbereitet ≠ getestet.** Was wirklich lief, steht in [`STATUS.md`](../STATUS.md).

## Glossar

| Begriff | Bedeutung |
| --- | --- |
| **Kernel** | Der Kern des Betriebssystems: redet mit Hardware, verteilt CPU und RAM |
| **Modul** | Teil des Kernels, der erst bei Bedarf geladen wird (z. B. `amdgpu`) |
| **Kernel-Config** (`.config`) | Liste von ~10.000 Schaltern: welche Treiber/Funktionen rein, welche raus |
| **Initramfs** | Mini-System im RAM, das der Kernel zuerst startet, um das echte System zu finden |
| **Bootloader** | Programm, das die Firmware startet und das dann den Kernel lädt |
| **UEFI** | Moderne PC-Firmware (Nachfolger des BIOS); dein PC nutzt UEFI |
| **OVMF** | UEFI-Firmware für virtuelle Maschinen |
| **QEMU** | Programm, das einen kompletten PC simuliert |
| **KVM** | Hardware-Beschleunigung für QEMU unter Linux |
| **pacman** | Paketmanager von Arch |
| **PKGBUILD** | Bauanleitung für ein Arch-Paket (ein Bash-Skript) |
| **makepkg** | Werkzeug, das ein PKGBUILD in ein installierbares Paket verwandelt |
| **archiso / mkarchiso** | Offizielles Arch-Werkzeug zum Bauen von Live-ISOs |
| **Profil** | Ordner, der archiso sagt, was in die ISO kommt |
| **airootfs** | Dateien, die ins Live-Dateisystem kopiert werden |
| **squashfs** | Komprimiertes, schreibgeschütztes Dateisystem, in dem das Live-System steckt |
| **WSL2** | "Windows-Subsystem für Linux": echtes Linux in einer leichten VM unter Windows |
