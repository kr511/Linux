# 06: Kairo auf deinem PC installieren

> **Achtung:** `kairo-install` löscht die **ganze** Festplatte, die du
> auswählst, inklusive Windows und aller Dateien darauf. Sichere vorher alles,
> was du behalten willst (Fotos, Spielstände, Dokumente).

## Was du bekommst

| Bereich | Was installiert wird |
| --- | --- |
| Desktop | GNOME (dunkles Design, deutsche Tastatur, Fensterknöpfe wie bei Windows) |
| Kernel | `linux-zen` (für Desktop und Spiele optimiert), AMD-Microcode |
| Grafik | AMD: Mesa, Vulkan (`vulkan-radeon`, auch 32 Bit für Steam), FreeSync an |
| Spiele | Steam (mit Proton), Roblox über **Sober**, GameMode, MangoHud, Gamescope |
| Apps | Firefox, Discord, Spotify, VS Code, Claude und ChatGPT als Web-Apps, Claude Code im Terminal |
| System | zram-Swap, Bluetooth, PipeWire (Ton), WLAN über NetworkManager |

**Roblox:** Der normale Roblox-Client läuft auf Linux nicht, auch nicht mit
Wine, weil der Anti-Cheat das blockiert. Sober ist die Android-Version von
Roblox für Linux. Die meisten Spiele laufen, aber nicht alle.

**Claude und ChatGPT:** Für Linux gibt es keine offiziellen Desktop-Apps. Kairo
öffnet die Webseiten in einem eigenen Fenster mit eigenem Symbol, ohne Browserleiste.

Roblox (Sober), Spotify, VS Code und Claude Code werden beim **ersten Start**
im Hintergrund aus dem Internet geladen. Nach ein paar Minuten tauchen sie im
App-Menü auf. Klappt es nicht (z. B. kein Internet), versucht Kairo es beim
nächsten Start erneut. Protokoll: `journalctl -u kairo-firstboot`.

## 1. ISO holen

GitHub → **Actions** → **ISO bauen und testen** → neuester grüner Lauf →
unten **Artifacts** → `kairo-iso` herunterladen und entpacken. Darin liegt
`kairo-0.2-JJJJ.MM.TT-x86_64.iso` und `SHA256SUMS`.

## 2. USB-Stick erstellen (unter Windows)

Du brauchst einen USB-Stick mit mindestens **4 GB**. Er wird dabei gelöscht.

1. [Rufus](https://rufus.ie) herunterladen und starten.
2. Laufwerk: deinen USB-Stick wählen.
3. Startart: **AUSWAHL** → die Kairo-ISO.
4. **START**. Fragt Rufus nach dem Modus, **"Im DD-Abbild-Modus schreiben"** wählen.

## 3. BIOS/UEFI einstellen

Beim Einschalten des PCs die Setup-Taste drücken (meist `Entf`, `F2` oder `F12`):

- **Secure Boot: aus.** Kairo startet sonst nicht (wie Arch Linux).
- **Boot-Modus: UEFI** (nicht "Legacy" oder "CSM").
- Vom USB-Stick starten (Boot-Menü, meist `F8`, `F11` oder `F12`).

## 4. Live-System und Installation

1. Im Bootmenü **"Kairo OS Live (x86_64, UEFI)"** wählen (startet nach 15 s von selbst).
2. Der GNOME-Desktop startet, ein Fenster fragt **"Jetzt auf die Festplatte
   installieren?"**. Du kannst auch erst ausprobieren. Der Installer ist
   später im Dock ("Kairo installieren").
3. Für WLAN: oben rechts auf das Netzwerk-Symbol klicken. LAN geht von selbst.
4. Im Installer:
   - Festplatte per Nummer wählen (die Liste zeigt Größe, Modell und vorhandene Partitionen)
   - Benutzername und Passwort festlegen
   - `LÖSCHEN` eintippen
5. Die Installation lädt etwa 3 GB aus dem Internet (10-30 Minuten).
6. Wenn **"Kairo OS ist installiert"** erscheint: Rechner aus, USB-Stick ab, wieder an.

## 5. Erster Start

- Im Anmeldebildschirm mit deinem Benutzer anmelden.
- Ein paar Minuten warten, bis Roblox (Sober), Spotify und VS Code im App-Menü sind.
- Steam starten, anmelden. Für Windows-Spiele: Steam → Einstellungen →
  Kompatibilität → **Steam Play für alle anderen Titel aktivieren**.
- Spiele-Tipps (in Steam: Spiel → Eigenschaften → Startoptionen):
  - `gamemoderun %command%` hebt die CPU-Leistung, solange das Spiel läuft
  - `MANGOHUD=1 %command%` zeigt FPS, CPU- und GPU-Last an

## Wenn etwas nicht klappt

| Problem | Lösung |
| --- | --- |
| Stick startet nicht | Secure Boot aus? Mit Rufus im **DD-Modus** geschrieben? |
| "Der PC ist im alten BIOS-Modus gestartet" | Im Setup CSM/Legacy aus, UEFI an |
| "Kein Internet" im Installer | WLAN oben rechts verbinden, dann Enter |
| Installation bricht ab | Meldung abfotografieren, Protokoll liegt in `/tmp/kairo-install.log` |
| Desktop hängt | `Strg+Alt+F5` öffnet eine Notfall-Konsole (nur im Live-System) |

Was davon schon wirklich getestet ist, steht in [`STATUS.md`](../STATUS.md).
