from __future__ import annotations

from typing import Iterable, List, Optional, Sequence

from .model import Probe


class Registry:
    def __init__(self, probes: Iterable[Probe] = ()) -> None:
        self._by_id = {}
        for probe in probes:
            self.register(probe)

    def register(self, probe: Probe) -> Probe:
        if probe.id in self._by_id:
            raise ValueError(f"duplicate probe id {probe.id}")
        self._by_id[probe.id] = probe
        return probe

    def all(self) -> List[Probe]:
        return [self._by_id[k] for k in sorted(self._by_id)]

    def select(self, family: Optional[str] = None, ids: Optional[Sequence[str]] = None) -> List[Probe]:
        if ids:
            for probe_id in ids:
                if probe_id not in self._by_id:
                    raise KeyError(probe_id)
            chosen = [self._by_id[i] for i in ids]
        else:
            chosen = self.all()
        if family:
            chosen = [p for p in chosen if p.family == family]
        return chosen


def builtin() -> Registry:
    from .probes import PROBES

    return Registry(PROBES)
