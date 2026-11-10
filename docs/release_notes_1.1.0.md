# Tooling 1.1.0 (2026-11-10)

This is a **tooling/view release**, not a contract release. The data contract stays at
`breeding-literature-record 3.8.0`: no field, vocabulary, profile or rule changed, and
`bdc diff 3.8.0 dev` reports `added 0, removed 0, changed 0`.

## Added

- **Per-paper research view**: select one paper, see only its phenotype–gene–population relations. QTL/QTN
  are on the gene layer; every other relation is counted but not shown.
- **Full-network toggle**: the same relations merged across papers, with deduplication.
- **Complete evidence chains** (`breeding_contract.evidence_chain`): claim → data/result → experiment/method,
  with quotes, page, section, figure/table, supplement and statistics at every node. Missing links are shown,
  never invented.
- **Article package** (`breeding_contract.article_package`): main text, figures, tables, supplement,
  data/code availability and licence; `complete` / `partial` / `unverified` / `not_submitted`.
- **Cross-paper aggregation** (`breeding_contract.aggregate`): cluster, deduplicate, direction conflicts and
  deterministic A/B/C confidence with the reasons.
- **Human review**: per-paper `人工复核（N）` button, approve / reject / return for evidence, notes, local
  browser decisions, export to JSON, and `bdc review apply` to write `review_status` / `review_note`.
- **Dashboard generation**: `scripts/make_network_dashboard.py`, `scripts/make_network_demo.py`,
  `site/pages/network.html`, `site/pages/network.js`; `make dashboard` now writes the simplified view and
  `make dashboard-full` keeps the previous paper dashboard.
- Runtime-derived JSON export: `--json-out`.

## Verification

- `bdc check --strict`: 0 error / 0 warning.
- Existing and new tests pass on the development environment (targeted suite: evidence chains, article
  packages, aggregation, review, network view, presentation contract, dashboard).
- A clean copy of the working tree, with no `out/` and no `dashboard.html`, reproduces the four-paper demo:
  4 papers, 6 nodes, 6 merged relations, 11 evidence items, 6 hidden relations; `dashboard.html` and
  `research_view.json` are generated.

## Notes

- `dashboard.html` and `out/` remain untracked/generation output.
- The demo's fourth paper is synthetic and exists to exercise cross-paper deduplication.
- The front-end review decisions are browser-local until exported; applying them requires
  `bdc review apply`.
