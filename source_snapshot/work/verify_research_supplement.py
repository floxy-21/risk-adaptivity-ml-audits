"""Verify every file listed in the extracted research supplement's SHA256 manifest."""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = ROOT / "MANIFEST.sha256"
    checked = 0
    for line in manifest.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT):
            raise ValueError(f"Manifest path leaves extraction directory: {relative}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"SHA256 mismatch for {relative}")
        checked += 1
    print(f"Verified {checked} packaged files against MANIFEST.sha256.")


if __name__ == "__main__":
    main()
