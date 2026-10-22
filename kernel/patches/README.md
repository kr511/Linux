# kernel/patches/

**In Kairo 0.1 absichtlich leer.** `linux-kairo` ist ein unveränderter
Upstream-Kernel von kernel.org.

Regeln für spätere Patches:

1. Erst wenn `linux-kairo` ohne Patches in QEMU **und** auf echter Hardware
   gebootet hat (siehe `STATUS.md`). Sonst weißt du bei einem Fehler nicht, ob
   der Patch schuld ist.
2. Ein Patch pro Datei, Format `NNNN-kurze-beschreibung.patch`
   (erzeugt mit `git format-patch`).
3. Jeder Patch bekommt hier einen Eintrag: Was, warum, Quelle (Mailingliste,
   Upstream-Commit), wann getestet.
4. Datei ins `source`-Array im PKGBUILD eintragen, `updpkgsums` ausführen,
   `pkgrel` erhöhen. `prepare()` wendet alle `*.patch` automatisch an.
5. Den Test `test_keine_patches_in_0_1` in `tests/test_kernel_package.py` dann
   bewusst entfernen.

| Patch | Zweck | Quelle | Getestet |
| --- | --- | --- | --- |
| *(keine)* | | | |
