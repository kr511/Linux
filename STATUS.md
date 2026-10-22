# Kairo OS: Status

Diese Datei trennt **vorbereitete** Dateien von **tatsächlich getesteten**
Builds. Ein Eintrag wandert erst nach rechts, wenn der Test wirklich gelaufen
ist, mit Datum, Umgebung und Ergebnis.

Legende: ⬜ offen · 🟨 vorbereitet (Dateien existieren, nicht gebaut) ·
🟩 gebaut · ✅ gebaut **und** Boot-Test bestanden

| Komponente | Status | Nachweis |
| --- | --- | --- |
| Repository-Struktur | 🟩 | Dieser Commit |
| Statische Tests (`tests/run-all.sh`) | 🟩 | Lokal + CI, siehe unten |
| Kairo-ISO-Profil (Overlay auf releng) | 🟨 | Noch nie mit `mkarchiso` gebaut |
| Kairo-ISO bootet in QEMU (UEFI) | ⬜ | |
| `linux-kairo` PKGBUILD | 🟨 | `makepkg --printsrcinfo` läuft, Kernel nie gebaut |
| `linux-kairo` Config-Fragment | 🟩 | Optionen gegen echten 7.2.12-Quellcode geprüft, siehe unten |
| `linux-kairo` bootet in QEMU | ⬜ | |
| `linux-kairo` in der ISO | ⬜ | Erst nach erfolgreichem Einzeltest |

## Testprotokoll

Neue Einträge oben anfügen. Format:

```
### JJJJ-MM-TT: <was>
- Umgebung: <z. B. WSL2 Arch, archiso 91, QEMU 10.x>
- Befehl: <exakt>
- Ergebnis: <bestanden / fehlgeschlagen + Fehlermeldung>
```
