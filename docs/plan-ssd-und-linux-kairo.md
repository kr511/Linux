# Kairo OS auf deiner separaten SSD, danach linux-kairo

Stand des Plans: 2026-10-24. Dieses Dokument beschreibt geplante Arbeiten,
keine bereits bestandenen Tests. Tatsächliche Ergebnisse stehen in
[`STATUS.md`](../STATUS.md).

## Ziel und feste Entscheidungen

Kairo OS läuft auf deinem Ryzen 5 4500 mit Radeon RX 6500 XT von einer eigenen
SSD. Zuerst läuft es mit dem bereits in der VM getesteten Kernel `linux-zen`,
der über die normalen Arch-Updates Sicherheitsupdates bekommt. `linux-kairo`
kommt danach als zusätzlicher Boot-Eintrag dazu. Standard wird er erst, wenn
er sich ebenfalls automatisch aktualisiert und die Hardwaretests bestanden hat.

- Installation nur auf die separate, leere SSD. Die Windows-SSD ist während
  der Installation abgesteckt.
- Das Live-System behält seinen bisherigen Kernel als Rettungsumgebung.
- Jede Stufe beginnt mit VM-Tests in GitHub Actions. Erst danach folgen
  Tests auf deinem PC und die jeweilige Installation beziehungsweise Umstellung.
- Verschlüsselung bleibt wählbar, ist aber vorausgewählt. Der echte
  Passwortdialog wird vor der Freigabe in QEMU getestet.
- Bekannte rote Tests gehen in keine Freigabe. Frühere grüne Läufe ersetzen
  keine Prüfung des tatsächlich veröffentlichten Quellstands.
- `linux-zen` bleibt in allen Stufen als separat startbarer Ersatz installiert.

## Stufe 1: Kairo mit linux-zen auf die SSD

### 1.1 Freigabe vorbereiten

Die ChatGPT-Reparatur aus dem Branch `kairo-chatgpt-test` erst übernehmen,
wenn der ISO-Test alle Installationsprüfungen besteht. Danach müssen auch
die zusätzlichen Änderungen dieser Stufe gemeinsam getestet werden.

**Installer vor dem ersten Löschbefehl absichern:**

- Laufwerksliste und letzte Zusammenfassung zeigen Modell, Größe und
  Seriennummer. Die Größe für den Identitätsvergleich in Bytes erfassen.
- Laufwerke mit eingehängten Partitionen, aktiven zugehörigen
  Geräteabbildungen oder aktivem Swap ablehnen. Den Live-Stick weiterhin
  ausschließen; die Prüfung gilt für GUI und Terminal.
- Die Identität bei der Auswahl erfassen und unmittelbar vor dem
  Partitionieren erneut vergleichen: Gerät, Seriennummer und Größe.
  Bei Änderung, abgezogenem Gerät oder nicht eindeutig feststellbarer
  Identität abbrechen. Virtuelle Testlaufwerke erhalten eine feste Seriennummer.
- Eine fehlgeschlagene Prüfung darf nicht durch vorheriges automatisches
  Aushängen oder Abschalten von Swap umgangen werden.
- Ohne gültige ausdrückliche Löschbestätigung keine Installation beginnen.

**Sicherheit im installierten System:**

- Eine persistente Firewall für IPv4 und IPv6 aktivieren: unaufgefordert
  eingehend blockieren, ausgehend erlauben. Loopback, Antworten auf eigene
  Verbindungen sowie erforderlichen DHCP- und ICMP/ICMPv6-Verkehr zulassen.
- Normale Steam-Verbindungen, Discord, DNS und Downloads prüfen. Für
  selbst gehostete Spiele oder Dienste sind später gezielte Freigaben nötig.
- Verschlüsselung in GUI und Terminal als Standard anbieten. Abbrechen
  bleibt eine eigene Aktion und darf nicht als Zustimmung zur
  unverschlüsselten Installation behandelt werden.

**Tests ergänzen:**

