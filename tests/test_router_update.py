import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
STUB = r'''
import hashlib, json, os
from pathlib import Path
import shutil, sys
name = Path(sys.argv[0]).name
root = Path(os.environ["FIXTURE"])
args = sys.argv[1:]
if name == "curl":
    url = next(arg for arg in args if arg.startswith("https://"))
    out = Path(args[args.index("-o") + 1])
    if "/releases/latest" in url:
        out.write_text('{"tag_name":"test-123"}')
    else:
        assert "/releases/download/test-123/" in url, url
        asset = url.rsplit("/", 1)[1]
        if os.environ.get("FAIL_DOWNLOAD") == asset:
            sys.exit(22)
        shutil.copyfile(root / "release" / asset, out)
elif name == "yq":
    print(json.loads(Path(args[-1]).read_text())["tag_name"])
elif name == "sha256sum":
    for line in Path(args[-1]).read_text().splitlines():
        expected, path = line.split()
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
            sys.exit(1)
elif name == "mihomo":
    stage = Path(args[args.index("-d") + 1])
    assert (stage / "GeoSite.dat").read_bytes() == b"new-site"
    assert (stage / "GeoIP.dat").read_bytes() == b"new-ip"
    if os.environ.get("FAIL_VALIDATE"):
        sys.exit(1)
    if os.environ.get("REPLACE_STAGE"):
        (stage / "GeoSite.dat").write_bytes(b"replaced by validator")
elif name == "xkeen":
    log = root / "restarts"
    count = len(log.read_text().splitlines()) if log.exists() else 0
    with log.open("a") as output:
        output.write("restart\n")
    if os.environ.get("FAIL_RESTART") and count == 0:
        sys.exit(1)
elif name == "pidof":
    print(1234)
'''


class RouterUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        (self.home / "config.yaml").write_text("mode: rule\n")
        (self.home / "GeoSite.dat").write_bytes(b"old-site")
        (self.home / "GeoIP.dat").write_bytes(b"old-ip")
        release = self.root / "release"
        release.mkdir()
        sums = []
        for name, data in (("GeoSite.dat", b"new-site"), ("GeoIP.dat", b"new-ip")):
            (release / name).write_bytes(data)
            sums.append(hashlib.sha256(data).hexdigest() + "  " + name)
        (release / "SHA256SUMS").write_text("\n".join(sums) + "\n")
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        for name in ("curl", "yq", "sha256sum", "mihomo", "xkeen", "pidof"):
            path = bin_dir / name
            path.write_text("#!" + sys.executable + "\n" + STUB)
            path.chmod(0o755)
        self.env = {**os.environ, "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"], "FIXTURE": str(self.root), "MIHOMO_HOME": str(self.home)}

    def run_update(self, **extra):
        return subprocess.run(["/bin/sh", str(ROOT / "router/update-mihomo-geodata.sh")], env={**self.env, **extra}, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def assert_old(self):
        self.assertEqual((self.home / "GeoSite.dat").read_bytes(), b"old-site")
        self.assertEqual((self.home / "GeoIP.dat").read_bytes(), b"old-ip")
        self.assertFalse((self.home / ".geodata-update.lock").exists())

    def test_success_installs_both_and_restarts_once(self):
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual((self.home / "GeoSite.dat").read_bytes(), b"new-site")
        self.assertEqual((self.home / "GeoIP.dat").read_bytes(), b"new-ip")
        self.assertEqual((self.root / "restarts").read_text().splitlines(), ["restart"])

    def test_failed_second_download_keeps_both_previous_files(self):
        result = self.run_update(FAIL_DOWNLOAD="GeoIP.dat")
        self.assertNotEqual(result.returncode, 0)
        self.assert_old()
        self.assertFalse((self.root / "restarts").exists())

    def test_checksum_failure_keeps_previous_files(self):
        (self.root / "release/GeoIP.dat").write_bytes(b"corrupt")
        result = self.run_update()
        self.assertNotEqual(result.returncode, 0)
        self.assert_old()

    def test_invalid_geodata_keeps_previous_files(self):
        result = self.run_update(FAIL_VALIDATE="1")
        self.assertNotEqual(result.returncode, 0)
        self.assert_old()
        self.assertFalse((self.root / "restarts").exists())

    def test_duplicate_checksums_do_not_leave_one_file_unchecked(self):
        path = self.root / "release/SHA256SUMS"
        path.write_text((path.read_text().splitlines()[0] + "\n") * 2)
        result = self.run_update()
        self.assertNotEqual(result.returncode, 0)
        self.assert_old()

    def test_validator_cannot_replace_database_after_checksum_verification(self):
        result = self.run_update(REPLACE_STAGE="1")
        self.assertNotEqual(result.returncode, 0)
        self.assert_old()

    def test_restart_failure_restores_pair_and_retries_old(self):
        result = self.run_update(FAIL_RESTART="1")
        self.assertNotEqual(result.returncode, 0)
        self.assert_old()
        self.assertEqual(len((self.root / "restarts").read_text().splitlines()), 2)

    def test_unchanged_data_does_not_restart(self):
        (self.home / "GeoSite.dat").write_bytes(b"new-site")
        (self.home / "GeoIP.dat").write_bytes(b"new-ip")
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertFalse((self.root / "restarts").exists())

    def test_initial_install_failure_removes_partial_pair(self):
        (self.home / "GeoSite.dat").unlink()
        (self.home / "GeoIP.dat").unlink()
        result = self.run_update(FAIL_RESTART="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.home / "GeoSite.dat").exists())
        self.assertFalse((self.home / "GeoIP.dat").exists())

    def test_another_update_lock_is_respected(self):
        (self.home / ".geodata-update.lock").mkdir()
        result = self.run_update()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.home / "GeoSite.dat").read_bytes(), b"old-site")
        self.assertTrue((self.home / ".geodata-update.lock").exists())


if __name__ == "__main__":
    unittest.main()
