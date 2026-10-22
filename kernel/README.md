# kernel/: linux-kairo

Eigenes Kernel-Paket für Kairo. Vollständige Anleitung:
[`docs/04-kernel-bauen.md`](../docs/04-kernel-bauen.md).

## Dateien

| Datei | Zweck |
| --- | --- |
| `linux-kairo/PKGBUILD` | Bauanleitung für `linux-kairo` und `linux-kairo-headers` |
| `linux-kairo/kairo.config` | Kairo-Anforderungen an die Kernel-Config (47 Optionen, kommentiert) |
| `linux-kairo/verify-config.py` | Bricht den Build ab, wenn eine Anforderung nicht erfüllt ist |
| `linux-kairo/config.arch-base` | **Fehlt noch.** Komplette Arch-Config, wird per `scripts/kernel-import-arch-config.sh` erzeugt |
| `patches/` | Spätere Kernel-Patches. In 0.1 leer, siehe `patches/README.md` |

## Wie die Config entsteht

```
config.arch-base          (offizielle Arch-Config, ~10.000 Zeilen)
      +  kairo.config     (Kairo-Pflichtoptionen)
      │
      ▼  scripts/kconfig/merge_config.sh -m
      ▼  make olddefconfig        (löst Abhängigkeiten auf)
      ▼  verify-config.py         (Abbruch, falls olddefconfig etwas verworfen hat)
      │
   .config  ──►  make  ──►  linux-kairo-*.pkg.tar.zst
```

## Versionen

| | Wert | Geprüft am | Quelle |
| --- | --- | --- | --- |
| `pkgver` | 7.2.12 | 2026-10-22 | Tag `v7.2.12` im Stable-Spiegel github.com/gregkh/linux |
| Arch-Kernel zum Vergleich | 7.2.11-arch1 | 2026-10-22 | Tag im Spiegel github.com/archlinux/linux |
| Aktuelle Mainline | 7.3 | 2026-10-22 | Tag `v7.3` |

7.2.12 ist die neueste Version der Serie, die Arch gerade ausliefert. Damit
passt die Arch-Basis-Config ohne große Sprünge. Ob 7.2 noch Updates bekommt,
siehst du auf [kernel.org](https://www.kernel.org) ("EOL" hinter der Version).
