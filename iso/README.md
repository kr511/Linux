# iso/: Kairo-Overlay für Archiso

Hier liegt **kein komplettes** Archiso-Profil, sondern nur das, was Kairo
anders macht als das offizielle Arch-Profil `releng` (das ist das Profil, aus
dem die echte Arch-Install-ISO gebaut wird).

```
offizielles releng (aus Paket archiso)   +   iso/ (dieser Ordner)
                 \                              /
            scripts/assemble-iso-profile.sh
                            |
                      build/profile/        <- fertiges Profil
                            |
                        mkarchiso
                            |
              out/kairo-0.1-JJJJ.MM.TT-x86_64.iso
```

Warum so? Würden wir releng komplett kopieren, müssten wir jede Änderung von
archiso (z. B. umbenannte Bootmodi in Version 86) selbst nachziehen. So erben
wir Bootloader, Initramfs und Dateirechte automatisch, und unser Diff bleibt
klein und lesbar.

## Dateien

| Datei | Zweck |
| --- | --- |
| `base.conf` | Welches Upstream-Profil, gegen welche archiso-Version geschrieben (91) |
| `profiledef.kairo.sh` | Name, Label, Herausgeber, Version der ISO. Wird an `profiledef.sh` angehängt |
| `packages.kairo.x86_64` | Zusatzpakete (an releng-Liste angehängt, Duplikate entfernt) |
| `airootfs/etc/hostname` | Hostname im Live-System: `kairo` |
| `airootfs/etc/motd` | Begrüßungstext nach dem Login |
| `airootfs/usr/local/share/kairo/os-release` | Kairo-Identität (`NAME`, `ID=kairo`, `ID_LIKE=arch`) |
| `airootfs/etc/pacman.d/hooks/kairo-os-release.hook` | Kopiert die os-release beim Build an ihren Platz, löscht sich danach selbst |

Zusätzlich ersetzt das Assembly-Skript in den Bootmenüs den sichtbaren Text
"Arch Linux install medium" durch "Kairo OS Live".

## Bewusst NICHT geändert (in 0.1)

- Kernel: offizieller Arch-Kernel `linux`. `linux-kairo` kommt erst nach
  eigenem Boot-Test (siehe `kernel/`).
- `install_dir` bleibt `arch`: unsichtbar für Nutzer, Ändern bringt nur Risiko.
- Pakete aus releng werden nicht entfernt (z. B. `archinstall`). Das Live-System
  installiert nichts von selbst. `archinstall` tut nur etwas, wenn du es
  bewusst startest.
