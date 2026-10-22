# 02: Kairo-ISO bauen

Voraussetzung: [01: Entwicklungsumgebung](01-entwicklungsumgebung.md) ist
erledigt und `scripts/check-env.sh` zeigt bei Arch, archiso und Speicher `[OK]`.

## Kurzfassung

```bash
cd ~/kairo
sudo pacman -Syu
scripts/build-iso.sh
```

Ergebnis: `out/kairo-0.1-JJJJ.MM.TT-x86_64.iso` (grob 1,2 bis 1,5 GB, wie die offizielle Arch-ISO).

## Ohne eigene Arch-Umgebung: in der Cloud bauen

Kein Platz, kein Arch, nur ein Chromebook? Der Workflow
[`iso.yml`](../.github/workflows/iso.yml) baut die ISO auf GitHub und bootet
sie dort in QEMU (UEFI und BIOS), inklusive der Prüfungen aus Teil C und D der
[Checkliste](05-checkliste-kairo-0.1.md).

1. Auf GitHub: **Actions** → **ISO bauen und testen** → **Run workflow**.
2. Nach ca. 20-30 Minuten im Lauf auf **Summary**: Prüftabellen und Prüfsumme.
3. Unten bei **Artifacts**: `kairo-iso` (die ISO) und `boot-test-uefi` /
   `boot-test-bios` (Screenshots vom Bootmenü, Login und fastfetch).

Der Workflow startet auch automatisch bei Pull Requests, die `iso/` oder die
Build-Skripte ändern. Lokal geht derselbe Boot-Test ohne Fenster mit
`scripts/boot-test.py out/kairo-*.iso`.

## Was dabei passiert, Schritt für Schritt

`scripts/build-iso.sh` macht vier Dinge. Du kannst jeden Schritt auch einzeln
ausführen, um zu verstehen, was passiert.

### 1. Vorabprüfungen

Das Skript bricht mit einer verständlichen Meldung ab, wenn:

- du nicht auf Arch bist,
- du es mit `sudo` startest (archiso ≥ 89 baut als normaler Benutzer mit
  `unshare`, also ohne root-Rechte),
- `mkarchiso` fehlt,
- das Repo unter `/mnt/...` (Windows-Laufwerk) liegt,
- weniger als 15 GiB frei sind,
- ein Paket aus `iso/packages.kairo.x86_64` nicht in den Arch-Repos existiert.

Weicht deine archiso-Version von 91 ab, gibt es eine **Warnung** (kein
Abbruch). Dann im
[archiso-Changelog](https://gitlab.archlinux.org/archlinux/archiso/-/blob/master/CHANGELOG.rst)
nachsehen, ob sich am releng-Profil etwas Grundlegendes geändert hat.

### 2. Profil zusammenbauen

```bash
scripts/assemble-iso-profile.sh
```

Kopiert `/usr/share/archiso/configs/releng` (das offizielle Profil, aus dem auch
die Arch-ISO entsteht) nach `build/profile/` und legt die Kairo-Änderungen aus
`iso/` darüber. Details in [`iso/README.md`](../iso/README.md).

Schau dir das Ergebnis ruhig an, bevor du baust:

```bash
diff -ru /usr/share/archiso/configs/releng build/profile
```
`diff -ru` vergleicht zwei Ordner rekursiv (`-r`) im lesbaren Format (`-u`).
Du siehst exakt, was Kairo anders macht als Arch.

### 3. ISO bauen

```bash
mkarchiso -v -w build/work -o out build/profile
```
| Teil | Bedeutung |
| --- | --- |
| `-v` | ausführliche Ausgabe |
| `-w build/work` | Arbeitsordner: hier installiert pacman alle Pakete in ein Mini-System |
| `-o out` | hier landet die fertige ISO |
| `build/profile` | das Profil aus Schritt 2 |

Grob läuft dabei ab: Pakete in `build/work` installieren → Kairo-Dateien
hineinkopieren → Initramfs erzeugen → alles in ein squashfs packen →
Bootloader für BIOS und UEFI einrichten → ISO-Datei schreiben.

Dauer: 10 bis 30 Minuten, je nach Internetverbindung (es werden ~1 GB Pakete
geladen).

### 4. Prüfsumme

Am Ende gibt das Skript die SHA-256-Prüfsumme der ISO aus. Trag sie zusammen
mit Datum und archiso-Version in [`STATUS.md`](../STATUS.md) ein. Damit ist
belegt, welche Datei du getestet hast.

## Typische Fehler

| Meldung | Ursache / Lösung |
| --- | --- |
| `Nicht in den Repos gefunden: ...` | Tippfehler in `packages.kairo.x86_64` oder Paketlisten veraltet: `sudo pacman -Syu` |
| `error: failed to retrieve some files` | Mirror-Problem. Nochmal versuchen; ggf. `/etc/pacman.d/mirrorlist` prüfen |
| `unshare: ... Operation not permitted` | User-Namespaces nicht verfügbar. Notlösung: `sudo mkarchiso -v -w build/work -o out build/profile` (dann Ordner mit `sudo` löschen) |
| `No space left on device` | `build/work` löschen, mehr Platz schaffen |

## Aufräumen

```bash
rm -rf build/ out/
```
Löscht nur die Build-Ergebnisse in diesem Repo (beide Ordner stehen in
`.gitignore`). Achte darauf, dass du dabei in `~/kairo` bist (`pwd`).

Weiter mit [03: ISO in QEMU testen](03-iso-in-qemu-testen.md).
