# Risk and Adaptivity in Certifying Machine-Learning Model Comparisons

Jishan Kapoor · Independent Researcher · Toronto, Canada

Research manuscript prepared for PeerJ Computer Science. This private repository
stores the author's submission materials; it does not indicate journal acceptance.

## Start here

- [Read the paper](manuscript/revised_manuscript.pdf).
- [Editable LaTeX source](manuscript/revised_manuscript.tex).
- [Complete reproducibility release](https://github.com/floxy-21/risk-adaptivity-ml-audits/releases/tag/peerj-cs-2026-10-13).
- [Table-to-command map](source_snapshot/work/risk_adaptivity_revision/CURRENT_RESULTS_MAP.txt).
- [Fresh execution record](verification/current_clean_package_replay.json).

The main result characterizes which interval-width objectives can benefit from
adaptive acquisition. Fixed, adaptive and bulk retrieval have different assurance
and resource trade-offs; the paper reports where each is appropriate. It includes
proofs, two public-source replays, measurement sensitivities and exact witnesses.
The declared-cost frontier is a modeled comparison, not measured financial savings.

## Reproduce the complete current paper

Download `research_supplement.zip` from the release, verify its SHA-256 against
`RELEASE_SHA256.txt`, and extract it. Use the documented Python 3.12 environment:

```sh
python -m pip install -r requirements.txt
python work/risk_adaptivity_revision/reproduce.py
```

Run these commands from the extracted package root. The default entry point
checks all manifested files, creates a new isolated stage, blocks network access
during scientific replay, executes 39 checks, compares saved
scientific results and reconstructs the current manuscript byte-for-byte.
The tested environment and exact scope appear in the verification record.
Allow several minutes plus extraction/copy time and several GB of free disk.

Default replay uses frozen forecasts; it does not refit models, download source
data or repeat the archived API/timing measurements. Separate regeneration and
fresh-fitting commands are documented in the package. BLEM-derived raw traces are
regenerated locally rather than redistributed; attributed public-source caches
and constructed instances are bundled as documented.

## Repository and release contents

`manuscript/` contains the final PDF, editable source and local cover letter.
`source_snapshot/` provides browsable code, methods, documentation and small
fixtures from the exact release. Large frozen inputs remain in the complete ZIP
release asset rather than Git history. Run the full package, not this intentionally
partial source snapshot. `verification/` contains the final execution and review
records. SHA-256 checksums identify the precise manuscript and supplement.

The intact supplement retains necessary historical inputs and development records,
clearly separated from current results by its README and results map. No browser
sessions, account credentials, registration forms or private outreach drafts are
part of this repository.

## Attribution and status

Author contributions and supervised generative-AI assistance are disclosed in the
manuscript. Internal checks are not external human peer review. Third-party source
and data notices remain in the supplement; no blanket relicensing is asserted.
This repository is private. The manuscript has not been submitted or accepted.
