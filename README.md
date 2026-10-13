# Risk and Adaptivity in Certifying Machine-Learning Model Comparisons

Jishan Kapoor · Independent Researcher · Toronto, Canada

Research manuscript prepared for PeerJ Computer Science. This private repository
stores the author's submission materials; it does not indicate journal acceptance.

## Start here

- [Read the paper](manuscript/revised_manuscript.pdf).
- [Editable LaTeX source](manuscript/revised_manuscript.tex).
- [Complete reproducibility release](https://github.com/floxy-21/risk-adaptivity-ml-audits/releases/tag/peerj-cs-2026-10-13-joint).
- [Table-to-command map](source_snapshot/work/risk_adaptivity_revision/CURRENT_RESULTS_MAP.txt).
- [Fresh execution record](verification/current_clean_package_replay.json).
- [Final five-point review](verification/peerj_five_point_audit.txt).

The central result gives exact shared-query separations with explicit policies,
matching lower bounds and a worked real-data proof certificate. A scalar
classification provides the foundation for understanding adaptive acquisition. Fixed, adaptive and bulk retrieval have different assurance
and resource trade-offs; the paper reports where each is appropriate. It includes
proofs, two public-source replays, measurement sensitivities and exact witnesses.
The declared-cost frontier is a modeled comparison, not measured financial savings.

## Reproduce the complete current paper

Download `Supplemental_Data_S1.zip` and `Supplemental_Data_S2.zip` from the release,
verify their SHA-256 values against `RELEASE_SHA256.txt`, and extract both into
the same empty directory. These publisher-sized files contain the current
reproduction package. Use the documented Python 3.12 environment:

```sh
python -m pip install -r requirements.txt
python work/risk_adaptivity_revision/reproduce.py
```

Run these commands from the extracted package root. The default entry point
checks all manifested files, creates a new isolated stage, blocks network access
during scientific replay, executes 69 checks, compares saved
scientific results and reconstructs the current manuscript byte-for-byte.
The tested environment and exact scope appear in the verification record.
The verified run took about 18.9 minutes on
the study host, plus extraction/copy time; allow several GB of free disk.

Default replay uses frozen forecasts; it does not refit models, download source
data or repeat the archived API/timing measurements. Separate regeneration and
fresh-fitting commands are documented in the package. BLEM-derived raw traces are
regenerated locally rather than redistributed; attributed public-source caches
and constructed instances are bundled as documented.

A separate completed source-to-table run checked pinned original counters,
restored the exact frozen forecast archive, regenerated both panels' policies
and exact certificates, and reproduced all 1,098 outcome rows. Its commands,
scope and execution records are in `joint_certification/provenance_chain/`.
That run uses frozen models; it is not fresh fitting or external human review.

## Repository and release contents

`manuscript/` contains the final PDF, editable source and local cover letter.
`source_snapshot/` provides browsable code, methods, documentation and small
fixtures from the exact release. Large frozen inputs remain in the complete ZIP
release asset rather than Git history. Run the full package, not this intentionally
partial source snapshot. `verification/` contains the final execution and review
records. SHA-256 checksums identify the precise manuscript and supplement.

The larger `research_supplement.zip` preserves historical development records.
The publisher package omits unused historical caches and lists those omissions;
its 69-step execution uses the same scientific files and driver. No browser
sessions, account credentials, registration forms or private outreach drafts are
part of this repository.

## Attribution and status

Author contributions and supervised generative-AI assistance are disclosed in the
manuscript. Internal checks are not external human peer review. Third-party source
and data notices remain in the supplement; no blanket relicensing is asserted.
This repository is private. The manuscript has not been submitted or accepted.
