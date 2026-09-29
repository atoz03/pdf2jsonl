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
