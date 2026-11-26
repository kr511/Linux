# 07: Kairo auf deinem PC testen (nur du kannst das)

Alles, was in einer VM geht, prüft GitHub Actions bei jedem Release
automatisch (siehe [`STATUS.md`](../STATUS.md)). Was übrig bleibt, hängt an
echter Hardware: deine RX 6500 XT, dein WLAN/LAN, Ton, Standby, die echte SSD.
Diese Liste ist dafür da. Dauer: etwa eine Stunde plus Download.

**Vorher:** [Schritt 0 aus 06-installieren.md](06-installieren.md#0-vorher-erledigen-die-gewählte-platte-wird-unwiederbringlich-gelöscht)
abhaken. Die **Windows-SSD abstecken**, solange du installierst.

## A. Live-System (nichts wird installiert)

Am einfachsten mit **Claudus** unter Windows
([`windows/claudus`](../windows/claudus/README.md)): Vorab-Check, ISO laden und
prüfen, Stick schreiben und zurücklesen, Spickzettel mit deinen Tasten.
Von Hand: ISO von https://github.com/kr511/Linux/releases/latest, Prüfsumme
vergleichen, mit Rufus im **DD-Modus** auf den Stick. Dann Secure Boot aus,
UEFI an.

| # | Prüfen | Erwartet | ✓ |
| --- | --- | --- | --- |
| A1 | Stick starten | Bootmenü, dann Kairo-Boot-Animation, dann GNOME | |
| A2 | Bild | Volle Auflösung deines Monitors, kein Flackern | |
| A3 | Startbildschirm | GNOME zeigt zuerst die Übersicht. Das Fenster "Willkommen bei Kairo OS" anklicken (oder `Esc`) | |
| A4 | **Hardware prüfen** im Willkommensfenster | Grafik: AMD (amdgpu), Internet, Ton, Festplatte grün | |
| A5 | LAN bzw. WLAN (oben rechts) | Webseite in Firefox lädt | |
| A6 | Ton | YouTube in Firefox, Ton kommt aus Lautsprecher/Headset | |
| A7 | USB | Zweiten USB-Stick einstecken, erscheint in "Dateien" | |

Wenn A2, A4 oder A5 nicht passen: **nicht installieren**, sondern Foto vom
Bildschirm machen und melden.

## B. Installation

| # | Prüfen | Erwartet | ✓ |
| --- | --- | --- | --- |
| B1 | Willkommen → **Installieren** | Installer-Fenster öffnet sich | |
| B2 | Laufwerksliste | Nur deine leere SSD, mit Modell und **Seriennummer**. Seriennummer mit dem Aufkleber/Karton vergleichen | |
| B3 | Verschlüsselung | "Verschlüsseln" ist vorausgewählt. Passwort merken bzw. aufschreiben | |
| B4 | Zusammenfassung | Richtige SSD, `LÖSCHEN` eintippen | |
| B5 | Installation | Balken läuft durch, "Kairo ist installiert" | |

## C. Installiertes System

USB-Stick nach dem Herunterfahren abziehen.

| # | Prüfen | Erwartet | ✓ |
| --- | --- | --- | --- |
| C1 | Start | Bootmenü (5 s), Passwortdialog der Verschlüsselung mit **deutscher** Tastatur (y/z!), dann Anmeldung | |
| C2 | Eintrag "Kairo OS (Notfall)" einmal starten | Startet ebenfalls bis zur Anmeldung | |
| C3 | Nach dem Anmelden ein paar Minuten warten | Roblox (Sober), Spotify, VS Code im App-Menü | |
| C4 | Terminal: `vulkaninfo --summary \| grep deviceName` | `AMD Radeon RX 6500 XT (RADV ...)` | |
| C5 | Steam: ein Spiel mit `MANGOHUD=1 gamemoderun %command%` starten | Spiel läuft, MangoHud zeigt GPU-Last und FPS | |
| C6 | Discord und ChatGPT starten, anmelden | Beide laufen | |
| C7 | Ton und Mikrofon (z. B. Discord-Sprachtest) | Geht | |
| C8 | Standby (oben rechts → Ausschalten → Bereitschaft), dann Taste drücken | Wacht auf, Bild und Netzwerk wieder da | |
| C9 | **Kairo Update** öffnen und Updates installieren, neu starten | Startet normal | |
| C10 | **Kairo Wiederherstellen**: Eintrag "vor Update" wählen, neu starten | Startet normal, Stand von vor dem Update | |
| C11 | Terminal: `systemctl is-active nftables` | `active` | |

Erst danach die **Windows-SSD wieder anschließen** und im UEFI-Setup die
Startreihenfolge einstellen (Kairo-SSD zuerst; Windows über das Boot-Menü
der Firmware, meist `F8`/`F11`/`F12`).

## D. Ergebnis melden

Am einfachsten: diese Tabelle abfotografieren oder in einem neuen Issue auf
GitHub abhaken. Bei Problemen zusätzlich:

```
journalctl -b -p err --no-pager | tail -n 50
sudo dmesg | grep -iE "amdgpu|firmware" | tail -n 30
```

Danach trägt jemand (du oder Claude) das Ergebnis mit Datum, Kairo-Version und
Hardware in [`STATUS.md`](../STATUS.md) ein. Erst dann wird dort die Zeile
"Installation auf deinem echten PC" grün.
