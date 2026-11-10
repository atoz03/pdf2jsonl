# Documentation

Start with the project README ([English](../README.en.md) · [简体中文](../README.md)). This page lists the
guides and reference files, and says where new writing belongs. Files marked *zh* are written in Chinese.

## Guides

How the project works and why, one topic per file. They describe current behaviour.

| Guide | Read it for |
| --- | --- |
| [architecture.md](architecture.md) | Components, data flow, pipeline stages, invariants, the checks CI runs |
| [versioning.md](versioning.md) | Semantic versioning of the contract, releases, `latest` / `dev`, compatibility, changing the contract |
| [downstream.md](downstream.md) | The record as a hub: the hooks consumers need, every output of `bdc derive`, source parts and incomplete papers |
| [workflow.md](workflow.md) | The research workflow of a paper as roles and links between records |
| [review.md](review.md) | The three layers of checking, `bdc verify`, review statuses, what experts decide |
| [relation_semantics.md](relation_semantics.md) *zh* | Relation nature, resolution, claim strength, validation status |
| [research_view.md](research_view.md) *zh* | The per-paper research view, evidence chains, article packages, A/B/C confidence, human review |
| [presentation.md](presentation.md) *zh* | Display rules every record list must follow (enforced by `bdc check`) |
| [migration.md](migration.md) | The three importers, the mapping files and the derived views |
| [source_analysis.md](source_analysis.md) | The source designs, their inconsistencies and the merge decisions |
| [field_functions.md](field_functions.md) | What every key is for: roles, the four functions, cards, the evidence chain (TRACE), the audit |

## Reference

| File | What it is |
| --- | --- |
| [generated/](generated/) | Built from the catalog by `bdc generate`; never edited by hand. Start with [field_definitions.md](generated/field_definitions.md); also the [field dictionary](generated/field_dictionary.md) ([CSV](generated/field_dictionary.csv)), [field functions](generated/field_functions.md), [profiles](generated/profiles.md), [rules](generated/rules.md), [vocabularies](generated/vocabularies.md), [ambiguities](generated/ambiguities.md) |
| [field_examples.yaml](field_examples.yaml), [field_classification.yaml](field_classification.yaml) | Inputs to the generated reference: an illustrative value and functional tags for every field |
| [diagrams/pipeline.html](diagrams/pipeline.html) | Source of the pipeline poster; `make diagram` exports the SVGs |
| [acceptance_3.8.0.md](acceptance_3.8.0.md) *zh* | Regression acceptance report, written by `make acceptance` |
| [Site](https://atoz03.github.io/pdf2jsonl/) | Field catalog, contract browser, paper dashboard and examples, built by `make site` |

## History

| File | What it is |
| --- | --- |
| [../CHANGELOG.md](../CHANGELOG.md) | Curated notes for every contract and tooling release, plus `Unreleased` |
| [releases/README.md](releases/README.md) | Release index: every version with its date, summary and long-form notes; text retired from the READMEs |

## Where things go

| Content | Home |
| --- | --- |
| What the project is, what it can do now, how to install and run it, links onward | `README.md` and `README.en.md`, kept to the same scope. Current version numbers only, no per-version sections. |
| How one part works and why | A guide in `docs/`. Describe current behaviour; name a version only where behaviour depends on it. |
| Field, rule, vocabulary and profile details | The catalog sources, then `bdc generate`. Never hand-edit `docs/generated/`. |
| What a release changed | One `CHANGELOG.md` entry per release (format stated at its top); unreleased work under `[Unreleased]`. |
| Long release write-ups, trial reports, retired README text | `docs/releases/`, linked from the changelog entry and the release index. Not updated afterwards. |
