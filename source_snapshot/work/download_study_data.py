"""Download original public study data and verify frozen SHA256 checksums.

Run from the extracted supplement root: python work/download_study_data.py
Needs Python standard library only. About 314 MB are downloaded and approximately
1.25 GB of working storage is needed before model fitting. Existing correct files
are reused. Unexpected existing contents fail explicitly rather than being erased.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request
import zipfile

from data_prepare_blem import prepare

ROOT = Path(__file__).resolve().parents[1]
SOURCES = [
    {
        "name": "UCI Individual Household Electric Power Consumption",
        "doi": "10.24432/C58K54", "license": "CC BY 4.0",
        "url": "https://archive.ics.uci.edu/static/public/235/individual%2Bhousehold%2Belectric%2Bpower%2Bconsumption.zip",
        "archive": "data_uci_household_power.zip",
        "archive_sha256": "9f84b46ade8a2d8e1286ec4b2b6c2987a45a755c59f263be3b3b3d10dfbda3ff",
        "member": "household_power_consumption.txt",
        "destination": "data_uci_household_power.txt",
        "text_sha256": "4259c9d7ece5dbee9ab8d53682baac68d791c864f0f64a52b4043cb3b90894b7",
    },
    {
        "name": "UCI ElectricityLoadDiagrams20112014",
        "doi": "10.24432/C58C86", "license": "CC BY 4.0",
        "url": "https://archive.ics.uci.edu/static/public/321/electricityloaddiagrams20112014.zip",
        "archive": "data_electricity.zip",
        "archive_sha256": "f6c4d0e0df12ecdb9ea008dd6eef3518adb52c559d04a9bac2e1b81dcfc8d4e1",
        "member": "LD2011_2014.txt", "destination": "data_electricity.txt",
        "text_sha256": "d51565f2cb5a6b768d06ba1bbd3c084c6e2f3aab07f00c6f2dcb80e90175124b",
    },
]


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def require_hash(path, expected):
    actual = digest(path)
    if actual != expected:
        raise ValueError(f"SHA256 mismatch: {path.name}; expected {expected}; got {actual}")


def fetch_uci(source, work):
    archive = work / source["archive"]
    if not archive.exists():
        partial = archive.with_suffix(archive.suffix + ".download")
        print(f"Downloading {source['name']} from {source['url']}", flush=True)
        request = urllib.request.Request(source["url"], headers={"User-Agent": "Python study reproducibility downloader"})
        with urllib.request.urlopen(request, timeout=180) as response, partial.open("wb") as dest:
            shutil.copyfileobj(response, dest, length=1024 * 1024)
        require_hash(partial, source["archive_sha256"])
        partial.replace(archive)
    require_hash(archive, source["archive_sha256"])
    destination = work / source["destination"]
    if not destination.exists():
        partial = destination.with_suffix(destination.suffix + ".extracting")
        # Extract exactly one known member to a fixed filename. No extractall.
        with zipfile.ZipFile(archive) as package:
            with package.open(source["member"]) as src, partial.open("wb") as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
        require_hash(partial, source["text_sha256"])
        partial.replace(destination)
    require_hash(destination, source["text_sha256"])
    print(f"Verified {archive.name} and {destination.name}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, default=ROOT / "work")
    parser.add_argument("--uci-only", action="store_true", help="Skip BLEM counter downloads/preparation")
    args = parser.parse_args()
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    for source in SOURCES:
        fetch_uci(source, work)
    if not args.uci_only:
        prepare(work, work, download=True)
        print("Verified and prepared all three pinned BLEM counter records", flush=True)
    (work / "data_download_audit.json").write_text(
        json.dumps({"uci_sources": SOURCES,
                    "blem": "See data_blem_preparation_audit.json and data_blem_provenance.json"}, indent=2),
        encoding="utf-8")
    print("Data preparation complete. Run tests, then outputs/run_energy_rank_study.py.", flush=True)


if __name__ == "__main__":
    main()
