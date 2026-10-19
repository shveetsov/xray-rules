#!/usr/bin/env python3
"""Verify all merged categories with the actual Mihomo parser, in small batches."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    args = parser.parse_args()
    directory = args.dist.resolve()
    manifest = json.loads((directory / "manifest.json").read_text())
    rules = []
    for filename, prefix in (("GeoSite.dat", "GEOSITE"), ("GeoIP.dat", "GEOIP")):
        rules.extend(prefix + "," + item["name"] + ",DIRECT" for item in manifest["outputs"][filename]["categories"])
    env = {**os.environ, "GOMEMLIMIT": "256MiB"}
    for start in range(0, len(rules), 40):
        config = {"geodata-mode": True, "geodata-loader": "memconservative", "geo-auto-update": False, "rules": rules[start:start + 40] + ["MATCH,DIRECT"]}
        with tempfile.TemporaryDirectory(prefix="mihomo-check-") as temp:
            path = Path(temp) / "config.json"
            path.write_text(json.dumps(config))
            result = subprocess.run([str(args.binary.resolve()), "-t", "-d", str(directory), "-f", str(path)], env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if result.returncode:
            print(result.stdout)
            raise SystemExit(result.returncode)
    print("Mihomo accepted all " + str(len(rules)) + " categories.")


if __name__ == "__main__":
    main()
