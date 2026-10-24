"""Disk-use and replacement regressions; no real block devices are touched."""

import copy
import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("disk_guard", REPO / "iso/airootfs/usr/local/lib/kairo/disk_guard.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class DiskEligibilityTest(unittest.TestCase):
    def setUp(self):
        self.disk = {"path": "/dev/vda", "type": "disk", "size": 40 * 1024**3,
                     "serial": "A", "wwn": "", "model": "VM SSD", "maj:min": "254:0",
                     "ro": False, "mountpoints": [None], "children": [
                         {"path": "/dev/vda1", "type": "part", "mountpoints": [None]}]}

    def allowed(self):
        return guard.eligible(self.disk, set(), lambda _: False)

    def test_empty_disk_with_stable_identity_allowed(self):
        self.assertTrue(self.allowed())

    def test_mounts_on_disk_and_partition_rejected(self):
        for node in [self.disk, self.disk["children"][0]]:
            with self.subTest(node=node["path"]):
                node["mountpoints"] = ["/run/archiso/bootmnt"]
                self.assertFalse(self.allowed())
                node["mountpoints"] = [None]

    def test_active_swap_rejected(self):
        self.assertFalse(guard.eligible(self.disk, {"/dev/vda1"}, lambda _: False))

    def test_active_mapper_or_holder_rejected(self):
        self.assertFalse(guard.eligible(self.disk, set(), lambda p: p == "/dev/vda1"))
        self.disk["children"][0]["children"] = [{"path": "/dev/dm-0", "type": "crypt"}]
        self.assertFalse(self.allowed())

    def test_missing_identity_readonly_small_or_non_disk_rejected(self):
        for field, value in [("serial", ""), ("ro", True), ("size", 1024), ("type", "loop")]:
            original = self.disk[field]
            with self.subTest(field=field):
                self.disk[field] = value
                self.assertFalse(self.allowed())
            self.disk[field] = original

    def test_each_identity_change_is_detected(self):
        identity = guard.fingerprint(self.disk)
        for field in ("serial", "size", "wwn", "model", "path", "maj:min"):
            replacement = copy.deepcopy(self.disk)
            replacement[field] = str(replacement[field]) + "changed"
            with self.subTest(field=field):
                self.assertNotEqual(identity, guard.fingerprint(replacement))


class RejectionReasonTest(DiskEligibilityTest):
    """Every rejection must come with a reason the user can act on."""

    def why(self, swaps=frozenset(), holders=lambda _: False):
        return guard.reason(self.disk, set(swaps), holders)

    def test_usable_disk_has_no_reason(self):
        self.assertIsNone(self.why())

    def test_reason_agrees_with_eligible(self):
        cases = [("serial", ""), ("ro", True), ("size", 1024)]
        for field, value in cases:
            original = self.disk[field]
            with self.subTest(field=field):
                self.disk[field] = value
                self.assertIsNotNone(self.why())
                self.assertFalse(self.allowed())
            self.disk[field] = original

    def test_mounted_partition_is_named_with_advice(self):
        self.disk["children"][0]["mountpoints"] = ["/run/media/x"]
        text = self.why()
        self.assertIn("/dev/vda1", text)
        self.assertIn("eingehängt", text)

    def test_swap_and_holder_are_named(self):
        self.assertIn("Swap", self.why(swaps={"/dev/vda1"}))
        self.assertIn("/dev/vda1", self.why(holders=lambda p: p == "/dev/vda1"))

    def test_missing_identity_explained(self):
        self.disk["serial"] = ""
        self.assertIn("Seriennummer", self.why())


class InstallerDestructionBoundaryTest(unittest.TestCase):
    def run_installer(self, scenario="ok", confirmation="LÖSCHEN", automatic=True):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            bindir = directory / "bin"
            bindir.mkdir()
            fixture = directory / "guard.py"
            fixture.write_text('''import os, sys
from pathlib import Path
counter = Path(os.environ["COUNTER"])
if sys.argv[1] == "list":
    print("/dev/vda\\t40\\tVM SSD\\tSERIAL-A\\tidentity")
else:
    count = int(counter.read_text()) + 1 if counter.exists() else 1
    counter.write_text(str(count))
    if os.environ["SCENARIO"] in ("removed", "replaced", "mounted", "swap") and count >= 2:
        sys.exit(1)
    if sys.argv[3] != "identity": sys.exit(1)
''')
            for name in ("wipefs", "sgdisk", "mkfs.fat", "mkfs.btrfs", "cryptsetup",
                         "umount", "swapoff", "mount", "pacstrap", "arch-chroot"):
                path = bindir / name
                path.write_text('#!/bin/sh\necho "' + name + '" >> "$DESTRUCTIVE"\nexit 88\n')
                path.chmod(0o755)
            for name, body in {"curl": "exit 0", "lsblk": "echo 42949672960",
                               "mountpoint": "exit 1"}.items():
                path = bindir / name
                path.write_text("#!/bin/sh\n" + body + "\n")
                path.chmod(0o755)
            script = (REPO / "iso/airootfs/usr/local/bin/kairo-install").read_text()
            script = script.replace("/usr/local/lib/kairo/disk_guard.py", str(fixture))
            script = script.replace("(( EUID == 0 ))", "true")
            script = script.replace("[[ -d /run/archiso ]]", "true")
            script = script.replace("[[ -d /sys/firmware/efi ]]", "true")
            script = script.replace("/tmp/kairo-install.log", str(directory / "install.log"))
            path = directory / "install"
            path.write_text(script)
            env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}",
                       KAIRO_DISK="/dev/vda", KAIRO_USER="tester", KAIRO_PASSWORD="test",
                       KAIRO_ENCRYPT="0", SCENARIO=scenario, COUNTER=str(directory / "counter"),
                       DESTRUCTIVE=str(directory / "destructive"))
            env.pop("KAIRO_YES", None)
            if automatic:
                env["KAIRO_YES"] = "1"
            result = subprocess.run(["bash", str(path)], env=env, input=confirmation + "\n",
                                    capture_output=True, text=True, timeout=10)
            log = directory / "destructive"
            return result, log.read_text().splitlines() if log.exists() else []

    def test_positive_control_reaches_stubbed_wipefs(self):
        result, operations = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(operations, ["wipefs"])

    def test_rejected_disk_never_reaches_destructive_command(self):
        for scenario in ("removed", "replaced", "mounted", "swap"):
            with self.subTest(scenario=scenario):
                result, operations = self.run_installer(scenario)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(operations, [])

    def test_cancelled_confirmation_never_reaches_destructive_command(self):
        result, operations = self.run_installer(confirmation="nein", automatic=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(operations, [])
