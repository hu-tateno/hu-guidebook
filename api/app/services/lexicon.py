"""Stage 2: student-slang -> institutional-term expansion, driven by data/search_lexicon.yaml.

Loaded fresh on every call (no caching) so that `mise run restart` / a redeploy after editing
the YAML is enough to pick up changes — no re-ingest/re-embed required, per README.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from app.config import get_settings


def load_lexicon(path: str | None = None) -> dict[str, list[str]]:
    lexicon_path = Path(path or get_settings().lexicon_path)
    if not lexicon_path.exists():
        return {}
    with lexicon_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        return {}
    return {
        str(key): [str(v) for v in values]
        for key, values in data.items()
        if isinstance(values, list)
    }


def expand_terms(query: str, lexicon: dict[str, list[str]] | None = None) -> list[str]:
    """Return institutional terms whose student-slang key appears in `query`, de-duplicated
    and excluding anything already equal to the query itself, in lexicon order."""
    lexicon = lexicon if lexicon is not None else load_lexicon()
    expanded: list[str] = []
    seen: set[str] = {query}
    for key, values in lexicon.items():
        if key in query:
            for term in values:
                if term not in seen:
                    expanded.append(term)
                    seen.add(term)
    return expanded
