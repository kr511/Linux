# 05: Checkliste: Ist Kairo 0.1 erfolgreich?

Kairo 0.1 ist **erst dann** fertig, wenn alle Punkte in Teil A–D abgehakt sind,
und zwar durch einen echten Durchlauf bei dir, nicht weil die Dateien
existieren. Trag jeden bestandenen Test mit Datum in [`STATUS.md`](../STATUS.md)
ein.

## A. Umgebung

- [ ] `wsl -d archlinux` startet, `whoami` zeigt deinen Benutzer (nicht root)
- [ ] Repo liegt unter `~/kairo`, **nicht** unter `/mnt/c/...`
- [ ] `scripts/check-env.sh` meldet `0 fehlen`
- [ ] `tests/run-all.sh` endet mit `Alle Prüfungen bestanden.`
      und die `AssembledProfileTest`-Tests laufen (nicht `skipped`)

## B. ISO-Build

- [ ] `scripts/build-iso.sh` läuft ohne `FEHLER:` durch
- [ ] Es gibt genau eine neue Datei `out/kairo-0.1-<datum>-x86_64.iso`
- [ ] SHA-256-Summe steht in `STATUS.md`, zusammen mit `pacman -Q archiso`
- [ ] `diff -ru /usr/share/archiso/configs/releng build/profile` zeigt **nur**
      die Kairo-Änderungen aus `iso/README.md`, nichts Unerwartetes

## C. Boot in QEMU (UEFI), das eigentliche Ziel

- [ ] `scripts/run-qemu.sh` zeigt das Bootmenü **"Kairo OS Live (x86_64, UEFI)"**
- [ ] Das System bootet bis zum Prompt `root@kairo`, ohne Fehler wie
      `Kernel panic` oder `emergency shell`
- [ ] Begrüßung "Willkommen bei Kairo OS 0.1" erscheint
- [ ] `cat /etc/os-release` zeigt `NAME="Kairo OS"`, `ID=kairo`,
      `ID_LIKE=arch` und `IMAGE_VERSION=0.1-<datum>`
- [ ] `hostnamectl` zeigt `Static hostname: kairo` und `Operating System: Kairo OS`
- [ ] `bootctl status` zeigt `Firmware: UEFI`
- [ ] `ping -c 3 archlinux.org` bekommt Antworten
- [ ] `fastfetch` zeigt "Kairo OS"
- [ ] `ls /etc/pacman.d/hooks/` enthält **keine** `kairo-os-release.hook` mehr
- [ ] `poweroff` fährt die VM sauber herunter

## D. Gegenprobe BIOS

- [ ] `scripts/run-qemu.sh --bios` bootet ebenfalls bis `root@kairo`
      (Bootmenü-Titel "Kairo OS Live (x86_64, BIOS)")

## E. Kein Teil von 0.1 (nur damit es klar ist)

Diese Punkte **dürfen** offen sein, 0.1 ist trotzdem erfolgreich:

- `linux-kairo` gebaut oder gebootet (das ist Ziel von 0.2)
- Boot auf deinem echten PC (Phase 2, braucht USB-Stick)
- Desktop, Hyprland (Phase 3)
- Installation auf eine Festplatte

## Wenn etwas nicht klappt

1. Fehlermeldung **komplett** kopieren (nicht abtippen, nicht zusammenfassen).
2. In `STATUS.md` als "fehlgeschlagen" eintragen, mit Befehl und Meldung.
3. Nur **eine** Sache ändern, neu bauen, neu testen.

Ein sauber dokumentierter Fehlschlag ist ein Fortschritt. Ein "ging irgendwie
nicht" ist keiner.
