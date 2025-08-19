"""Utility helpers to convert geometric diff information into targets.

The real project will consume sophisticated diff data structures.  For
our tests we only need a very small bridge that maps a dictionary of
object ids to diff kinds.
"""
from __future__ import annotations

from typing import Dict, Iterable, List

from .types import DiffKind, GraphicObject, Target


def build_targets(objects: Iterable[GraphicObject], diff_map: Dict[str, DiffKind]) -> List[Target]:
    """Create :class:`Target` instances for objects affected by a diff.

    Parameters
    ----------
    objects:
        Iterable of extracted :class:`GraphicObject`.
    diff_map:
        Mapping of ``obj_id`` to ``DiffKind`` values describing whether the
        object was added, removed or changed.
    """

    targets: List[Target] = []
    for obj in objects:
        diff = diff_map.get(obj.obj_id)
        if not diff:
            continue
        target = Target(
            obj_id=obj.obj_id,
            page_index=obj.page_index,
            kind=obj.kind,
            diff=diff,
            paint_mode=obj.paint_mode,
            stream_ref=obj.stream_ref,
            ops_hint=obj.ops_hint,
        )
        targets.append(target)
    return targets
