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

**ChatGPT:** Kairo installiert die offizielle native Linux-App schon während
der Installation, aus OpenAIs signiertem pacman-Repository. Nach dem ersten
Anmelden im App-Menü oder Dock **ChatGPT** öffnen und mit deinem Konto anmelden.
Updates kommen über **Kairo Update** / `pacman -Syu`. Links aus ChatGPT öffnen
sich in Firefox (Standardbrowser, änderbar unter Einstellungen → Apps).
[Offizielle Anleitung](https://learn.chatgpt.com/docs/linux/linux-app).

**Claude:** Der Kairo-Starter öffnet weiterhin die Webseite in einem eigenen
Fenster. Claude Code im Terminal ist ein separates Programm. Claude Desktop
für Linux gibt es als Beta für Ubuntu/Debian; es ist hier nicht integriert.

Roblox (Sober), Spotify, VS Code und Claude Code werden beim **ersten Start**
im Hintergrund aus dem Internet geladen. Nach ein paar Minuten tauchen sie im
App-Menü auf. Klappt es nicht (z. B. kein Internet), versucht Kairo es beim
nächsten Start erneut. Protokoll: `journalctl -u kairo-firstboot`.

Ging ChatGPT während der Installation nicht (z. B. Internet weg), holt der
erste Start es nach. Bis dahin öffnet **ChatGPT** im Dock die Webseite in einem
eigenen Fenster; sobald die Desktop-App da ist, verschwindet dieser Ersatz.
Von Hand: `sudo kairo-chatgpt-install`.

Wie Kairo ChatGPT einrichtet: OpenAIs Signaturschlüssel liegt in Kairo
(`/usr/local/share/kairo/openai-chatgpt.gpg`, Fingerprint
`3BFA0E4AE8B8CC16A2D9BA684A3B4A566C4660E4`). Kairo prüft ihn, trägt das
Repository genau so ein wie OpenAIs Installer, und pacman prüft Paketliste und
Paket gegen diesen Schlüssel. OpenAIs `install-arch.sh` selbst führt Kairo nicht
aus, weil es sich mit jedem Release ändert. Die Anwendung wird nicht ins
Live-System oder die ISO gepackt, sondern direkt von OpenAI geladen.

## 0. Vorher erledigen (die gewählte Platte wird unwiederbringlich gelöscht)

Ersetzt du die Platte, auf der Windows liegt, gibt es danach **kein Zurück**
ohne Neuinstallation von Windows. Hake das vorher ab:

- [ ] Alles Wichtige von dieser Platte auf ein **anderes** Laufwerk kopiert
      (Dokumente, Bilder, Spielstände, Browser-Lesezeichen, Passwort-Datenbank).
      Prüfe, dass die Kopie sich öffnen lässt.
- [ ] Lizenzen und Zugänge notiert: Windows-Aktivierung hängt meist am
      Microsoft-Konto, Office/Adobe/Spiele-Launcher brauchen eine Neuanmeldung.
- [ ] Bei **BitLocker** auf der alten Platte: Wiederherstellungsschlüssel aus
      dem Microsoft-Konto gesichert, falls du Dateien später doch brauchst.
- [ ] Du weißt, **welche** Platte es ist (Modell und Seriennummer stehen in
      Windows unter Einstellungen → System → Speicher → Datenträger, oder im
      Installer). Hängen mehrere Platten im PC, ziehe die anderen zum
      Installieren ab oder prüfe Modell und Seriennummer in der Liste.
- [ ] Netzteil/Laptop am Strom, die Installation darf nicht unterbrochen werden.

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
   - Festplatte auswählen (die Liste zeigt Größe, Modell und Seriennummer;
     belegte oder nicht eindeutig identifizierbare Laufwerke fehlen ebenso
     wie der Live-Stick). Nur die separate leere SSD anschließen.
   - Benutzername und Passwort festlegen
   - **Verschlüsseln oder nicht.** Verschlüsselung ist vorausgewählt.
     Abbrechen beendet die Installation. Mit Verschlüsselung fragt Kairo bei jedem
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
- Ein paar Minuten warten, bis Roblox (Sober), Spotify und VS Code im App-Menü sind.
- KI im Terminal: Terminal öffnen, `claude` (Anthropic) oder `codex` (OpenAI)
  eintippen. Beim ersten Aufruf meldest du dich mit deinem Konto an.
- Steam starten, anmelden. Für Windows-Spiele: Steam → Einstellungen →
  Kompatibilität → **Steam Play für alle anderen Titel aktivieren**.
- Spiele-Tipps (in Steam: Spiel → Eigenschaften → Startoptionen):
  - `gamemoderun %command%` hebt die CPU-Leistung, solange das Spiel läuft
  - `MANGOHUD=1 %command%` zeigt FPS, CPU- und GPU-Last an

## 6. Updates und Zurückrollen

Die installierte Firewall blockiert unaufgeforderte eingehende Verbindungen
für IPv4 und IPv6. Surfen, Downloads, Steam als Client und Discord können
ausgehende Verbindungen herstellen. Für eigene Spielserver oder andere
gehostete Dienste sind gezielte Regeln in `/etc/nftables.conf` erforderlich.
Die Firewall nicht pauschal abschalten.

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

## 7. Sicherung (wichtig, auch mit Snapshots)

Snapshots liegen auf **derselben** SSD wie dein System. Sie helfen gegen ein
missglücktes Update, aber nicht gegen eine defekte SSD, Diebstahl oder
versehentliches Löschen. Außerdem sind `/home` (deine Dateien) und die
Snapshots selbst nicht voneinander getrennt gesichert.

Halte darum wichtige Dateien **zusätzlich auf einem zweiten Laufwerk oder in
der Cloud**. Ein einfacher Anfang: externe Festplatte einstecken und den
Ordner `/home/<name>` mit der App "Dateien" hinüberkopieren.

## 8. Wenn die Installation scheitert

- Die Meldung steht im Fenster, das ausführliche Protokoll in
  `/tmp/kairo-install.log`. Das Live-System liegt im Arbeitsspeicher und der
  Stick ist schreibgeschützt: Das Protokoll geht beim Neustart verloren. Öffne
  es vorher (`cat /tmp/kairo-install.log`) und fotografiere die letzten Zeilen
  oder kopiere es auf einen zweiten, eigenen USB-Stick.
- Nach einem Fehler hängt der Installer die Platte selbst wieder aus. Meist
  hilft es dann, ihn einfach nochmal zu starten: Er beginnt die gewählte Platte
  von vorn. (Wurde das Fenster gewaltsam geschlossen oder der PC ausgeschaltet,
  zuerst neu starten.)
- Erscheint **"Keine Festplatte gefunden"**, nennt der Installer jetzt den
  Grund je Platte. Häufigster Fall: Die Platte wurde im Dateimanager angeklickt
  und ist dadurch eingehängt. Dort auswerfen und den Installer neu starten.
- Bricht es mit einem Netzwerkfehler ab, WLAN prüfen und neu starten.
