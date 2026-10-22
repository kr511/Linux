#!/usr/bin/env python3
"""Prüft, ob eine fertige Kernel-.config alle Kairo-Anforderungen erfüllt.

Warum ist das nötig? Der Kernel-Konfigurator ("make olddefconfig") verwirft
still und leise Optionen, deren Abhängigkeiten nicht erfüllt sind, oder die es
gar nicht (mehr) gibt. Ohne diese Prüfung würde ein Tippfehler in kairo.config
niemandem auffallen, bis der Kernel auf echter Hardware nicht bootet.

Aufruf:
    python3 verify-config.py <fertige .config> <kairo.config>

Exit-Code 0 = alles erfüllt, 1 = mindestens eine Anforderung verletzt.
Nur Python-Standardbibliothek, keine Zusatzpakete nötig.
"""

import re
import sys

# "CONFIG_FOO=y", "CONFIG_FOO=m", 'CONFIG_FOO="text"' ...
SET_RE = re.compile(r"^(CONFIG_[A-Za-z0-9_]+)=(.*)$")
# "# CONFIG_FOO is not set" (so schreibt der Kernel "aus")
UNSET_RE = re.compile(r"^# (CONFIG_[A-Za-z0-9_]+) is not set$")


def parse_config(path):
    """Liest eine Kconfig-Datei in ein Dict {Optionsname: Wert}.

    Ausgeschaltete Optionen bekommen den Wert "n".
    """
    options = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if m := SET_RE.match(line):
                options[m.group(1)] = m.group(2)
            elif m := UNSET_RE.match(line):
                options[m.group(1)] = "n"
    return options


def is_satisfied(wanted, actual):
    """Vergleicht gewünschten und tatsächlichen Wert.

    Sonderfall: Wird "m" (Modul) verlangt, ist "y" (fest eingebaut) auch ok.
    Der Treiber ist dann trotzdem vorhanden, nur eben direkt im Kernel.
    """
    if wanted == actual:
        return True
    return wanted == "m" and actual == "y"


def main(argv):
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2

    actual = parse_config(argv[1])
    wanted = parse_config(argv[2])

    if not wanted:
        print(f"FEHLER: {argv[2]} enthält keine Optionen.", file=sys.stderr)
        return 1

    problems = []
    for name, want in sorted(wanted.items()):
        have = actual.get(name, "n")  # nicht erwähnt = aus
        if not is_satisfied(want, have):
            problems.append(f"  {name}: gewünscht {want}, tatsächlich {have}")

    if problems:
        print("FEHLER: Diese Kairo-Kernel-Optionen sind nicht erfüllt:")
        print("\n".join(problems))
        print("Ursache meist: Abhängigkeit fehlt oder Option existiert in"
              " dieser Kernelversion nicht. Prüfen mit 'make menuconfig' (/ Suche).")
        return 1

    print(f"OK: alle {len(wanted)} Kairo-Optionen sind erfüllt.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
