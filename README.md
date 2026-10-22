# Kairo OS

Kairo OS ist eine eigene, bootfähige x86_64-Linux-Distribution auf Basis von
Arch Linux. Langfristiges Ziel: eigene Live-ISO, eigener Kernel `linux-kairo`
und eine von Omarchy/Hyprland inspirierte Desktopumgebung.

> **Stand:** Phase 1 (Kairo 0.1). Was davon wirklich gebaut und getestet
> wurde, steht **nur** in [`STATUS.md`](STATUS.md). Alles andere gilt als
> "vorbereitet, aber ungetestet".

## Aufbau

| Ordner | Inhalt |
| --- | --- |
| [`iso/`](iso/) | Kairo-Anpassungen für das offizielle Archiso-Profil `releng` |
| [`kernel/`](kernel/) | `linux-kairo`: PKGBUILD, Kernel-Konfiguration, dokumentierte Patches |
| [`desktop/`](desktop/) | Platzhalter für die spätere Desktopintegration |
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
5. Hake die Checkliste ab: [`docs/05-checkliste-kairo-0.1.md`](docs/05-checkliste-kairo-0.1.md).

## Grundregeln

- Gebaut und getestet wird nur in einer Arch-Linux-Umgebung (WSL2 oder VM),
  nie direkt auf echten Datenträgern.
- Keine Skripte aus dem Internet ungeprüft ausführen.
- Nur offizielle Quellen: archlinux.org, kernel.org, die Arch-Paketquellen.