- Verschlüsselte Installation ohne den bisherigen automatischen
  Testschlüssel im Initramfs starten. QMP sendet echte Tastendrücke für
  ein festes, ausschließlich im Test verwendetes Passwort mit deutscher
  Tastaturbelegung und Sonderzeichen. Den sichtbaren Dialog fotografieren
  und anschließend den erfolgreichen Systemstart prüfen.
- Ein falsches Passwort darf nicht entsperren. Die richtige Eingabe muss
  danach funktionieren. Produktionspasswörter gehören in keine Testprotokolle.
- Firewall nach Neustart prüfen: Ein von außen gestarteter Testclient
  erreicht einen absichtlich gestarteten Testdienst nicht. Ohne Firewall
  muss derselbe Prüfaufbau den Dienst erreichen, damit der Test aussagekräftig
  ist. IPv4 und IPv6 sowie ausgehende Verbindungen prüfen.
- Für Abbruch, fehlendes beziehungsweise ausgetauschtes Laufwerk und
  belegte Laufwerke mit nachgebauten Löschbefehlen nachweisen, dass weder
  `wipefs` noch `sgdisk` noch Formatierungsbefehle ausgeführt werden.

**Freigabe v1.0.1:** Erst veröffentlichen, wenn statische Tests, ISO-Build,
UEFI- und BIOS-Live-Test sowie beide Installationstests mit und ohne
Verschlüsselung grün sind. Screenshots und Testprotokolle aufbewahren.
Die Größenprüfung für Release-Dateien bleibt bestehen.

### 1.2 Auf deinem PC

1. Wichtige Daten extern sichern und prüfen, ob sie lesbar sind.
   Die Windows-SSD abstecken.
2. ISO-Prüfsumme vergleichen und die ISO im DD-Modus auf den USB-Stick
   schreiben. Der Stick wird gelöscht. UEFI verwenden und Secure Boot
   für diese Version ausschalten.
3. Live starten und prüfen: Grafik, LAN/WLAN, Ton, USB und Erkennung der
   Ziel-SSD. Noch nichts installieren, wenn wesentliche Hardware nicht läuft.
4. Modell und Seriennummer der leeren SSD bestätigen, dann installieren.
   Verschlüsselung ist empfohlen und vorausgewählt.
5. USB-Stick nach dem Herunterfahren abziehen und von der SSD starten.
   Bei Verschlüsselung das Passwort am echten Dialog eingeben. Anschließend
   auch den Eintrag „Kairo OS (Notfall)“ einmal starten.
6. Grafikbeschleunigung, Steam/Vulkan mit einem Spiel, SSD-Zugriffe,
   Netzwerk, Ton, Neustart sowie Standby und Aufwachen prüfen. Ein normales
   Systemupdate installieren und einen vorher angelegten Snapshot zurückrollen;
   nach jedem Schritt den erfolgreichen Neustart prüfen.
7. Die Windows-SSD erst danach wieder anschließen und die gewünschte
   UEFI-Startreihenfolge einstellen.
8. Ergebnis mit Version, Datum, Hardware und noch offenen Problemen in
   `STATUS.md` eintragen.

Der Ryzen 5 4500 hat keine integrierte Grafik; der Monitor bleibt an der
RX 6500 XT angeschlossen. Bei schwarzem Bildschirm den Notfall-Eintrag
versuchen. Dieser verwendet ein vollständigeres Initramfs, aber denselben
Kernel und garantiert daher keine Behebung eines Grafiktreiberfehlers.
Als weitere Rettungsumgebung bleibt der Live-Stick verfügbar.

## Stufe 2: linux-kairo als zusätzlicher Boot-Eintrag

### 2.1 Paket bauen

Einen eigenen Kernel-Workflow getrennt vom ISO-Workflow ergänzen:

