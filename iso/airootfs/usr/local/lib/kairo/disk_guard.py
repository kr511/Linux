#!/usr/bin/env python3
"""Read-only disk selection and identity checks before destructive installation."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def descendants(node):
    yield node
    for child in node.get("children", []):
        yield from descendants(child)


def fingerprint(node):
    fields = {key: node.get(key) for key in
              ("path", "maj:min", "size", "serial", "wwn", "model")}
    return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()


def reason(node, swaps, holders):
    """Why a disk may not be used, in German for the user; None if it may be."""
    if node.get("ro"):
        return "ist schreibgeschützt"
    if not (node.get("serial") or node.get("wwn")):
        return "meldet weder Seriennummer noch WWN, Kairo kann sie nicht sicher wiedererkennen"
    if int(node.get("size") or 0) < 32 * 1024**3:
        return "ist kleiner als 32 GiB"
    for dev in descendants(node):
        if any(dev.get("mountpoints") or []):
            return (f"{dev.get('path')} ist eingehängt (im Dateimanager angeklickt oder der "
                    "USB-Stick, von dem Kairo läuft). Im Dateimanager auswerfen und nochmal versuchen")
        if dev.get("path") in swaps:
            return f"{dev.get('path')} wird als Auslagerungsspeicher (Swap) benutzt"
        if dev.get("type") not in ("disk", "part"):
            return f"{dev.get('path')} ist ein {dev.get('type')}-Gerät (z. B. RAID oder Verschlüsselung), bitte erst trennen"
        if holders(dev["path"]):
            return f"{dev.get('path')} wird von einem anderen Gerät benutzt (z. B. LVM oder Verschlüsselung)"
    return None


def eligible(node, swaps, holders):
    if node.get("type") != "disk":
        return False
    return reason(node, swaps, holders) is None


def scan():
    result = subprocess.run(
        ["lsblk", "--json", "--bytes", "--paths", "--tree", "--output",
         "PATH,TYPE,SIZE,MODEL,SERIAL,WWN,RO,MAJ:MIN,MOUNTPOINTS"],
        check=True, capture_output=True, text=True)
    swaps = subprocess.run(["swapon", "--show=NAME", "--noheadings", "--raw"],
                           check=True, capture_output=True, text=True)
    swap_devices = {str(Path(p).resolve()) for p in swaps.stdout.splitlines()}

    def holders(path):
        # Missing sysfs data is not evidence that a disk is unused.
        directory = Path("/sys/class/block") / Path(path).resolve().name / "holders"
        return not directory.is_dir() or any(directory.iterdir())

    nodes = [n for n in json.loads(result.stdout)["blockdevices"] if n.get("type") == "disk"]
    return [(n, reason(n, swap_devices, holders)) for n in nodes]


def disks():
    return [n for n, why in scan() if why is None]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("list", "identity", "verify", "rejected"))
    parser.add_argument("disk", nargs="?")
    parser.add_argument("expected", nargs="?")
    args = parser.parse_args()
    try:
        if args.operation == "rejected":
            for node, why in scan():
                if why is not None:
                    print(f"{node['path']}\t{why}")
            return
        candidates = disks()
        if args.operation == "list":
            for node in candidates:
                values = [node["path"], str(int(node["size"]) // 1024**3),
                          node.get("model") or "unbekannt",
                          node.get("serial") or node["wwn"], fingerprint(node)]
                print("\t".join(str(v).replace("\t", " ").replace("\n", " ")
                                for v in values))
            return
        node = next((n for n in candidates if n["path"] == args.disk), None)
        if node is None:
            raise ValueError("Laufwerk fehlt, ist belegt oder nicht eindeutig identifizierbar")
        identity = fingerprint(node)
        if args.operation == "verify":
            if not args.expected or identity != args.expected:
                raise ValueError("Laufwerksidentität hat sich geändert; nichts wird gelöscht")
        else:
            print(identity)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"FEHLER: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
