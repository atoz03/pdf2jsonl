# Source materials (immutable inputs)

These files are the original inputs from which the data contract was established.
They are **never edited**. The canonical contract lives in `field_catalog/field_catalog.yaml`;
tests (`tests/test_catalog_fidelity.py`, `tests/test_migrations.py`) check the catalog and
mappings against these files, so any divergence from the sources is deliberate and visible.

| Path | Origin | Role | sha256 |
| --- | --- | --- | --- |
| `archives/fields_v3__jsonl.zip` | `jsonl.zip` (contains `字段/`) | v3.0.0 field specification (authoritative) | `9f6d0b33b014966f538a0270995e6ea62b00589e29698d95d8f54dfec0a4c786` |
| `archives/legacy_v1__Jsonl.zip` | `Jsonl.zip` (contains `Jsonl/`) | legacy v1.0.0 document-centric design | `dedf9fa9576c162e18b98d08cdc366e853386737fb0922a23a578b84ffdb0b52` |
| `omics_v2/omics_metadata_template.json` | `omics_metadata_template.json` | multi-omics candidate template 2.0.0 | `608c4b84924de6149cdd3ec4e4b2385f9e4ba5d0088f05aa74f02f80d83682e0` |
| `project/record_functions.md` | data owner's requirement (2026-09-30), verbatim with the list line breaks restored | the four functions every key must serve (`key_role`, `serves`) | `8f00e7b4154da51bdc4e34e5d62bf5f4db1e878bdc339b013ca7b3c8fdd62f08` |
| `project/research_contents.md` | project research contents supplied by the data owner (2026-09-30), verbatim | definition of Topics 1–3; basis of the four record functions (`codes.function`, AMB-032) | `498fa2f3323a73ba9362f4915a1ebc25001a9b357d04b10d03d4f88a542cc386` |

Extracted members (byte-identical to the archive members):

| Path | sha256 |
| --- | --- |
| `fields_v3/breeding_fields_259_final.md` | `1c2b52936805f2c69a4254db920adc3d9e099d672ced1ee9cbbca9d44296ad44` |
| `fields_v3/breeding_fields_259_intro.md` | `dd8a60d0ed1c442a59d94a1980759f4ba853bd089f2af00139ce16f253444e2b` |
| `fields_v3/breeding_fields_compact_final.md` | `6c0569d569325d40643d355281afb01839b02af4646685c5b64f6b6dc982bcc4` |
| `fields_v3/breeding_fields_compact_intro.md` | `e4a62d2d7a624eed92bcb019df8c6ce70a53d40c8d5e362abed3bf26428fba31` |
| `legacy_v1/README.md` | `85241c22341fc3b6f9e24a8898a38a925233042449afc974602b163815ecd687` |
| `legacy_v1/breeding_jsonl_spec.md` | `5094159f1c3c35a4526df0fcf8d4e214b1f0a9577337d6e0de5f0be91214a329` |
| `legacy_v1/breeding_jsonl_schema.json` | `d058e1ef473fc56f0498c09da587c3b7a15eb9918466519daad0f1f8dc4e0aaf` |
| `legacy_v1/breeding_jsonl_template.json` | `18a90dfd2df154d88f30698b89de018444b884b3382a52a509b84599d73adbc7` |
| `legacy_v1/breeding_jsonl_example.jsonl` | `bbfa7e120ad0f84205a0e984a228ed3548e3373020d8ef7de06d11c9ae2b2031` |
| `legacy_v1/breeding_jsonl_example_pretty.json` | `6625f4552f9a4e1a48af92cf125aff471937df71a85c2125955101ec7e02c746` |

The original upload names `jsonl.zip` and `Jsonl.zip` differ only by case, which collides on
case-insensitive filesystems; they are stored under distinct prefixed names.

See `docs/source_analysis.md` for the structural analysis and the inconsistencies found.

## merged v2 archive (supplied 2026-10-06)

Original combined document/unit-row design, preserved verbatim. `docs/source_analysis.md` records what was
found in it and what the contract took from it; `docs/migration.md` describes its importer.

| Path | sha256 |
| --- | --- |
| `archives/merged_v2__merged.zip` | `a42f4b442a0845d89578f29673530904a11dc5fd14e6fec4dd32958e6faf3da0` |
| `merged_v2/README.md` | `9512818f6867fb9917ea38cff6c1c6bbac9f51c9305b588b30587650609f10b3` |
| `merged_v2/breeding_jsonl_example_v2.json` | `0bd04c6da25abef8f826e83b6cb1f2c7a863f286279bee32958bb25c6e2e346d` |
| `merged_v2/breeding_jsonl_example_v2.jsonl` | `0c67eaf677b9dc808fdfa41793ef8e42de1199fe017edde202c9bef6d84a177c` |
| `merged_v2/breeding_jsonl_schema_v2.json` | `45a3009e881468862a443910c225d09a891cea6b8c6d70f36b75cd93b9faadc4` |
| `merged_v2/breeding_jsonl_spec_v2.md` | `addb194233753913e3ee174cc934f95209bd1df737916098a024eee18f44b458` |
| `merged_v2/breeding_jsonl_template_v2.json` | `a1acf4380a6ef90397b2ab1daf0d3d175dd2597e13430f8655ded61254726e84` |
| `merged_v2/to_merged_mapping.md` | `04daf397a949e68c136aa30519ba7a8aeccccf9a90b5d84f79e8144c8d073eb1` |
