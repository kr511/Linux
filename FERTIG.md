# Wann ist Kairo OS fertig?

Festgelegt am 2026-11-25. "Fertig" heißt hier: **Kairo 1.0.1 ist sauber
veröffentlicht, alles, was in einer VM beweisbar ist, ist in GitHub Actions
bewiesen, und für den Rest gibt es eine klare Anleitung.** Neue Funktionen
gehören in eine spätere Version, nicht in diese Liste.

Beweise stehen in [`STATUS.md`](STATUS.md) (Lauf-Nummern, Datum, Ergebnis).

## Checkliste

- [ ] Alle offenen Arbeitsstände in `main`: SSD-Schutz, Firewall, echter
      Entsperrtest (PR #12-#15), native ChatGPT-App (PR #11), Firewall-Fix und
      GUI-Test (PR #16). Veraltete PRs geschlossen.
- [ ] ISO-Workflow auf dem Release-Commit komplett grün:
      statische Tests, ISO-Build, Live UEFI, Live BIOS, Installation,
      Installation mit Verschlüsselung (echter Passwortdialog),
      **grafischer Installer über die echten Fenster**.
- [ ] Release `v1.0.1` auf GitHub mit ISO, `SHA256SUMS` und Release-Notizen,
      ISO unter 2 GiB.
- [ ] `STATUS.md`, `README.md` und die Anleitungen beschreiben 1.0.1.
- [ ] Testanleitung für echte Hardware:
      [`docs/07-test-auf-deinem-pc.md`](docs/07-test-auf-deinem-pc.md).
- [ ] Entscheidung zu `linux-kairo` begründet dokumentiert (unten).

## Was nur Eli prüfen kann

Kein automatischer Test ersetzt das. Anleitung: `docs/07-test-auf-deinem-pc.md`.

- Installation auf der echten SSD (Ryzen 5 4500, RX 6500 XT)
- AMD-Grafik mit Vulkan in einem echten Spiel, FreeSync
- WLAN/LAN, Ton, Mikrofon, Standby und Aufwachen
- Passwortdialog mit deiner echten Tastatur

## Entscheidung: eigener Kernel `linux-kairo`

**Zurückgestellt, nicht Teil von 1.0.1.** `linux-zen` bleibt Standard.

Begründung:

1. **Sicherheit.** Ein eigener Kernel ist nur so sicher wie seine Updates.
   `linux-zen` bekommt Sicherheitsupdates automatisch über Arch. Für
   `linux-kairo` bräuchte es vorher einen täglichen Bau mit vollen VM-Tests
   und ein signiertes eigenes Paket-Repository samt Schlüsselverwaltung
   (Stufe 3 in [`docs/plan-ssd-und-linux-kairo.md`](docs/plan-ssd-und-linux-kairo.md)).
   Ohne das wäre dein PC nach ein paar Wochen auf einem Kernel mit bekannten
   Lücken.
2. **Kein Gewinn.** `kairo.config` legt über die Arch-Konfiguration nur
   Pflichtoptionen (AMD-CPU/GPU, Dateisysteme, Virtio, EFI), die Arch
   ohnehin setzt; Patches gibt es keine. `linux-kairo` wäre damit im Kern der
   normale Arch-Kernel und weniger auf Desktop und Spiele abgestimmt als
   `linux-zen`, den Kairo schon nutzt. Ein eigener Kernel lohnt sich erst,
   wenn es etwas gibt, das `linux-zen` nicht kann.
3. **Signierschlüssel.** Ein signiertes Repository braucht einen privaten
   Schlüssel als GitHub-Secret. Den kann nur Eli anlegen; das soll keine
   automatische Sitzung nebenbei erledigen.

Was bleibt: PKGBUILD, `kairo.config` und die Prüfskripte sind fertig
vorbereitet und getestet (siehe `STATUS.md`). Wer weitermachen will, beginnt
mit Stufe 2.1 des Plans (Paket in einem eigenen Workflow bauen) und baut es
**nicht** in die ISO ein, bevor Stufe 3 steht.
