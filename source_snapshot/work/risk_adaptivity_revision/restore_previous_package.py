"""Recover the exact preceding supplement layout, including its original entry point."""
from pathlib import Path
import argparse, hashlib, shutil
ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'work/risk_adaptivity_revision/prior_release'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--destination', type=Path, required=True)
    args=ap.parse_args()
    dest=args.destination.resolve()
    dest.mkdir(parents=True, exist_ok=False)
    special={'README.txt':BASE/'README_prior.txt',
             'outputs/revised_manuscript.tex':BASE/'revised_manuscript.tex'}
    count=0
    for line in (BASE/'MANIFEST_prior.sha256').read_text().splitlines():
        expected,name=line.split('  ',1)
        source=special.get(name,ROOT/name)
        assert sha(source)==expected, name
        target=(dest/name).resolve()
        assert target.is_relative_to(dest), name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        count+=1
    shutil.copy2(BASE/'MANIFEST_prior.sha256',dest/'MANIFEST.sha256')
    print(f'Restored {count} original manifested members; follow {dest / "README.txt"}.')
if __name__=='__main__':main()
