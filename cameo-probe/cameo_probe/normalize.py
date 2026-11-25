"""Replace volatile values (IDs, timestamps) so observations can be compared and diffed."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence

# Starting assumptions about Cameo's ID formats. Confirm against live output (P-ELM-001).
DEFAULT_ID_PATTERNS = (
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
    r"_\d+(?:_\d+)*_[0-9a-f]+_\d{10,}_\d+_\d+",
    r"[A-Za-z]{3}_\d{10,}_\d+_\d+",
)
DEFAULT_TS_PATTERNS = (
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?",
)


class Normalizer:
    def __init__(self, id_patterns: Sequence[str] = DEFAULT_ID_PATTERNS,
                 ts_patterns: Sequence[str] = DEFAULT_TS_PATTERNS) -> None:
        self._ids = [re.compile(p) for p in id_patterns]
        self._ts = [re.compile(p) for p in ts_patterns]

    def normalize_run(self, values: Sequence[Any]) -> List[Any]:
        """Normalize the values of one run with a shared ID map.

        The same real ID always becomes the same placeholder (<ID:1>, <ID:2>, ...,
        numbered by first appearance), so two runs with different real IDs but the
        same behaviour normalize to equal structures.
        """
        mapping: Dict[str, str] = {}
        return [self._walk(v, mapping) for v in values]

    def _walk(self, value: Any, mapping: Dict[str, str]) -> Any:
        if isinstance(value, str):
            return self._string(value, mapping)
        if isinstance(value, dict):
            return {
                (self._string(k, mapping) if isinstance(k, str) else k): self._walk(v, mapping)
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [self._walk(v, mapping) for v in value]
        return value

    def _string(self, text: str, mapping: Dict[str, str]) -> str:
        def placeholder(match: "re.Match[str]") -> str:
            real = match.group(0)
            if real not in mapping:
                mapping[real] = f"<ID:{len(mapping) + 1}>"
            return mapping[real]

        for pattern in self._ids:
            text = pattern.sub(placeholder, text)
        for pattern in self._ts:
            text = pattern.sub("<TS>", text)
        return text