- Sauberer Arch-Container; den Build als normalen Benutzer ausführen.
- Vorab mehr als 20 GiB freien Platz schaffen und kontrollieren.
  Ein Zeitlimit von sechs Stunden vorsehen; der erste vollständige Bau
  kann mit vier Kernen mehrere Stunden dauern.
- Für die Vorbereitung die dann aktuelle stabile Version von
  [kernel.org](https://www.kernel.org/) auswählen und mit Quellen und
  Prüfsummen fest im Repository hinterlegen. Der eigentliche Build nutzt
  genau diese geprüfte Version. Keinen Release-Candidate verwenden und
  keine bald auslaufende Serie ungeprüft weiterführen.
- Die vollständige offizielle Arch-Konfiguration importieren und Herkunft
  sowie Version speichern. `kairo.config` darüberlegen und nach
  `olddefconfig` mit `verify-config.py` prüfen. Bei einem Serienwechsel
  veränderte Optionen und Abhängigkeiten erneut prüfen.
- Keine zusätzlichen Patches und keine Übertaktung einführen.
- Die Quellsignatur gegen die passenden `validpgpkeys` prüfen und echte
  `sha256sums` hinterlegen. Nur die `.sign`-Datei darf `SKIP` behalten.
- `linux-kairo` und `linux-kairo-headers` bauen. Beide Pakete, Version,
  Quellstand, fertige `.config`, Prüfsummen und Build-Protokoll als
  zusammengehörigen Release-Artefaktsatz bereitstellen.

**Abnahme:** Beide Pakete lassen sich in einer Test-VM installieren.
Kernel, Module und Header haben dieselbe Kernelversion. Ein Smoke-Test
ohne Root-Dateisystem zählt nicht als vollständiger Systemstart.

### 2.2 Installer, bestehendes System und Bootmenü

- Das Paket nicht in die ISO legen. Release-Dateien müssen unter der
  bestehenden Grenze von 2 GiB bleiben; die tatsächliche ISO-Größe bei
  jedem Build prüfen.
- Im Installer `linux-kairo` als zusätzliche, zunächst nicht standardmäßig
  aktivierte Auswahl anbieten. Stufe 1 bleibt ohne eigenes Kernelpaket nutzbar.
- Ist diese Auswahl aktiv, beide Pakete vor dem Löschen von einer exakt
  festgelegten Release-URL herunterladen. Gegen im geprüften Installerstand
  hinterlegte Prüfsummen prüfen; keine ungeprüfte `latest`-URL verwenden.
  Bei fehlenden oder veränderten Paketen vor dem ersten Löschbefehl abbrechen.
- Das Grundsystem mit `linux-zen` installieren, danach die geprüften lokalen
  Pakete im Zielsystem installieren. Keine Kernelkompilierung auf dem Ziel-PC.
- Für bereits installierte Kairo-Systeme denselben Download- und Prüfablauf
  als dokumentierte Nachinstallation bereitstellen. Dafür ist weder eine
  Neuinstallation noch eine Formatierung erforderlich; vorher Snapshot anlegen.
- mkinitcpio für beide Kernel einrichten und jeweils normales sowie
  Ersatz-Initramfs erzeugen. AMD-Firmware und Microcode müssen installiert sein.
- Das Bootmenü fünf Sekunden anzeigen und vier eindeutig benannte Einträge
  bereitstellen: `linux-zen` als Standard, `linux-zen Ersatz`, `linux-kairo`
  und `linux-kairo Ersatz`.
- `kairo-update-root` erkennt Änderungen an beiden Kernelpaketen und erzeugt
  den Neustarthinweis. Kairo Update weist darauf hin, dass `linux-kairo`
  bis Stufe 3 über geprüfte Kairo-Releases aktualisiert wird.

### 2.3 Tests in QEMU

- Vollständigen Start mit `linux-kairo` und `linux-zen` prüfen:
  `uname -r`, Root-Dateisystem, Module, Netzwerk und GNOME. Beide
  Ersatz-Initramfs ebenfalls starten; mit und ohne Verschlüsselung testen.
- Nach einem tatsächlichen Kernelpaket-Update zurückrollen. Dabei prüfen,
  dass `kairo-rollback` die Kerneldateien und Initramfs auf `/boot` passend
  zu den wiederhergestellten Modulen erzeugt und beide Kernel danach booten.
- Den echten Verschlüsselungsdialog auch mit `linux-kairo` prüfen.
- Fehlende oder manipulierte Kernelpakete müssen bei aktivierter
  Kernel-Auswahl vor dem ersten Löschbefehl zum Abbruch führen.
- Die Nachinstallation auf einem vorhandenen Kairo-System testen und
  nachweisen, dass `linux-zen` Standard bleibt.

### 2.4 Auf deinem PC

Nach grünen VM-Tests Kairo aktualisieren und das geprüfte Kernelpaket auf
dem bestehenden System nachinstallieren. `linux-kairo` im Bootmenü wählen
und dieselben Hardware- und Wiederherstellungsprüfungen wie in Stufe 1
durchführen. `linux-zen` bleibt Standard. Ergebnisse in `STATUS.md` festhalten.

## Stufe 3: linux-kairo zum Standard machen

Die Umstellung erfolgt erst, wenn alle folgenden Bedingungen erfüllt sind:

- Ein täglicher Workflow prüft kernel.org auf neue stabile Versionen,
  aktualisiert die festgelegten Quellen und Konfiguration, baut die Pakete
  und führt die vollständigen VM-Tests aus Stufe 2 aus. Fehler lassen die
  bisherige veröffentlichte Version unverändert und werden als fehlgeschlagene
  Workflow-Läufe sichtbar.
- Nur erfolgreich getestete Pakete werden in ein eigenes signiertes
  pacman-Repository übernommen. Paket- und Datenbanksignaturen sind
  verpflichtend; der öffentliche Schlüssel wird mit festgelegtem Fingerprint
  in Kairo eingebunden. Updates kommen dann über Kairo Update.
- Die Verwaltung des privaten Signierschlüssels ist vor der Einrichtung
  ausdrücklich entschieden: entweder ein geschütztes GitHub-Environment
  mit Secret für den Veröffentlichungsjob oder manuelles Signieren.
  Manuelles Signieren allein erfüllt die Anforderung unbeaufsichtigter
  automatischer Veröffentlichung noch nicht; bis zu deren Lösung bleibt
  `linux-zen` Standard.
- Der Signierjob verarbeitet nur freigegebene Build-Artefakte und hat keinen
  Zugriff aus ungeprüften Pull Requests. Private Schlüssel gehören weder
  in Git noch in Logs oder herunterladbare Artefakte.
- Die Test-VM kann über das Repository ein neues Kernelpaket installieren,
  davon starten und danach erfolgreich zurückrollen.
- `linux-kairo` lief mindestens vier Wochen als optionaler Eintrag auf
  deinem PC ohne ungeklärte Start-, Grafik-, Speicher- oder Standby-Probleme.

Danach den Standard im Bootmenü umstellen. `linux-zen` bleibt als Ersatz
installiert und bekommt weiterhin seine normalen Arch-Updates.

## Fertig ist es, wenn

- **Stufe 1:** Kairo mit `linux-zen` startet von deiner SSD, die Hardwaretests
  und das Zurückrollen funktionieren, und die Ergebnisse stehen in `STATUS.md`.
- **Stufe 2:** Beide Kernel starten auf deiner SSD; die Wiederherstellung
  funktioniert für beide. `linux-zen` bleibt Standard.
- **Stufe 3:** `linux-kairo` ist Standard, bekommt automatisch geprüfte und
  signierte Updates, und `linux-zen` bleibt unabhängig startbar.

VM-Tests, lokale Codeänderungen und erzeugte Build-Dateien allein bestätigen
keine erfolgreiche Installation auf deinem PC. Hardwaretests werden erst
nach der tatsächlichen Durchführung als bestanden dokumentiert.
