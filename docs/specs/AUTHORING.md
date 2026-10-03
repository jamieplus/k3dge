# Authoring

New domain: register in `manifest.json` first, copy `docs/specs/_template/spec.md`.
Do not hand-edit Contract Hash; run `k3dge sync`.

Keep the template's four numbered sections in order and do not renumber/reorder them — the gate rejects
out-of-order numbered sections (`DOC_SECTION_ORDER`) and any missing required section (`SPEC_MISSING_SECTION`).
Every "Verification Matrix" row must resolve to a concrete test: write `file::test_name`, not a bare file
name — `MISSING_TEST_FILE` / `MATRIX_TEST_UNRESOLVED` fire otherwise. `k3dge check` applies these structural
rules and blocks the commit; run it before committing.
