# Kairo OS

Kairo OS ist eine eigene, bootfähige x86_64-Linux-Distribution auf Basis von
Arch Linux: fertig eingerichtet zum Spielen und Arbeiten, mit Live-ISO,
Installer und eigenem Design. Später: eigener Kernel `linux-kairo`.

> **Stand:** Kairo 1.0. GNOME im Kairo-Design mit grafischem Installer,
> Snapshots und Zurückrollen, optionaler Verschlüsselung und Kairo Update.
> Dabei: Steam, Roblox (Sober), Discord, Spotify, VS Code, Claude/ChatGPT,
> Claude Code und Codex im Terminal, eingestellt für AMD.
>
> **Download:** https://github.com/kr511/Linux/releases/latest ·
> **Installieren:** [`docs/06-installieren.md`](docs/06-installieren.md)
>
> Was davon wirklich gebaut und getestet wurde, steht **nur** in
> [`STATUS.md`](STATUS.md).

## Aufbau

| Ordner | Inhalt |
| --- | --- |
| [`iso/`](iso/) | Kairo-Anpassungen für das offizielle Archiso-Profil `releng`, Installer und Kairo-Apps |
| [`branding/`](branding/) | Logo, Schriftzug, Hintergrund (SVG), daraus erzeugt `scripts/render-branding.sh` die Bilder |
| [`kernel/`](kernel/) | `linux-kairo`: PKGBUILD, Kernel-Konfiguration, dokumentierte Patches |
| [`desktop/`](desktop/) | Platzhalter (der GNOME-Desktop steckt in `iso/airootfs/`) |
| [`packages/`](packages/) | Platzhalter für eigene Pakete |
| [`scripts/`](scripts/) | Build- und Testskripte |
| [`tests/`](tests/) | Automatische Prüfungen (laufen auch in der CI) |
| [`docs/`](docs/) | Anfänger-Dokumentation, **hier anfangen** |
| [`.github/workflows/`](.github/workflows/) | Nichtprivilegierte CI-Prüfungen |

## Schnellstart

1. Lies [`docs/00-ueberblick.md`](docs/00-ueberblick.md).
2. Richte die Build-Umgebung ein: [`docs/01-entwicklungsumgebung.md`](docs/01-entwicklungsumgebung.md).
3. Baue die ISO: [`docs/02-iso-bauen.md`](docs/02-iso-bauen.md).
4. Teste sie in QEMU: [`docs/03-iso-in-qemu-testen.md`](docs/03-iso-in-qemu-testen.md).
5. Hake die Checkliste ab: [`docs/05-checkliste-kairo-0.1.md`](docs/05-checkliste-kairo-0.1.md). **Damit ist Kairo 0.1 fertig.**
6. Danach (Kairo 0.2) der eigene Kernel: [`docs/04-kernel-bauen.md`](docs/04-kernel-bauen.md).

## Grundregeln

- Gebaut und getestet wird nur in einer Arch-Linux-Umgebung (WSL2 oder VM),
  nie direkt auf echten Datenträgern.
- Keine Skripte aus dem Internet ungeprüft ausführen.
- Nur offizielle Quellen: archlinux.org, kernel.org, die Arch-Paketquellen.
