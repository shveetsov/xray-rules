#!/usr/bin/env python3
"""Build custom lists and merge the three XKeen sources into native geodata."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import urllib.request

from geodata import digest, merge, read_entries

ROOT = Path(__file__).resolve().parents[1]
KINDS = {"geosite": "GeoSite.dat", "geoip": "GeoIP.dat"}
TOOLS = {
    "dlc": "https://github.com/v2fly/domain-list-community.git",
    "geoip": "https://github.com/v2fly/geoip.git",
}
MAX_DOWNLOAD = 128 * 1024 * 1024


def github_request(url):
    headers = {"User-Agent": "shveetsov/xray-rules", "Accept": "application/vnd.github+json"}
    if url.startswith("https://api.github.com/") and os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    return urllib.request.Request(url, headers=headers)


def download_sources(config, destination):
    """Resolve each release once so pairs from one repository stay consistent."""
    releases = {}
    jobs = []
    for source in config["sources"]:
        for kind in KINDS:
            url = source[kind]
            match = re.fullmatch(r"https://github.com/([^/]+/[^/]+)/releases/latest/download/([^/]+)", url)
            if not match:
                raise ValueError("Expected a GitHub latest-release asset URL: " + url)
            repo, asset = match.groups()
            if repo not in releases:
                with urllib.request.urlopen(github_request("https://api.github.com/repos/" + repo + "/releases/latest"), timeout=60) as response:
                    releases[repo] = json.load(response)
            release = releases[repo]
            candidates = [item for item in release["assets"] if item["name"] == asset]
            if len(candidates) != 1:
                raise ValueError("Release asset is missing or ambiguous: " + url)
            item = candidates[0]
            jobs.append((source["name"], kind, item, release["tag_name"]))
    destination.mkdir(parents=True, exist_ok=True)

    def fetch(job):
        source, kind, asset, tag = job
        path = destination / (source + "-" + kind + ".dat")
        with urllib.request.urlopen(github_request(asset["browser_download_url"]), timeout=90) as response:
            with path.open("wb") as output:
                total = 0
                while chunk := response.read(65536):
                    total += len(chunk)
                    if total > MAX_DOWNLOAD:
                        raise ValueError("Upstream asset exceeds download limit")
                    output.write(chunk)
        data = path.read_bytes()
        if not data or len(data) != asset["size"]:
            raise ValueError("Incomplete upstream download: " + asset["name"])
        expected = asset.get("digest")
        if expected and expected != "sha256:" + digest(data):
            raise ValueError("GitHub asset checksum mismatch: " + asset["name"])
        print(source + "/" + kind + ": " + str(len(data)) + " bytes", flush=True)
        return source + "/" + kind, {"url": asset["browser_download_url"], "release": tag}

    with ThreadPoolExecutor(max_workers=4) as pool:
        return dict(pool.map(fetch, jobs))


def checkout_tool(path, url):
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--depth=1", url, str(path)], check=True)
    revision = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
    return {"repository": url, "commit": revision}


def build_custom(args, stage):
    env = os.environ.copy()
    env.update({"GOCACHE": str(args.cache_dir / "go-build"), "GOMODCACHE": str(args.cache_dir / "go-mod"), "GOPATH": str(args.cache_dir / "go")})
    tools = {}
    for name, url in TOOLS.items():
        directory = args.dlc_dir if name == "dlc" else args.geoip_tool_dir
        tools[name] = checkout_tool(directory, url)
    subprocess.run([
        "go", "run", "./", "--datapath=" + str(ROOT / "geosite/data"),
        "--outputdir=" + str(stage), "--outputname=geosite_shvetsov.dat",
    ], cwd=args.dlc_dir, env=env, check=True)
    inputs = []
    for path in sorted((ROOT / "geoip/data").glob("*.txt")):
        name = path.stem.lower()
        inputs.append({"type": "text", "action": "add", "args": {"name": name, "uri": str(path)}})
        if name != "all":
            inputs.append({"type": "text", "action": "add", "args": {"name": "all", "uri": str(path)}})
    if not inputs:
        raise ValueError("No custom IP lists found")
    config = {"input": inputs, "output": [{"type": "v2rayGeoIPDat", "action": "output", "args": {"outputName": "geoip_shvetsov.dat", "outputDir": str(stage)}}]}
    config_path = stage / "geoip-build.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    subprocess.run(["go", "run", "./", "-c", str(config_path)], cwd=args.geoip_tool_dir, env=env, check=True)
    config_path.unlink()
    for kind in KINDS:
        read_entries((stage / (kind + "_shvetsov.dat")).read_bytes(), kind)
    return tools


def write_catalog(path, catalog):
    lines = ["# Категории объединённых баз", "", "Названия можно использовать в GEOSITE/GEOIP в Mihomo и через ext: в Xray.", ""]
    for kind, items in catalog.items():
        lines += ["## " + KINDS[kind], "", "| Категория | Источник / ссылка | Записей |", "|---|---|---:|"]
        for item in items:
            origin = item.get("alias_of", item.get("source", ""))
            lines.append("| `" + item["name"] + "` | " + origin + " | " + str(item["records"]) + " |")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    parser.add_argument("--cache-dir", type=Path, default=ROOT / ".cache")
    parser.add_argument("--upstream-dir", type=Path, help="Use existing SOURCE-geosite.dat / SOURCE-geoip.dat instead of downloading")
    parser.add_argument("--dlc-dir", type=Path)
    parser.add_argument("--geoip-tool-dir", type=Path)
    args = parser.parse_args()
    args.cache_dir = args.cache_dir.resolve()
    args.dlc_dir = (args.dlc_dir or args.cache_dir / "tools/dlc").resolve()
    args.geoip_tool_dir = (args.geoip_tool_dir or args.cache_dir / "tools/geoip").resolve()
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    config = json.loads((ROOT / "sources.json").read_text())
    with tempfile.TemporaryDirectory(prefix="build-", dir=args.cache_dir) as temp:
        stage = Path(temp)
        upstream = args.upstream_dir.resolve() if args.upstream_dir else stage / "upstream"
        resolved = {} if args.upstream_dir else download_sources(config, upstream)
        tools = build_custom(args, stage)
        manifest = {"schema": 1, "built_at": datetime.now(timezone.utc).isoformat(), "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "tools": tools, "inputs": [], "outputs": {}}
        catalogs = {}
        for kind, filename in KINDS.items():
            sources = []
            for source in config["sources"]:
                name = source["name"]
                data = (upstream / (name + "-" + kind + ".dat")).read_bytes()
                sources.append((name, data))
                manifest["inputs"].append({"source": name, "kind": kind, "bytes": len(data), "sha256": digest(data), **resolved.get(name + "/" + kind, {"url": source[kind]})})
            custom = (stage / (kind + "_shvetsov.dat")).read_bytes()
            sources.append(("shvetsov", custom))
            manifest["inputs"].append({"source": "shvetsov", "kind": kind, "bytes": len(custom), "sha256": digest(custom)})
            data, catalogs[kind] = merge(sources, config["aliases"][kind], kind)
            (stage / filename).write_bytes(data)
            manifest["outputs"][filename] = {"sha256": digest(data), "bytes": len(data), "categories": catalogs[kind]}
            print(filename + ": " + str(len(catalogs[kind])) + " categories, " + str(len(data)) + " bytes", flush=True)
        (stage / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        write_catalog(stage / "categories.md", catalogs)
        for name in ("05_routing.json", "update-rules.sh", "update-mihomo-geodata.sh", "mihomo-rules.yaml"):
            shutil.copyfile(ROOT / "router" / name, stage / name)
        shutil.copyfile(ROOT / "README.md", stage / "README.md")
        files = sorted(path for path in stage.iterdir() if path.is_file())
        checksums = "".join(digest(path.read_bytes()) + "  " + path.name + "\n" for path in files)
        (stage / "SHA256SUMS").write_text(checksums, encoding="ascii")
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for path in [*files, stage / "SHA256SUMS"]:
            shutil.copyfile(path, args.output_dir / path.name)
        print("Build complete: " + str(args.output_dir), flush=True)


if __name__ == "__main__":
    main()
