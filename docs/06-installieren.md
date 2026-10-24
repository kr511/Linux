# 06: Kairo auf deinem PC installieren

> **Achtung:** Der Installer löscht die **ganze** Festplatte, die du
> auswählst, inklusive Windows und aller Dateien darauf. Sichere vorher alles,
> was du behalten willst (Fotos, Spielstände, Dokumente).

## Was du bekommst

| Bereich | Was installiert wird |
| --- | --- |
| Desktop | GNOME im Kairo-Design (dunkel, grüner Akzent, eigenes Logo und Hintergrund), deutsche Tastatur, Fensterknöpfe wie bei Windows |
| Kernel | `linux-zen` (für Desktop und Spiele optimiert), AMD-Microcode |
| Grafik | AMD: Mesa, Vulkan (`vulkan-radeon`, auch 32 Bit für Steam), FreeSync an |
| Spiele | Steam (mit Proton), Roblox über **Sober**, GameMode, MangoHud, Gamescope |
| Apps | Firefox, Discord, Spotify, VS Code, native ChatGPT-Desktop-App, Claude als Web-App, Claude Code und Codex im Terminal |
| Kairo-Apps | **Kairo Update** (Updates mit einem Klick, meldet sich täglich), **Kairo Wiederherstellen** (zurück auf einen früheren Stand) |
| System | Btrfs mit automatischen Snapshots vor jedem Update, optional verschlüsselt, Boot-Animation, zram-Swap, Bluetooth, PipeWire (Ton), WLAN über NetworkManager |

**Roblox:** Der normale Roblox-Client läuft auf Linux nicht, auch nicht mit
Wine, weil der Anti-Cheat das blockiert. Sober ist die Android-Version von
Roblox für Linux. Die meisten Spiele laufen, aber nicht alle.

