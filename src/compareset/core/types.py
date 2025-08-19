from dataclasses import dataclass
from typing import Literal, Tuple, Optional

Kind = Literal["path", "text", "xobject"]
DiffKind = Literal["added", "removed", "changed"]
PaintMode = Literal["stroke", "fill", "both"]


@dataclass
class GraphicObject:
    obj_id: str
    kind: Kind
    page_index: int
    bbox: Tuple[float, float, float, float]
    paint_mode: PaintMode
    linewidth: Optional[float]
    stroke_color: Optional[Tuple[float, float, float]]
    fill_color: Optional[Tuple[float, float, float]]
    ctm: Tuple[float, float, float, float, float, float]
    stream_ref: str  # page:<index> or xobj:<name>
    ops_hint: Optional[Tuple[int, int]]


@dataclass
class Target:
    obj_id: str
    page_index: int
    kind: Kind
    diff: DiffKind
    paint_mode: PaintMode
    stream_ref: str
    ops_hint: Optional[Tuple[int, int]]
