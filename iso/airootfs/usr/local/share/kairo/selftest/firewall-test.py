#!/usr/bin/env python3
"""Probe IPv4/IPv6 input from a separate network namespace in the test VM."""

import json
import socket
import subprocess
import threading


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def reachable(address):
    code = "import socket; socket.create_connection((%r,48765),timeout=2).close()" % address
    return subprocess.run(["ip", "netns", "exec", "kairo-fw-client", "python3", "-c", code],
                          capture_output=True).returncode == 0


def accept_connections(server):
    while True:
        try:
            connection, _ = server.accept()
            connection.close()
        except OSError:
            return


def main():
    servers = []
    handle = None
    try:
        run("nft", "--check", "--file", "/etc/nftables.conf")
        run("ip", "netns", "add", "kairo-fw-client")
        run("ip", "link", "add", "kairo-fw-host", "type", "veth", "peer", "name", "kairo-fw-peer")
        run("ip", "link", "set", "kairo-fw-peer", "netns", "kairo-fw-client")
        for prefix, interface, addresses in [
                ([], "kairo-fw-host", ["192.0.2.1/30", "2001:db8::1/64"]),
                (["ip", "netns", "exec", "kairo-fw-client"], "kairo-fw-peer",
                 ["192.0.2.2/30", "2001:db8::2/64"])]:
            for address in addresses:
                run(*prefix, "ip", "address", "add", address, "dev", interface, "nodad")
            run(*prefix, "ip", "link", "set", interface, "up")
        for family, address in [(socket.AF_INET, "192.0.2.1"), (socket.AF_INET6, "2001:db8::1")]:
            server = socket.socket(family)
            servers.append(server)
            server.bind((address, 48765))
            server.listen()
            threading.Thread(target=accept_connections, args=(server,), daemon=True).start()
        # Positive control on precisely the same path; otherwise an unreachable
        # guest, broken namespace or stopped service could falsely pass the test.
        run("nft", "insert", "rule", "inet", "kairo", "input", "iifname", '"kairo-fw-host"',
            "tcp", "dport", "48765", "accept", "comment", '"kairo-firewall-probe"')
        rules = json.loads(run("nft", "--json", "--handle", "list", "chain", "inet", "kairo", "input"))
        handle = next(r["rule"]["handle"] for r in rules["nftables"]
                      if r.get("rule", {}).get("comment") == "kairo-firewall-probe")
        for address in ("192.0.2.1", "2001:db8::1"):
            if not reachable(address):
                raise RuntimeError("Firewall-Kontrollmessung fehlgeschlagen")
        run("nft", "delete", "rule", "inet", "kairo", "input", "handle", str(handle))
        handle = None
        # Each create_connection uses a fresh source port / connection tuple.
        for address in ("192.0.2.1", "2001:db8::1"):
            if reachable(address):
                raise RuntimeError("Unaufgeforderte eingehende Verbindung erlaubt")
        # Outbound TCP, DNS and response traffic must remain functional.
        run("curl", "--fail", "--silent", "--max-time", "30", "https://archlinux.org/")
        print("FIREWALL_PROBE=ok")
    finally:
        if handle is not None:
            run("nft", "delete", "rule", "inet", "kairo", "input", "handle", str(handle))
        for server in servers:
            server.close()
        subprocess.run(["ip", "link", "delete", "kairo-fw-host"], capture_output=True)
        subprocess.run(["ip", "netns", "delete", "kairo-fw-client"], capture_output=True)


if __name__ == "__main__":
    main()
