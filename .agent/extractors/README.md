# Language extractor plugins

Two ways to teach `k3dge check` a new language:

## 1. Generated (recommended)

Declare it in `.agent/extractors.toml`, then run `k3dge extractor sync`:

```toml
# Builtin rows (typescript/go/rust/c): just enable by name.
enable = ["typescript", "go"]

# Custom language: full row required (unknown/missing keys are hard errors).
[languages.mylang]
grammar = "tree_sitter_mylang"    # Python import name
package = "tree-sitter-mylang"    # pip name (may differ!)
lang_func = "language"
lang_name = "mylang"
suffixes = [".ml"]
wrapper = []
wrapper_kw = ""
fn = ["func_decl"]
container = []
body = []
member = []
type = ["type_decl"]
lexical_nodes = []
lexical_markers = []
lexical = false
```

(`fn`/`container`/`type`/… node tables: copy the closest builtin row from
`engine/extractor_gen.py` `DEFAULT_LANGS` and adjust names. Node types must be
verified against the real grammar — never guessed.)

Generated files carry a `GENERATED` header. `sync` rewrites changed ones and
prunes stale ones; markerless files are never touched. `k3dge sync` runs the
generator automatically when `.agent/extractors.toml` exists.

Missing grammar packages are reported (`pip install …`), never fatal:
files of that language are skipped until installed.

## 2. Hand-written

Drop a `.py` file here that calls `register_extractor()` at import —
# .agent/extractors/go.py
from pathlib import Path
from k3dge.engine.contract import ContractExtractor, register_extractor

class GoExtractor(ContractExtractor):
    def can_handle(self, path: Path) -> bool:
        return path.suffix == ".go"

    def extract(self, path: Path, include_doc: bool = False) -> str:
        ...  # return normalized public interface text

register_extractor(GoExtractor())
```

Rules:

- Files are loaded alphabetically on every `k3dge check`; first `can_handle` match wins.
- `register_extractor(ext, override=True)` inserts at front (overrides a built-in for the same suffix).
- Files starting with `_` are skipped (put shared helpers there).
- One bad file warns (`[WARN][EXTRACTOR]`) and the rest still load — a broken plugin never reds the gate.
- Alternatively, declare out-of-repo modules in manifest `extractors: ["mod" / "mod:attr"]`.
