# Claudus: Wechsel-Kit für Kairo OS

Claudus läuft auf deinem **Windows** und bereitet den Umstieg auf Kairo vor:
prüfen, was mitkommen muss, die ISO holen, den USB-Stick schreiben und dir einen
Spickzettel für den Neustart geben. Danach übernimmt der Kairo-Stick selbst.

## Starten

1. Den Ordner `windows/claudus` auf den PC holen (ganzes Repo als ZIP von
   GitHub → **Code** → **Download ZIP**, entpacken).
2. Doppelklick auf **`Claudus.cmd`**. Windows fragt nach Administratorrechten
   (nötig für den Stick und um BitLocker/Secure Boot zu lesen).
   Kommt "Der Computer wurde durch Windows geschützt": **Weitere Informationen
   → Trotzdem ausführen** (das passiert bei jeder heruntergeladenen,
   unsignierten Datei).

## Menü

| Taste | Was | Ändert etwas? |
| --- | --- | --- |
| 1 | **Vorab-Check**: Start-Modus, Secure Boot, BitLocker, Grafik, WLAN-Chip, welche Platte Windows hat und welche leer ist, Git-Projekte ohne Push, Spielstände, Browser. Bericht als `Claudus-Bericht.txt` auf dem Desktop | Nein |
| 2 | Neueste Kairo-ISO von GitHub laden (setzt abgebrochene Downloads fort) und gegen `SHA256SUMS` prüfen | Nur Downloads-Ordner |
| 3 | **USB-Stick schreiben**, 1:1 wie Rufus im DD-Modus, danach Bit für Bit zurücklesen und vergleichen | **Löscht den gewählten Stick** |
| 4 | Stick nachprüfen (nur lesen) | Nein |
| 5 | **Spickzettel** mit deinen Tasten (Boot-Menü, Setup, Secure Boot, passend zu deinem Mainboard), deinen Platten mit Seriennummer und dem Notfallplan | Datei auf dem Desktop |
| 6 | Plan B: offizielles Rufus laden (Signatur wird geprüft) und starten | Nur Downloads-Ordner |
| A | 1, 3 und 5 hintereinander | wie oben |

## Wie Claudus verhindert, dass die falsche Platte gelöscht wird

- Wählbar sind nur Laufwerke am **USB/SD**-Anschluss, **höchstens 256 GB**,
  groß genug für die ISO. Gesperrt sind immer: die Platte, von der Windows
  startet, die Systempartition, jede Platte mit Windows oder Auslagerungsdatei,
  schreibgeschützte und offline Laufwerke. Gesperrte Laufwerke stehen grau in
  der Liste, mit Grund.
- Du tippst die Nummer und dann **`LÖSCHEN`**. Direkt davor liest Claudus die
  Platte noch einmal und vergleicht Nummer, Seriennummer, ID und Größe. Wurde
  der Stick inzwischen getauscht, bricht Claudus ab, ohne zu schreiben.
- Geschrieben wird nur eine ISO, deren SHA256 zu `SHA256SUMS` aus dem Release
  passt. Nach dem Schreiben liest Claudus den Stick zurück; passt die
  Prüfsumme nicht (defekter oder gefälschter Stick), sagt es das deutlich.

## Was du selbst tun musst (kann kein Programm)

- Den Stick einstecken und die Nummer wählen.
- Fragt Windows nach dem Schreiben "Datenträger formatieren?": **Abbrechen**.
- PC ganz ausschalten, die **Windows-SSD abstecken** (bei M.2 heißt das
  ausbauen; wenn dir das zu fummelig ist, drinlassen und im Kairo-Installer
  streng nach Seriennummer wählen).
- Im BIOS-Setup **Secure Boot aus**, dann über das Boot-Menü vom Stick
  starten. Die Tasten stehen auf dem Spickzettel.
- Danach: [`docs/07-test-auf-deinem-pc.md`](../../docs/07-test-auf-deinem-pc.md).

## Rettung, wenn etwas schiefgeht

Der Kairo-Stick ist selbst das Rettungssystem: Er startet das Live-System,
darin gibt es `sudo kairo-rollback` (Kairo auf einen Snapshot zurücksetzen,
auch verschlüsselt), "Hardware prüfen" und mit `Strg+Alt+F5` eine
Notfall-Konsole. Was in welchem Fall hilft, steht auf dem Spickzettel (Menü 5).
Eigene Dateien lassen sich auf einen per DD geschriebenen Stick nicht dazulegen,
er ist danach schreibgeschützt (ISO-Format), darum liegt der Spickzettel auf dem
Desktop und gehört aufs Handy.

## Getestet

`.github/workflows/claudus.yml` läuft auf echtem Windows (GitHub Actions,
Windows Server 2025) unter **Windows PowerShell 5.1** und PowerShell 7:

- Unit-Tests der Sicherheitsprüfung (USB erlaubt; NVMe, SATA, virtuelle Platte,
  Windows-Platte, >256 GB, zu klein, schreibgeschützt, offline gesperrt;
  getauschter Stick erkannt), SHA256SUMS-Leser, Spickzettel.
- Echter Schreibtest auf eine virtuelle Platte statt USB-Stick: die echte
  Kairo-ISO laden, prüfen, schreiben, zurücklesen (identisch), Windows erkennt
  danach die ISO-Partitionen. Ein manipuliertes Byte wird erkannt.
- Rufus-Download mit gültiger Signatur.

**Nicht** automatisch testbar: ein echter USB-Stick an deinem PC und ob er
danach in deinem UEFI bootet. Wenn Claudus beim Schreiben scheitert: Plan B
(Menü 6, Rufus im DD-Modus) macht dasselbe.
