# RBL1 case (manual attachments)

This directory holds the redistributable part of the RBL1 regression case: the six primer rows transcribed from
Supplementary Table 2. The paper PDF is **not** committed.

Source identity:

- paper: Sha et al., *Genome editing of a rice CDP-DAG synthase confers multipathogen resistance*, Nature 618,
  1017–1023 (2023), DOI `10.1038/s41586-023-06205-2`
- open-access PDF: `https://escholarship.org/content/qt2321j386/qt2321j386.pdf`
- PDF SHA256: `323646482dd6a7536dbdcf8a23a3f61cbddd964c3bb15a65de90a4443aac3812`
- primer table (original XLSX): `https://static-content.springer.com/esm/art%3A10.1038%2Fs41586-023-06205-2/MediaObjects/41586_2023_6205_MOESM4_ESM.xlsx`
- this CSV is a transcription; its SHA256 is recorded in the generated source manifest

Run the local case (PDF optional for a smoke test):

```bash
bdc rbl1 --pdf /path/to/qt2321j386.pdf --primers examples/rbl1/primers.csv --out out/rbl1_case_final
```

Outputs: source manifest, sequence/association records, five tables, field-level evidence, triples and
`rbl1_case.json`. The PDF is checked against the expected SHA256 when supplied; it is never redistributed by
the repository.
