from src.compareset.overlay import make_annotation_style, tint_color


def test_make_annotation_style_uses_lightened_fill():
    base = (0.2, 0.4, 0.6)
    style = make_annotation_style(base, stroke_width=1.2, fill_opacity=0.3)

    assert style.stroke_color == base
    assert style.stroke_width == 1.2
    assert style.fill_opacity == 0.3
    for base_channel, fill_channel in zip(base, style.fill_color):
        assert fill_channel >= base_channel
        assert 0.0 <= fill_channel <= 1.0


def test_tint_color_clamps_and_blends_with_white():
    tinted = tint_color((0.5, 0.25, 0.0), blend=0.8)
    expected = (
        0.5 + (1.0 - 0.5) * 0.8,
        0.25 + (1.0 - 0.25) * 0.8,
        0.0 + (1.0 - 0.0) * 0.8,
    )
    assert tinted == expected

    # Blend values outside [0, 1] are clamped, and colours remain in range.
    clamped = tint_color((1.2, -0.5, 0.5), blend=2.0)
    assert all(0.0 <= channel <= 1.0 for channel in clamped)