**ChatGPT:** Kairo installiert beim ersten Start die offizielle native Linux-App
aus OpenAIs signiertem pacman-Repository. Der alte Web-App-Starter entfällt.
Danach im App-Menü oder Dock **ChatGPT** öffnen und mit deinem Konto anmelden.
Updates kommen über **Kairo Update** / `pacman -Syu`.
[Offizielle Anleitung](https://learn.chatgpt.com/docs/linux/linux-app).

**Claude:** Der Kairo-Starter öffnet weiterhin die Webseite in einem eigenen
Fenster. Claude Code im Terminal ist ein separates Programm. Claude Desktop
für Linux gibt es als Beta für Ubuntu/Debian; es ist hier nicht integriert.

ChatGPT Desktop, Roblox (Sober), Spotify, VS Code und Claude Code werden beim **ersten Start**
im Hintergrund aus dem Internet geladen. Nach ein paar Minuten tauchen sie im
App-Menü auf. Klappt es nicht (z. B. kein Internet), versucht Kairo es beim
nächsten Start erneut. Protokoll: `journalctl -u kairo-firstboot`.

Der ChatGPT-Installer wird vor der Ausführung mit einer fest hinterlegten
SHA-256-Prüfsumme geprüft. Ändert OpenAI das Skript, wird die Installation
abgebrochen, bis die neue Version geprüft und die Prüfsumme aktualisiert ist.
Eine Wiederholung ist mit `sudo kairo-chatgpt-install` möglich. Die offizielle
Installation führt ein vollständiges Systemupdate durch; bei einem neuen
Kernel danach neu starten. Die Anwendung wird nicht im Live-System installiert.

## 1. ISO holen

Auf der Download-Seite **https://github.com/kr511/Linux/releases/latest**
unter **Assets** die `kairo-1.0-JJJJ.MM.TT-x86_64.iso` und `SHA256SUMS`
herunterladen. Jedes Release hat vorher alle automatischen Tests bestanden.

Prüfsumme vergleichen (PowerShell): `Get-FileHash .\kairo-*.iso` muss den
Wert aus `SHA256SUMS` zeigen.

(Neuere Testversionen gibt es auch unter GitHub → **Actions** → **ISO bauen
und testen** → grüner Lauf → **Artifacts** → `kairo-iso`.)

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
2. Der GNOME-Desktop startet mit einem Begrüßungsfenster. Klicke zuerst auf
   **Hardware prüfen**: Es zeigt, ob Grafik (AMD-Treiber), WLAN, Ton,
   Internet und Festplatte passen. Bei ❌ erst das Problem lösen.
   Beides ("Hardware prüfen", "Kairo installieren") ist auch im Dock links.
3. Für WLAN: oben rechts auf das Netzwerk-Symbol klicken. LAN geht von selbst.
4. Der Installer führt dich durch ein paar Fenster:
   - Festplatte auswählen (die Liste zeigt Größe und Modell, der USB-Stick fehlt absichtlich)
   - Benutzername und Passwort festlegen
   - **Verschlüsseln oder nicht.** Mit Verschlüsselung fragt Kairo bei jedem
     Start nach einem eigenen Passwort (mindestens 8 Zeichen, deutsche
     Tastatur). Ohne dieses Passwort kommt niemand an deine Daten, auch du
     nicht: **Vergisst du es, sind die Daten weg.**
   - In der Zusammenfassung `LÖSCHEN` eintippen
5. Die Installation lädt etwa 3 GB aus dem Internet (10-30 Minuten), ein
   Balken zeigt den Fortschritt.
6. Wenn **"Kairo ist installiert"** erscheint: **Jetzt neu starten**, beim
   Herunterfahren den USB-Stick abziehen.

Lieber im Terminal? `sudo kairo-install` stellt dieselben Fragen ohne Fenster.

## 5. Erster Start

- Im Anmeldebildschirm mit deinem Benutzer anmelden.
- Ein paar Minuten warten, bis ChatGPT Desktop, Roblox (Sober), Spotify und VS Code im App-Menü sind.
- KI im Terminal: Terminal öffnen, `claude` (Anthropic) oder `codex` (OpenAI)
  eintippen. Beim ersten Aufruf meldest du dich mit deinem Konto an.
- Steam starten, anmelden. Für Windows-Spiele: Steam → Einstellungen →
  Kompatibilität → **Steam Play für alle anderen Titel aktivieren**.
- Spiele-Tipps (in Steam: Spiel → Eigenschaften → Startoptionen):
  - `gamemoderun %command%` hebt die CPU-Leistung, solange das Spiel läuft
  - `MANGOHUD=1 %command%` zeigt FPS, CPU- und GPU-Last an

## 6. Updates und Zurückrollen

- **Kairo Update** (im App-Menü) zeigt, wie viele Updates da sind, und
  installiert System und Apps mit einem Klick. Einmal am Tag meldet sich
  Kairo von selbst, wenn es Updates gibt.
- Vor **jedem** Update legt Kairo automatisch einen Snapshot an (die letzten
  10 werden behalten). Läuft nach einem Update etwas nicht mehr:
  **Kairo Wiederherstellen** öffnen, den Eintrag **"vor Update"** wählen,
  neu starten. Deine Dateien in `/home` (Dokumente, Bilder, Spielstände)
  bleiben dabei unverändert, nur das System geht zurück.
- Startet Kairo gar nicht mehr: vom Kairo-USB-Stick starten, Terminal öffnen,
  `sudo kairo-rollback` eintippen und einen Snapshot wählen. Bei
  Verschlüsselung fragt es vorher nach dem Passwort.
- Im Terminal geht beides auch direkt: `sudo kairo-rollback` zeigt die
  Snapshots, `sudo pacman -Syu` aktualisiert (Snapshot kommt automatisch).

## Wenn etwas nicht klappt

| Problem | Lösung |
| --- | --- |
| Stick startet nicht | Secure Boot aus? Mit Rufus im **DD-Modus** geschrieben? |
| "Der PC ist im alten BIOS-Modus gestartet" | Im Setup CSM/Legacy aus, UEFI an |
| "Kein Internet" im Installer | WLAN oben rechts verbinden, dann **Nochmal prüfen** |
| Verschlüsselungs-Passwort vergessen | Daten sind nicht mehr lesbar, nur Neuinstallation hilft |
| Nach einem Update kaputt | **Kairo Wiederherstellen**, Eintrag "vor Update", siehe Abschnitt 6 |
| Installation bricht ab | Meldung abfotografieren, Protokoll liegt in `/tmp/kairo-install.log` |
| Desktop hängt (Live-System) | `Strg+Alt+F5` öffnet eine Notfall-Konsole |
| Desktop hängt (installiert) | `Strg+Alt+F3`, anmelden, `sudo kairo-rollback` |

Was davon schon wirklich getestet ist, steht in [`STATUS.md`](../STATUS.md).
