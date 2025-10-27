"""Comparison parameter presets and color helpers."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, Iterable, Mapping, Optional, Tuple

Color = Tuple[float, float, float]


@dataclass(frozen=True)
class ColorScheme:
    """RGB color palette used for overlays."""

    added: Color = (0.0, 0.73, 0.0)
    removed: Color = (0.84, 0.0, 0.0)
    modified: Color = (0.93, 0.63, 0.0)
    text: Color = (0.15, 0.15, 0.15)

    def with_overrides(
        self,
        *,
        added: Optional[Color] = None,
        removed: Optional[Color] = None,
        modified: Optional[Color] = None,
        text: Optional[Color] = None,
    ) -> "ColorScheme":
        return ColorScheme(
            added=added or self.added,
            removed=removed or self.removed,
            modified=modified or self.modified,
            text=text or self.text,
        )

    def to_dict(self) -> Dict[str, Color]:
        return {
            "added": self.added,
            "removed": self.removed,
            "modified": self.modified,
            "text": self.text,
        }


@dataclass(frozen=True)
class CompareParams:
    """Parameters driving raster comparison and post-processing."""

    dpi: int = 300
    absdiff_threshold: int = 25
    ssim_threshold: float = 0.15
    added_threshold: int = 20
    removed_threshold: int = 20
    min_area_px: int = 196
    padding_px: int = 6
    merge_iou: float = 0.25
    morph_kernel_px: int = 5
    dilate_iterations: int = 1

    def to_dict(self) -> Dict[str, float]:
        return {
            "dpi": self.dpi,
            "absdiff_threshold": self.absdiff_threshold,
            "ssim_threshold": self.ssim_threshold,
            "added_threshold": self.added_threshold,
            "removed_threshold": self.removed_threshold,
            "min_area_px": self.min_area_px,
            "padding_px": self.padding_px,
            "merge_iou": self.merge_iou,
            "morph_kernel_px": self.morph_kernel_px,
            "dilate_iterations": self.dilate_iterations,
        }

    def copy(self, **overrides: float) -> "CompareParams":
        return replace(self, **overrides)


@dataclass(frozen=True)
class Preset:
    """Bundle of parameters, overlay styling and metadata."""

    name: str
    description: str
    params: CompareParams
    colors: ColorScheme
    fill_opacity: float = 0.22
    stroke_width: float = 1.0

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "description": self.description,
            "params": self.params.to_dict(),
            "colors": self.colors.to_dict(),
            "fill_opacity": self.fill_opacity,
            "stroke_width": self.stroke_width,
        }


_DEFAULT_COLORS = ColorScheme()

PRESETS: Mapping[str, Preset] = {
    "strict": Preset(
        name="strict",
        description="High confidence changes only; smallest tolerance.",
        params=CompareParams(
            dpi=360,
            absdiff_threshold=35,
            ssim_threshold=0.22,
            added_threshold=30,
            removed_threshold=30,
            min_area_px=256,
            padding_px=4,
            merge_iou=0.2,
            morph_kernel_px=3,
            dilate_iterations=1,
        ),
        colors=_DEFAULT_COLORS,
        fill_opacity=0.25,
        stroke_width=1.1,
    ),
    "balanced": Preset(
        name="balanced",
        description="Default mix of sensitivity and noise rejection.",
        params=CompareParams(
            dpi=300,
            absdiff_threshold=25,
            ssim_threshold=0.18,
            added_threshold=24,
            removed_threshold=24,
            min_area_px=196,
            padding_px=6,
            merge_iou=0.25,
            morph_kernel_px=5,
            dilate_iterations=1,
        ),
        colors=_DEFAULT_COLORS,
        fill_opacity=0.22,
        stroke_width=1.0,
    ),
    "loose": Preset(
        name="loose",
        description="Maximum sensitivity; tolerates small noisy regions.",
        params=CompareParams(
            dpi=240,
            absdiff_threshold=18,
            ssim_threshold=0.12,
            added_threshold=18,
            removed_threshold=18,
            min_area_px=96,
            padding_px=8,
            merge_iou=0.3,
            morph_kernel_px=7,
            dilate_iterations=2,
        ),
        colors=_DEFAULT_COLORS,
        fill_opacity=0.2,
        stroke_width=0.9,
    ),
}


def get_preset(name: str) -> Preset:
    key = name.lower()
    if key not in PRESETS:
        raise KeyError(f"Unknown preset '{name}'. Available: {', '.join(sorted(PRESETS))}")
    return PRESETS[key]


def iter_presets() -> Iterable[Preset]:
    return PRESETS.values()


def parse_color(value: Optional[str]) -> Optional[Color]:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if value.startswith("#"):
        hex_value = value[1:]
        if len(hex_value) not in (6, 8):
            raise ValueError("Hex colors must be #RRGGBB or #RRGGBBAA")
        rgb = tuple(int(hex_value[i : i + 2], 16) for i in range(0, 6, 2))
        return tuple(channel / 255.0 for channel in rgb)  # type: ignore[return-value]
    parts = value.replace(";", ",").split(",")
    if len(parts) != 3:
        raise ValueError("RGB colors must provide three comma separated numbers")
    rgb = tuple(float(p.strip()) for p in parts)
    if any(channel > 1.0 for channel in rgb):
        rgb = tuple(channel / 255.0 for channel in rgb)  # type: ignore[assignment]
    return rgb  # type: ignore[return-value]
