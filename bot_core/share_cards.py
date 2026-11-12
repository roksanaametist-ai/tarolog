from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps


WIDTH = 1080
HEIGHT = 1350

# Пропорции файлов колоды static/card*.jpg (1024×1748)
TAROT_CARD_RATIO = 1024 / 1748  # width / height

BG = (5, 5, 5)
INK = (245, 245, 247)
MUTED = (140, 140, 148)
SILVER = (210, 210, 216)
CARD_SLOT = (22, 22, 26)

# Облачный паттерн только по флагу (прод по умолчанию — чёрный фон)
SHARE_CLOUD_BG = os.getenv("SHARE_CLOUD_BG", "0").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_share_display_font() -> Path:
    """Landing `--font-display`: Project Space only (.otf then .ttf)."""
    root = _project_root()
    for path in (
        root / "landing" / "static" / "fonts" / "ProjectSpace.otf",
        root / "landing" / "static" / "fonts" / "ProjectSpace.ttf",
        root / "static" / "fonts" / "ProjectSpace.otf",
        root / "static" / "fonts" / "ProjectSpace.ttf",
        Path("/root/tarolog/static/fonts/ProjectSpace.otf"),
        Path("/root/tarolog/static/fonts/ProjectSpace.ttf"),
    ):
        if path.exists():
            return path
    return Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")


def resolve_share_font(preferred: str | Path | None = None) -> Path:
    root = _project_root()
    candidates: list[Path] = []
    # Prefer Project Space before any caller-supplied path so brand metrics
    # never silently fall back to Arial/DejaVu when a preferred file exists.
    display = resolve_share_display_font()
    if display.exists() and display.name.lower().startswith("projectspace"):
        candidates.append(display)
    if preferred:
        candidates.append(Path(preferred))
    candidates.extend(
        [
            root / "landing" / "static" / "fonts" / "ProjectSpace.otf",
            root / "landing" / "static" / "fonts" / "ProjectSpace.ttf",
            root / "static" / "fonts" / "ProjectSpace.otf",
            root / "static" / "fonts" / "ProjectSpace.ttf",
            Path("/root/tarolog/static/fonts/ProjectSpace.otf"),
            Path("/root/tarolog/static/fonts/ProjectSpace.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("C:/Windows/Fonts/arial.ttf"),
        ]
    )
    seen: set[str] = set()
    for path in candidates:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        if path.exists():
            return path
    return Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")


def resolve_share_body_font() -> Path:
    """Classical serif for reading summary (site body vibe / editorial)."""
    root = _project_root()
    for path in (
        root / "static" / "fonts" / "CormorantGaramond-Italic.ttf",
        root / "static" / "fonts" / "CormorantGaramond-Regular.ttf",
        Path("C:/Windows/Fonts/georgiai.ttf"),
        Path("C:/Windows/Fonts/georgia.ttf"),
        Path("C:/Windows/Fonts/times.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"),
        Path("/root/tarolog/static/fonts/DejaVuSerif.ttf"),
    ):
        if path.exists():
            return path
    return resolve_share_font()


def _font(font_path: Path, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(str(font_path), size=size)
    except (OSError, ValueError):
        for fallback in (
            resolve_share_font(),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("C:/Windows/Fonts/arial.ttf"),
        ):
            try:
                return ImageFont.truetype(str(fallback), size=size)
            except (OSError, ValueError):
                continue
    return ImageFont.load_default()


def _fit_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_path: Path,
    *,
    max_width: int,
    start_size: int,
    min_size: int,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for size in range(start_size, min_size - 1, -1):
        font = _font(font_path, size)
        box = draw.textbbox((0, 0), text, font=font)
        if (box[2] - box[0]) <= max_width:
            return font
    return _font(font_path, min_size)


def _wrap(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
    max_lines: int,
) -> list[str]:
    words = " ".join(str(text or "").split()).split()
    if not words:
        return []
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) == max_lines and len(" ".join(lines)) < len(" ".join(words)):
        last = lines[-1].rstrip(".,;:!?—- ")
        while last and draw.textbbox((0, 0), last + "…", font=font)[2] > max_width:
            last = last[:-1]
        lines[-1] = last.rstrip() + "…"
    return lines


def _text_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    return int(box[2] - box[0])


def _draw_centered(
    draw: ImageDraw.ImageDraw,
    y: float,
    text: str,
    *,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: tuple[int, int, int],
) -> None:
    w = _text_width(draw, text, font)
    draw.text(((WIDTH - w) / 2, y), text, font=font, fill=fill)


def _draw_fake_bold_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    text: str,
    *,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: tuple[int, int, int],
    radius: int = 1,
) -> None:
    """Heavier wordmark via offset redraws (Project Space has no bold cut)."""
    x, y = xy
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            draw.text((x + dx, y + dy), text, font=font, fill=fill)
    for ox in range(1, radius + 2):
        draw.text((x + ox, y), text, font=font, fill=fill)
        draw.text((x - ox, y), text, font=font, fill=fill)


def _paste_heavy_brand(
    canvas: Image.Image,
    xy: tuple[int, int],
    text: str,
    *,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: tuple[int, int, int] = INK,
    dilate: int = 2,
) -> int:
    """Light fake-bold via ~2–3 px offset redraws; returns advance width."""
    _ = dilate  # kept for call-site compat; weight is fixed light offsets
    probe = Image.new("L", (8, 8), 0)
    probe_draw = ImageDraw.Draw(probe)
    tw = _text_width(probe_draw, text, font)
    pad = 4
    th = int(getattr(font, "size", 48) * 1.35) + pad * 2
    mask = Image.new("L", (tw + pad * 2, th), 0)
    md = ImageDraw.Draw(mask)
    ox, oy = pad, pad // 2
    # Horizontal ±1/±2 + slight vertical — ~2–3 px, not MaxFilter fat stems
    for dx, dy in ((0, 0), (1, 0), (-1, 0), (2, 0), (-2, 0), (0, 1)):
        md.text((ox + dx, oy + dy), text, font=font, fill=255)
    colored = Image.new("RGBA", mask.size, (*fill, 0))
    colored.putalpha(mask)
    canvas.paste(colored, (xy[0] - pad, xy[1] - pad // 2), colored)
    return tw + 2


def _draw_soft_glow_text(
    canvas: Image.Image,
    xy: tuple[float, float],
    text: str,
    *,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: tuple[int, int, int] = INK,
    glow_alpha: int = 72,
    blur_radius: float = 2.4,
    weight_x: int = 0,
) -> None:
    """White text with a soft dark halo for readability on bright clouds."""
    probe = ImageDraw.Draw(Image.new("L", (8, 8)))
    bbox = probe.textbbox((0, 0), text, font=font)
    pad = max(8, int(blur_radius * 6))
    w = max(1, int(bbox[2] - bbox[0])) + pad * 2
    h = max(1, int(bbox[3] - bbox[1])) + pad * 2
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    tx = pad - bbox[0]
    ty = pad - bbox[1]
    ld.text((tx, ty), text, font=font, fill=(0, 0, 0, glow_alpha))
    glow = layer.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    canvas.paste(glow, (int(xy[0] - pad), int(xy[1] - pad)), glow)
    text_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    td = ImageDraw.Draw(text_layer)
    td.text((tx, ty), text, font=font, fill=(*fill, 255))
    if weight_x > 0:
        for dx in range(1, weight_x + 1):
            td.text((tx + dx, ty), text, font=font, fill=(*fill, 255))
    canvas.paste(text_layer, (int(xy[0] - pad), int(xy[1] - pad)), text_layer)


def _drapery_swag_path(
    strip_w: int,
    strip_h: int,
    *,
    panel_w: int,
    y0: float,
    sag: float,
    n: int = 128,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Smooth downward-arc path on the central swag (strip-local coords).

    Returns xs, ys, cumulative arc length. Cloth lip is a U: sides high,
    center lower — path matches that banner sag. Glyphs stay undeformed.
    """
    x0 = (strip_w - panel_w) * 0.5
    xs = np.linspace(x0, x0 + panel_w, max(8, n), dtype=np.float64)
    cx = strip_w * 0.5
    half = max(1.0, panel_w * 0.5)
    nx = (xs - cx) / half
    # Softer swag with smoother shoulders for a more flowing cloth line.
    t = np.clip(1.0 - np.abs(nx), 0.0, 1.0)
    curve = np.sin(t * np.pi / 2.0) ** 1.1
    ys = y0 + sag * curve
    dx = np.diff(xs)
    dy = np.diff(ys)
    seg = np.hypot(dx, dy)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    return xs, ys, cum


def _path_point_at(
    xs: np.ndarray, ys: np.ndarray, cum: np.ndarray, s: float
) -> tuple[float, float, float]:
    """Interpolate (x, y, tangent_radians) at arc length s along the path."""
    total = float(cum[-1])
    if total <= 1e-6:
        return float(xs[0]), float(ys[0]), 0.0
    s = float(np.clip(s, 0.0, total))
    i = int(np.searchsorted(cum, s, side="right") - 1)
    i = max(0, min(i, len(cum) - 2))
    span = cum[i + 1] - cum[i]
    t = 0.0 if span <= 1e-9 else (s - cum[i]) / span
    x = float(xs[i] * (1.0 - t) + xs[i + 1] * t)
    y = float(ys[i] * (1.0 - t) + ys[i + 1] * t)
    ang = float(np.arctan2(ys[i + 1] - ys[i], xs[i + 1] - xs[i]))
    return x, y, ang


def _draw_glyph_on_canvas(
    canvas: Image.Image,
    ch: str,
    *,
    xy: tuple[float, float],
    angle_rad: float,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: tuple[int, int, int, int],
) -> None:
    """Paste one undeformed FreeType glyph, rotated to path tangent."""
    if ch == " ":
        return
    probe = ImageDraw.Draw(Image.new("L", (8, 8)))
    bbox = probe.textbbox((0, 0), ch, font=font)
    ascent = max(1, -int(bbox[1]))
    descent = max(1, int(bbox[3]))
    tw = max(1, int(bbox[2] - bbox[0]))
    pad = 3
    gw = tw + pad * 2
    gh = ascent + descent + pad * 2
    glyph = Image.new("RGBA", (gw, gh), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glyph)
    baseline_y = pad + ascent
    gd.text((pad - bbox[0], baseline_y), ch, font=font, fill=fill)
    # Large square with pivot at center → rotate without expand (stable anchor)
    side = int(max(gw, gh) * 2.6) | 1
    big = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    cx = cy = side // 2
    big.paste(glyph, (cx - gw // 2, cy - baseline_y), glyph)
    deg = -float(np.degrees(angle_rad))
    rotated = big.rotate(deg, resample=Image.Resampling.BICUBIC)
    paste_x = int(round(xy[0] - cx))
    paste_y = int(round(xy[1] - cy))
    canvas.paste(rotated, (paste_x, paste_y), rotated)


def _draw_text_chunk_on_canvas(
    canvas: Image.Image,
    text: str,
    *,
    xy: tuple[float, float],
    angle_rad: float,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: tuple[int, int, int, int],
) -> None:
    """Paste one undeformed text chunk with supersampling for clean strokes."""
    if not text.strip():
        return
    scale = 4
    font_size = int(getattr(font, "size", 14))
    hi_font = _font(resolve_share_body_font(), max(8, font_size * scale))
    probe = ImageDraw.Draw(Image.new("L", (8, 8)))
    bbox = probe.textbbox((0, 0), text, font=hi_font)
    ascent = max(1, -int(bbox[1]))
    descent = max(1, int(bbox[3]))
    tw = max(1, int(bbox[2] - bbox[0]))
    pad = 10
    gw = tw + pad * 2
    gh = ascent + descent + pad * 2
    glyph = Image.new("RGBA", (gw, gh), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glyph)
    baseline_y = pad + ascent
    text_xy = (pad - bbox[0], baseline_y)
    gd.text(text_xy, text, font=hi_font, fill=fill)
    # Tiny second pass to add just a touch of weight without blurring the forms.
    gd.text((text_xy[0] + 1, text_xy[1]), text, font=hi_font, fill=fill)
    side = int(max(gw, gh) * 2.6) | 1
    big = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    cx = cy = side // 2
    big.paste(glyph, (cx - gw // 2, cy - baseline_y), glyph)
    deg = -float(np.degrees(angle_rad))
    rotated = big.rotate(deg, resample=Image.Resampling.BICUBIC)
    out_w = max(1, rotated.width // scale)
    out_h = max(1, rotated.height // scale)
    rotated = rotated.resize((out_w, out_h), Image.Resampling.LANCZOS)
    paste_x = int(round(xy[0] - out_w / 2))
    paste_y = int(round(xy[1] - out_h / 2))
    canvas.paste(rotated, (paste_x, paste_y), rotated)


def _draw_line_on_path(
    canvas: Image.Image,
    text: str,
    *,
    xs: np.ndarray,
    ys: np.ndarray,
    cum: np.ndarray,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: tuple[int, int, int, int],
    cloth_alpha: np.ndarray | None = None,
) -> None:
    """Place readable glyphs/chunks densely enough for a smooth cloth arc."""
    if not text:
        return
    probe = ImageDraw.Draw(Image.new("L", (8, 8)))
    chunks: list[tuple[str, int]] = []
    for ch in text:
        if ch == " ":
            width = max(4, int(getattr(font, "size", 14) * 0.35))
        else:
            bb = probe.textbbox((0, 0), ch, font=font)
            width = max(1, int(bb[2] - bb[0]))
        chunks.append((ch, width))
    total_w = float(sum(width for _, width in chunks))
    path_len = float(cum[-1])
    if path_len < 8:
        return
    # Center the line on the arc; if too long, start at 0 and clip naturally.
    s = max(0.0, (path_len - total_w) * 0.5)
    h_a, w_a = (cloth_alpha.shape[:2] if cloth_alpha is not None else (0, 0))
    for chunk, cw in chunks:
        mid = s + cw * 0.5
        if mid > path_len:
            break
        x, y, ang = _path_point_at(xs, ys, cum, mid)
        if cloth_alpha is not None:
            ix, iy = int(round(x)), int(round(y))
            if ix < 0 or iy < 0 or ix >= w_a or iy >= h_a or cloth_alpha[iy, ix] < 24:
                s += cw
                continue
        if chunk != " ":
            _draw_text_chunk_on_canvas(
                canvas, chunk, xy=(x, y), angle_rad=ang, font=font, fill=fill
            )
        s += cw


def _paste_quote_on_drapery(
    canvas: Image.Image,
    *,
    strip: Image.Image | None,
    strip_x: int,
    strip_y: int,
    strip_w: int,
    strip_h: int,
    lines: list[str],
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    line_step: int,
) -> None:
    """Draw summary as readable glyphs on curved paths following the swag."""
    if not lines:
        return
    panel_w = max(200, int(strip_w * 0.4))
    # High on drapery: stable readable baselines on the central swag.
    y0 = strip_h * 0.438
    sag = max(24.0, strip_h * 0.102)
    cloth_alpha = None
    if strip is not None:
        cloth_alpha = np.asarray(strip.convert("RGBA"))[:, :, 3]

    # Soft charcoal with a little more density so it doesn't wash out on folds.
    fill = (6, 6, 8, 255)
    layer = Image.new("RGBA", (strip_w, strip_h), (0, 0, 0, 0))

    max_lines = max(1, min(len(lines), 5))
    for li, line in enumerate(lines[:max_lines]):
        # Parallel offset down the swag with consistent rhythm.
        line_y0 = y0 + li * float(line_step)
        # Keep last baselines on opaque cloth (center lip ~0.52 + room)
        if line_y0 + sag > strip_h * 0.78:
            break
        xs, ys, cum = _drapery_swag_path(
            strip_w, strip_h, panel_w=panel_w, y0=line_y0, sag=sag
        )
        _draw_line_on_path(
            layer,
            line,
            xs=xs,
            ys=ys,
            cum=cum,
            font=font,
            fill=fill,
            cloth_alpha=cloth_alpha,
        )

    canvas.paste(layer, (strip_x, strip_y), layer)



def _card_crop(path: Path, size: tuple[int, int]) -> Image.Image | None:
    """Scale card to slot; prefer contain when ratios match so art isn't chopped."""
    try:
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            image = ImageEnhance.Contrast(image).enhance(1.04)
            tw, th = size
            iw, ih = image.size
            if iw <= 0 or ih <= 0 or tw <= 0 or th <= 0:
                return None
            src_ratio = iw / ih
            dst_ratio = tw / th
            # Same proportions (±2%) → contain+pad; else fit (blur bg only)
            if abs(src_ratio - dst_ratio) <= 0.02:
                fitted = ImageOps.contain(
                    image, (tw, th), method=Image.Resampling.LANCZOS
                )
                canvas = Image.new("RGB", (tw, th), BG)
                canvas.paste(
                    fitted, ((tw - fitted.width) // 2, (th - fitted.height) // 2)
                )
                return canvas
            return ImageOps.fit(image, size, method=Image.Resampling.LANCZOS)
    except Exception:
        return None


def _card_paste(
    canvas: Image.Image,
    image: Image.Image,
    box: tuple[int, int, int, int],
) -> None:
    """Paste full card face into a matching slot — thin silver rim, no soft window cut."""
    width = box[2] - box[0]
    height = box[3] - box[1]
    card = image.resize((width, height), Image.Resampling.LANCZOS)
    canvas.paste(card, (box[0], box[1]))
    rim = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ImageDraw.Draw(rim).rectangle(
        (0, 0, width - 1, height - 1),
        outline=(220, 220, 228, 140),
        width=2,
    )
    canvas.paste(rim, (box[0], box[1]), rim)


def _cloud_tile_path() -> Path | None:
    root = _project_root()
    for path in (
        root / "static" / "share" / "cloud_tile.jpg",
        root / "static" / "share" / "cloud_bg_source.png",
        Path("/root/tarolog/static/share/cloud_tile.jpg"),
        Path("/root/tarolog/static/share/cloud_bg_source.png"),
    ):
        if path.exists():
            return path
    return None


def _cloud_bg_path() -> Path | None:
    """Готовый фон облаков под размер шер-карточки (без ангелов/логотипа)."""
    root = _project_root()
    for path in (
        root / "static" / "share" / "clouds_share_1080x1350.jpg",
        root / "static" / "share" / "clouds_only_1080.jpg",
        root / "static" / "share" / "cloud_bg_pattern.jpg",
        root / "static" / "share" / "cloud_bg_1080.jpg",
        Path("/root/tarolog/static/share/clouds_share_1080x1350.jpg"),
        Path("/root/tarolog/static/share/clouds_only_1080.jpg"),
        Path("/root/tarolog/static/share/cloud_bg_pattern.jpg"),
        Path("/root/tarolog/static/share/cloud_bg_1080.jpg"),
    ):
        if path.exists():
            return path
    return None


def _background_from_card(
    path: Path | None,
    *,
    size: tuple[int, int] | None = None,
    cloud: bool | None = None,
) -> Image.Image:
    """Чёрный фон по умолчанию; облака с рефа — если SHARE_CLOUD_BG / cloud=True."""
    _ = path
    target = size or (WIDTH, HEIGHT)
    use_cloud = SHARE_CLOUD_BG if cloud is None else bool(cloud)
    if use_cloud:
        cloud_path = _cloud_bg_path()
        if cloud_path is not None:
            try:
                with Image.open(cloud_path) as src:
                    return ImageOps.fit(
                        src.convert("RGB"),
                        target,
                        method=Image.Resampling.LANCZOS,
                    )
            except Exception:
                pass
    return Image.new("RGB", target, BG)


def _shell_mark_path() -> Path | None:
    root = _project_root()
    for path in (
        root / "static" / "share-shell-mark.png",
        root / "landing" / "static" / "images" / "shell-hero-static.png",
        root / "landing" / "static" / "images" / "shell-open.png",
        Path("/root/tarolog/static/share-shell-mark.png"),
        Path("/root/tarolog/landing/static/images/shell-hero-static.png"),
    ):
        if path.exists():
            return path
    return None


def _cherub_path(name: str) -> Path | None:
    root = _project_root()
    for path in (
        root / "static" / "share" / "cherubs" / name,
        Path(f"/root/tarolog/static/share/cherubs/{name}"),
        root / "stickers" / "telegram" / "static" / name,
    ):
        if path.exists():
            return path
    return None


def _paste_shell_logo(
    canvas: Image.Image, *, xy: tuple[int, int], size: int = 36
) -> int:
    path = _shell_mark_path()
    if path is None:
        return 0
    try:
        with Image.open(path) as source:
            mark = ImageOps.contain(
                source.convert("RGBA"), (size, size), Image.Resampling.LANCZOS
            )
        canvas.paste(mark, xy, mark)
        return mark.width
    except Exception:
        return 0


def _load_angels_holding_drapery(max_width: int) -> Image.Image | None:
    """Load precomposed cherubs+cloth asset scaled to max_width."""
    path = _cherub_path("angels_holding_drapery.png")
    if path is None:
        return None
    try:
        with Image.open(path) as source:
            strip = source.convert("RGBA")
        return ImageOps.contain(
            strip, (max_width, max_width), Image.Resampling.LANCZOS
        )
    except Exception:
        return None


def _rgba_opaque_bounds(
    image: Image.Image, *, threshold: int = 8
) -> tuple[int, int, int, int]:
    """Opaque content box (left, top, right, bottom) with exclusive right/bottom."""
    rgba = image.convert("RGBA")
    alpha = np.asarray(rgba.split()[-1])
    ys, xs = np.where(alpha > threshold)
    if xs.size == 0:
        return (0, 0, rgba.width, rgba.height)
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)


def generate_share_card(
    output_path: str | Path,
    *,
    card_names: Iterable[str],
    card_paths: Iterable[str],
    summary: str,
    kind: str,
    font_path: str | Path,
    gift_questions: int,
    cloud: bool | None = None,
) -> Path:
    """Minimal share art: brand → cards + cherubs → quote. No CTA on image."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    paths = [Path(path) for path in card_paths if path][:3]
    names = [str(name).strip() for name in card_names if str(name).strip()][:3]
    font_file = resolve_share_font(font_path)
    use_cloud = SHARE_CLOUD_BG if cloud is None else bool(cloud)

    # Portrait canvas; crop to content
    canvas = _background_from_card(
        paths[0] if paths else None, size=(WIDTH, HEIGHT), cloud=use_cloud
    ).convert("RGBA")
    draw = ImageDraw.Draw(canvas, "RGBA")
    # White rim hugs card-row ∪ angel-wing opaque extents (+ small pad).
    frame_content_pad = 16
    # Keep a clean inset so the wordmark does not press into the white frame.
    brand_side_pad = 18
    bottom_pad = 20
    # Modest cloud margin kept beyond the white rim after final crop.
    frame_outer_pad = 24
    _ = kind

    # --- Measure / layout first (no frame yet) ---
    count = max(1, min(3, len(paths) or len(names) or 1))
    # Proportional shrink of the card row (cards + gaps) vs prior ~247×422,
    # then another 1.5× compact vs prior ~208×355 → ~139×237.
    card_row_scale = 0.84 / 1.5
    gap_cards = max(10, int(round(28 * card_row_scale)))
    # Prior outer air was 142; scale available width, then center the row.
    prior_avail = WIDTH - 2 * 142
    avail = max(200, int(round(prior_avail * card_row_scale)))
    max_card_w = (avail - gap_cards * (count - 1)) // count
    # Nudge toward ~139px slot (0.99 × floor math can land on 138).
    card_w = max(1, int(round(max_card_w * 0.992)))
    card_h = int(round(card_w / TAROT_CARD_RATIO))
    group_w = card_w * count + gap_cards * (count - 1)
    cards_left = (WIDTH - group_w) // 2
    cards_right = cards_left + group_w

    # Brand height probe (final size after frame width is known).
    brand = "FOLLOW THE FRENSY"
    display_font = resolve_share_display_font()
    # Provisional brand metrics for vertical stack; refit after frame width.
    brand_font = _fit_font(
        draw, brand, display_font, max_width=max(200, group_w - 16), start_size=44, min_size=14
    )
    brand_h = int(getattr(brand_font, "size", 34) * 1.15)
    # Top frame inset: modest air above brand (not locked to huge side margin).
    frame_top_pad = 34
    brand_y = frame_top_pad + 24
    brand_bottom = brand_y + brand_h
    card_y = brand_bottom + 20
    cards_bottom = card_y + card_h

    # Angel strip keeps near the pre-1.5× row width so the wordmark can grow
    # slightly; tarot slots stay compact and centered inside the wing span.
    strip_max_w = max(group_w, int(round(prior_avail * 0.84)))
    strip_y = cards_bottom + 20
    max_strip_h = max(240, canvas.height - strip_y - bottom_pad - 8)
    strip = _load_angels_holding_drapery(strip_max_w)
    if strip is not None:
        if strip.height > max_strip_h:
            scale = max_strip_h / strip.height
            strip = strip.resize(
                (max(1, int(strip.width * scale)), max_strip_h),
                Image.Resampling.LANCZOS,
            )
        strip_w, strip_h = strip.size
        strip_x = (WIDTH - strip_w) // 2
        ol, _ot, oright, _ob = _rgba_opaque_bounds(strip)
        angels_left = strip_x + ol
        angels_right = strip_x + oright
    else:
        strip_w = strip_max_w
        strip_h = min(max_strip_h, int(strip_max_w * 0.45))
        strip_x = (WIDTH - strip_w) // 2
        angels_left = strip_x
        angels_right = strip_x + strip_w

    content_left = min(cards_left, angels_left)
    content_right = max(cards_right, angels_right)
    frame_left = max(8, content_left - frame_content_pad)
    frame_right = min(WIDTH - 8, content_right + frame_content_pad)
    frame_inner_w = max(200, frame_right - frame_left)

    # Refit brand to final frame inner width (Project Space, no shell).
    brand_max_w = max(200, frame_inner_w - 2 * brand_side_pad)
    brand_font = _fit_font(
        draw, brand, display_font, max_width=brand_max_w, start_size=46, min_size=14
    )
    brand_w = _text_width(draw, brand, brand_font)
    brand_h = int(getattr(brand_font, "size", 34) * 1.15)
    brand_y = frame_top_pad + 24
    brand_bottom = brand_y + brand_h
    # If brand height changed, keep card_y from measured stack (already generous).
    card_y = max(card_y, brand_bottom + 28)
    cards_bottom = card_y + card_h
    strip_y = cards_bottom + 20

    # --- Draw: brand → cards → angels → quote; frame last ---
    brand_xy = (int((WIDTH - brand_w) / 2), brand_y)
    _draw_soft_glow_text(
        canvas,
        brand_xy,
        brand,
        font=brand_font,
        fill=INK,
        glow_alpha=68,
        blur_radius=2.2,
        weight_x=1,
    )
    draw = ImageDraw.Draw(canvas)

    draw = ImageDraw.Draw(canvas)
    x = cards_left
    for index in range(count):
        box = (x, card_y, x + card_w, card_y + card_h)
        image = (
            _card_crop(paths[index], (card_w, card_h)) if index < len(paths) else None
        )
        if image is not None:
            _card_paste(canvas, image, box)
        else:
            draw.rectangle(box, fill=CARD_SLOT, outline=SILVER, width=1)
        x += card_w + gap_cards

    if strip is not None:
        canvas.paste(strip, (strip_x, strip_y), strip)

    # Tagline 3 lines in wing notch above drapery (ref 5e6323dd)
    tagline_lines = (
        "ТВОЙ",
        "ПЕРСОНАЛЬНЫЙ",
        "БОТ",
        "ТАРОЛОГ",
    )
    draw = ImageDraw.Draw(canvas)
    tag_font = _fit_font(
        draw,
        max(tagline_lines, key=len),
        font_file,
        max_width=min(380, int(strip_w * 0.38)),
        start_size=21,
        min_size=14,
    )
    tag_line_step = max(23, int(getattr(tag_font, "size", 16) + 5))
    tag_block_h = tag_line_step * len(tagline_lines)
    wing_top_y = strip_y + int(strip_h * 0.14)
    cloth_top_y = strip_y + int(strip_h * 0.438)
    notch = max(tag_block_h + 8, cloth_top_y - wing_top_y)
    tag_y = wing_top_y + max(2, int((notch - tag_block_h) * 0.28))
    tag_y_max = cloth_top_y - tag_block_h - 8
    if tag_y > tag_y_max:
        tag_y = tag_y_max
    for tag in tagline_lines:
        tw = _text_width(draw, tag, tag_font)
        tx = (WIDTH - tw) / 2
        _draw_soft_glow_text(
            canvas,
            (tx, tag_y),
            tag,
            font=tag_font,
            fill=INK,
            glow_alpha=62,
            blur_radius=1.8,
        )
        tag_y += tag_line_step

    quote = " ".join(str(summary or "").split())
    if not quote:
        quote = "Карты подсветили главный акцент и следующий шаг."
    body_font_path = resolve_share_body_font()
    quote_max_w = max(240, int(strip_w * 0.42))
    # Stacked path lines on swag (readable; path sag handles the curve)
    quote_area_h = max(72, int(strip_h * 0.28))
    quote_font = _font(body_font_path, 17)
    quote_lines: list[str] = []
    line_step = 22
    for size in range(17, 11, -1):
        quote_font = _font(body_font_path, size)
        line_step = max(16, size + 5)
        max_lines = max(2, quote_area_h // line_step)
        quote_lines = _wrap(draw, quote, quote_font, quote_max_w, max_lines)
        fits_height = len(quote_lines) * line_step <= quote_area_h
        complete = not quote_lines or not quote_lines[-1].endswith("…")
        if fits_height and complete:
            break
        if fits_height and size <= 12:
            break
    _paste_quote_on_drapery(
        canvas,
        strip=strip,
        strip_x=strip_x,
        strip_y=strip_y,
        strip_w=strip_w,
        strip_h=strip_h,
        lines=quote_lines,
        font=quote_font,
        line_step=line_step,
    )

    _ = gift_questions

    content_bottom = strip_y + strip_h
    frame_top = frame_top_pad
    frame_bottom = min(canvas.height - 8, content_bottom + frame_content_pad)
    frame_bottom = max(frame_top + 40, frame_bottom)
    # Keep a little canvas below the frame so outer pad crop is possible.
    final_h = min(canvas.height, max(content_bottom + bottom_pad, frame_bottom + frame_outer_pad + 2))
    if final_h < canvas.height:
        canvas = canvas.crop((0, 0, WIDTH, final_h))
    draw = ImageDraw.Draw(canvas, "RGBA")
    draw.rectangle(
        (frame_left, frame_top, frame_right, frame_bottom),
        outline=(255, 255, 255, 40),
        width=1,
    )

    # Trim excess navy/cloud outside the white rim; leave modest outer pad.
    crop_left = max(0, frame_left - frame_outer_pad)
    crop_top = max(0, frame_top - frame_outer_pad)
    crop_right = min(canvas.width, frame_right + frame_outer_pad)
    crop_bottom = min(canvas.height, frame_bottom + frame_outer_pad)
    canvas = canvas.crop((crop_left, crop_top, crop_right, crop_bottom))

    rgb = canvas.convert("RGB")
    temporary = output.with_suffix(output.suffix + ".tmp")
    try:
        rgb.save(temporary, format="JPEG", quality=92, optimize=True)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return output



def _avatar_share_base_path() -> Path | None:
    root = _project_root()
    for path in (
        root / "static" / "share" / "avatar_share_base.png",
        root / "static" / "share" / "cloud_bg_source.png",
    ):
        if path.exists():
            return path
    return None


def generate_share_card_from_avatar(
    output_path: str | Path,
    *,
    card_names: Iterable[str],
    card_paths: Iterable[str],
    summary: str,
    kind: str,
    font_path: str | Path,
    gift_questions: int,
) -> Path:
    """Шер-карточка поверх аватарки: облака + ангелы с рефа, карты в центре круга."""
    _ = kind
    _ = gift_questions
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    base_path = _avatar_share_base_path()
    if base_path is None:
        raise FileNotFoundError("avatar_share_base.png not found in static/share/")

    size = WIDTH
    with Image.open(base_path) as src:
        canvas = ImageOps.fit(
            src.convert("RGB"), (size, size), method=Image.Resampling.LANCZOS
        ).convert("RGBA")

    # Лёгкое затемнение центра круга — чтобы карты читались
    cx = cy = size // 2
    circle_r = int(size * 0.28)
    dim = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(dim).ellipse(
        (cx - circle_r, cy - circle_r - 10, cx + circle_r, cy + circle_r - 10),
        fill=(0, 0, 0, 160),
    )
    canvas = Image.alpha_composite(canvas, dim)

    paths = [Path(path) for path in card_paths if path][:3]
    names = [str(name).strip() for name in card_names if str(name).strip()][:3]
    _ = names
    count = max(1, min(3, len(paths) or 1))
    gap = 14
    # Карты внутри золотого круга
    max_group_w = int(circle_r * 1.72)
    card_w = min(200, (max_group_w - gap * (count - 1)) // count)
    card_h = int(round(card_w / TAROT_CARD_RATIO))
    group_w = card_w * count + gap * (count - 1)
    card_y = cy - card_h // 2 - 18
    x0 = (size - group_w) // 2
    x = x0
    for index in range(count):
        box = (x, card_y, x + card_w, card_y + card_h)
        image = (
            _card_crop(paths[index], (card_w, card_h)) if index < len(paths) else None
        )
        if image is not None:
            _card_paste(canvas, image, box)
        x += card_w + gap

    font_file = resolve_share_font(font_path)
    draw = ImageDraw.Draw(canvas)
    tag = "СДЕЛАЛ РАСКЛАД"
    tag_font = _fit_font(
        draw, tag, font_file, max_width=int(circle_r * 1.6), start_size=22, min_size=14
    )
    tag_y = card_y + card_h + 14
    _draw_centered(draw, tag_y, tag, font=tag_font, fill=INK)

    # Итог между нижними ангелами рефа
    quote = " ".join(str(summary or "").split())
    if not quote:
        quote = "Карты подсветили главный акцент и следующий шаг."
    body_font_path = resolve_share_body_font()
    quote_max_w = int(size * 0.46)
    quote_area_top = int(size * 0.72)
    quote_area_h = int(size * 0.18)
    quote_font = _font(body_font_path, 16)
    line_step = 22
    quote_lines: list[str] = []
    for font_size in range(18, 12, -1):
        quote_font = _font(body_font_path, font_size)
        line_step = max(15, font_size + 5)
        max_lines = max(3, quote_area_h // line_step)
        quote_lines = _wrap(draw, quote, quote_font, quote_max_w, max_lines)
        complete = not quote_lines or not quote_lines[-1].endswith("…")
        if len(quote_lines) * line_step <= quote_area_h and complete:
            break
    # полупрозрачная плашка под текст
    plate = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pd = ImageDraw.Draw(plate)
    block_h = len(quote_lines) * line_step + 24
    plate_y0 = quote_area_top + max(0, (quote_area_h - block_h) // 2)
    pd.rounded_rectangle(
        (size // 2 - quote_max_w // 2 - 28, plate_y0 - 8, size // 2 + quote_max_w // 2 + 28, plate_y0 + block_h),
        radius=10,
        fill=(0, 0, 0, 120),
    )
    canvas = Image.alpha_composite(canvas, plate)
    draw = ImageDraw.Draw(canvas)
    qy = plate_y0 + 8
    for line in quote_lines:
        _draw_centered(draw, qy, line, font=quote_font, fill=SILVER)
        qy += line_step

    rgb = canvas.convert("RGB")
    temporary = output.with_suffix(output.suffix + ".tmp")
    try:
        rgb.save(temporary, format="JPEG", quality=93, optimize=True)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return output


# ------------------------------------------------------------------ сторис 9:16

STORY_WIDTH = 1080
STORY_HEIGHT = 1920
STORY_SAFE_TOP = 250
STORY_SAFE_BOTTOM = 250
STORY_BOT_HANDLE = "@Roxanaametist_Taro_bot"


SKY_BASE = (3, 3, 8)  # #030308 — как .bg-stars на сайте
# (файл, верх в долях высоты, ширина в долях ширины, левый край) — как .bg-cloud--* на сайте
_SKY_CLOUDS = (
    ("cloud-1.webp", 0.06, 0.40, 0.58),
    ("cloud-1.webp", 0.14, 0.27, -0.08),
    ("cloud-2.webp", 0.31, 0.48, 0.62),
    ("cloud-3.webp", 0.46, 0.36, -0.12),
    ("cloud-2.webp", 0.58, 0.32, 0.74),
    ("cloud-5.webp", 0.84, 0.40, 0.04),
)


def _sky_dir() -> Path | None:
    root = _project_root()
    for path in (
        root / "static" / "share" / "sky",
        Path("/root/tarolog/static/share/sky"),
    ):
        if (path / "star-lg.webp").exists():
            return path
    return None


def _radial(size: tuple[int, int], cx: float, cy: float, rx: float, ry: float, rgba: tuple) -> Image.Image:
    """Мягкое эллиптическое пятно (аналог radial-gradient ... transparent)."""
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((xx - cx * w) / (rx * w)) ** 2 + ((yy - cy * h) / (ry * h)) ** 2)
    a = np.clip(1.0 - d / 0.7, 0.0, 1.0) * rgba[3]
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = rgba[0], rgba[1], rgba[2]
    arr[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def sky_background(size: tuple[int, int] = (1080, 1920), *, seed: int = 0) -> Image.Image:
    """Фон «как на сайте»: тёмное небо, золотые звёздочки-спрайты, облака, лёгкое затемнение.

    Если картинок нет (например, на сервере их забыли залить) — просто тёмный фон.
    """
    import random

    w, h = size
    rnd = random.Random(seed)
    canvas = Image.new("RGBA", size, (*SKY_BASE, 255))
    canvas.alpha_composite(_radial(size, 0.5, 0.28, 0.55, 0.45, (90, 110, 160, 0.10)))
    canvas.alpha_composite(_radial(size, 0.2, 0.75, 0.50, 0.40, (40, 90, 120, 0.07)))
    sky = _sky_dir()
    if sky is None:
        return canvas

    # Звёзды: те же спрайты и разброс размеров, что в stars-bg.js (масштаб ×2.6 под 1080 px)
    k = w / 414.0
    sprites = []
    for name in ["star-lg", "star-sm"] + [f"star-{i}" for i in range(1, 11)]:
        try:
            with Image.open(sky / f"{name}.webp") as im:
                sprites.append(im.convert("RGBA"))
        except Exception:
            continue
    if sprites:
        for _ in range(95):
            idx = rnd.randrange(len(sprites))
            img = sprites[idx]
            px = rnd.uniform(10, 28)
            if idx == 0:
                px = rnd.uniform(22, 42)
            elif idx == 1:
                px = rnd.uniform(8, 16)
            side = max(4, int(px * k))
            star = ImageOps.contain(img, (side, side), Image.Resampling.LANCZOS)
            alpha = rnd.uniform(0.4, 0.95)
            if alpha < 1:
                star.putalpha(star.getchannel("A").point(lambda v, a=alpha: int(v * a)))
            canvas.alpha_composite(star, (rnd.randrange(0, w), rnd.randrange(0, h)))

    # Облака
    for name, top, width, left in _SKY_CLOUDS:
        try:
            with Image.open(sky / name) as im:
                cloud = im.convert("RGBA")
        except Exception:
            continue
        cw = int(width * w)
        cloud = cloud.resize((cw, max(1, int(cloud.height * cw / cloud.width))), Image.Resampling.LANCZOS)
        # paste с маской допускает выход за край (фон непрозрачный — результат как наложение)
        canvas.paste(cloud, (int(left * w), int(top * h)), cloud)

    # Затемнение для читаемости текста (как .bg-dim)
    grad = np.linspace(0.28, 0.55, h, dtype=np.float32)[:, None].repeat(w, axis=1)
    dim = np.zeros((h, w, 4), dtype=np.uint8)
    dim[..., 3] = (grad * 255).astype(np.uint8)
    canvas.alpha_composite(Image.fromarray(dim, "RGBA"))
    return canvas


def _font_covers(font: ImageFont.FreeTypeFont | ImageFont.ImageFont, text: str) -> bool:
    """True, если в шрифте есть глифы для всех букв (кириллица в Project Space может отсутствовать)."""
    try:
        notdef = font.getmask("\uffff").tobytes()
    except Exception:
        return True
    for ch in {c for c in str(text or "") if c.isalpha()}:
        try:
            if font.getmask(ch).tobytes() == notdef:
                return False
        except Exception:
            return False
    return True


def _story_centered(
    canvas: Image.Image,
    y: int,
    text: str,
    *,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: tuple[int, int, int] = INK,
    weight_x: int = 0,
) -> int:
    probe = ImageDraw.Draw(canvas)
    w = _text_width(probe, text, font)
    _draw_soft_glow_text(
        canvas,
        ((STORY_WIDTH - w) / 2, y),
        text,
        font=font,
        fill=fill,
        glow_alpha=60,
        blur_radius=2.0,
        weight_x=weight_x,
    )
    box = probe.textbbox((0, 0), text, font=font)
    return int(box[3] - box[1])


def generate_compat_story_card(
    output_path: str | Path,
    *,
    first_name: str,
    second_name: str,
    topic: str,
    card_paths: Iterable[str],
    phrase: str,
    bot_handle: str = STORY_BOT_HANDLE,
) -> Path:
    """Вертикальная карточка 1080×1920 для сторис «Совместимость».

    Всё значимое — между 250 px сверху и снизу (безопасная зона Instagram/Telegram).
    Существующую карточку 1080×1350 (generate_share_card) не трогает.
    """
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    paths = [Path(p) for p in card_paths if p][:3]
    import zlib

    seed = zlib.crc32(f"{first_name}|{second_name}|{output.stem}".encode("utf-8"))
    canvas = sky_background((STORY_WIDTH, STORY_HEIGHT), seed=seed)
    draw = ImageDraw.Draw(canvas)
    display_font = resolve_share_display_font()
    body_font = resolve_share_body_font()
    max_w = STORY_WIDTH - 2 * 110

    y = STORY_SAFE_TOP + 10
    # Ракушка + бренд
    logo_size = 96
    path = _shell_mark_path()
    if path is not None:
        try:
            with Image.open(path) as source:
                mark = ImageOps.contain(
                    source.convert("RGBA"), (logo_size, logo_size), Image.Resampling.LANCZOS
                )
            canvas.paste(mark, ((STORY_WIDTH - mark.width) // 2, y), mark)
            y += mark.height + 18
        except Exception:
            pass
    brand = "FOLLOW THE FRENSY"
    brand_font = _fit_font(draw, brand, display_font, max_width=620, start_size=40, min_size=18)
    y += _story_centered(canvas, y, brand, font=brand_font, fill=SILVER, weight_x=1) + 46

    # «Имя + Партнёр»
    names = f"{first_name} + {second_name}"
    names_font_path = display_font
    probe_font = _font(display_font, 80)
    if not _font_covers(probe_font, names):
        names_font_path = body_font
    names_max_w = STORY_WIDTH - 2 * 140
    names_font = _fit_font(draw, names, names_font_path, max_width=names_max_w, start_size=84, min_size=40)
    nb = draw.textbbox((0, 0), names, font=names_font)
    if nb[2] - nb[0] <= names_max_w:
        y += _story_centered(canvas, y, names, font=names_font, weight_x=1) + 30
    else:
        # длинные имена — в две строки: «Имя +» / «Партнёр»
        lines = [f"{first_name} +", str(second_name)]

        def _lines_font(path):
            return min(
                (_fit_font(draw, ln, path, max_width=names_max_w, start_size=72, min_size=28) for ln in lines),
                key=lambda f: f.size,
            )

        def _fits(f):
            return all(draw.textbbox((0, 0), ln, font=f)[2] - draw.textbbox((0, 0), ln, font=f)[0] <= names_max_w for ln in lines)

        line_font = _lines_font(names_font_path)
        if not _fits(line_font) and names_font_path != body_font:
            # широкий фирменный шрифт не влез даже мелко — узкий Cormorant
            line_font = _lines_font(body_font)
        if not _fits(line_font):
            line_font = min(
                (_fit_font(draw, ln, body_font, max_width=names_max_w, start_size=56, min_size=16) for ln in lines),
                key=lambda f: f.size,
            )
        for ln in lines:
            y += _story_centered(canvas, y, ln, font=line_font, weight_x=1) + 30

    # Тема
    topic_text = f"СОВМЕСТИМОСТЬ · {str(topic or '').upper()}".strip(" ·")
    topic_font_path = display_font if _font_covers(_font(display_font, 30), topic_text) else body_font
    topic_font = _fit_font(draw, topic_text, topic_font_path, max_width=max_w, start_size=32, min_size=18)
    y += _story_centered(canvas, y, topic_text, font=topic_font, fill=MUTED) + 54

    # 3 карты
    count = 3
    gap = 30
    card_w = (STORY_WIDTH - 2 * 105 - gap * (count - 1)) // count
    card_h = int(round(card_w / TAROT_CARD_RATIO))
    x = (STORY_WIDTH - (card_w * count + gap * (count - 1))) // 2
    for index in range(count):
        box = (x, y, x + card_w, y + card_h)
        image = _card_crop(paths[index], (card_w, card_h)) if index < len(paths) else None
        if image is not None:
            _card_paste(canvas, image, box)
        else:
            draw.rectangle(box, fill=CARD_SLOT, outline=SILVER, width=2)
        x += card_w + gap
    y += card_h + 26

    # Херувимы с драпировкой и фраза на ткани
    handle_font = _fit_font(draw, bot_handle, body_font, max_width=max_w, start_size=40, min_size=24)
    handle_h = int(getattr(handle_font, "size", 36) * 1.3)
    bottom_limit = STORY_HEIGHT - STORY_SAFE_BOTTOM - handle_h - 24
    strip = _load_angels_holding_drapery(STORY_WIDTH - 2 * 70)
    quote = " ".join(str(phrase or "").split())
    if strip is not None and bottom_limit - y > 200:
        max_h = bottom_limit - y
        if strip.height > max_h:
            scale = max_h / strip.height
            strip = strip.resize(
                (max(1, int(strip.width * scale)), max_h), Image.Resampling.LANCZOS
            )
        strip_w, strip_h = strip.size
        strip_x = (STORY_WIDTH - strip_w) // 2
        canvas.paste(strip, (strip_x, y), strip)
        quote_max_w = max(260, int(strip_w * 0.37))
        quote_area_h = max(72, int(strip_h * 0.28))
        quote_font = _font(body_font, 24)
        quote_lines: list[str] = []
        line_step = 30
        for size in range(28, 13, -1):
            quote_font = _font(body_font, size)
            line_step = max(18, size + 6)
            max_lines = max(2, quote_area_h // line_step)
            quote_lines = _wrap(draw, quote, quote_font, quote_max_w, max_lines)
            if len(quote_lines) * line_step <= quote_area_h and (
                not quote_lines or not quote_lines[-1].endswith("…")
            ):
                break
        _paste_quote_on_drapery(
            canvas,
            strip=strip,
            strip_x=strip_x,
            strip_y=y,
            strip_w=strip_w,
            strip_h=strip_h,
            lines=quote_lines,
            font=quote_font,
            line_step=line_step,
        )
    elif quote:
        qf = _font(body_font, 34)
        for line in _wrap(draw, quote, qf, max_w, 3):
            y += _story_centered(canvas, y, line, font=qf) + 12

    # Ник бота — нижний край безопасной зоны
    _story_centered(
        canvas,
        STORY_HEIGHT - STORY_SAFE_BOTTOM - handle_h,
        bot_handle,
        font=handle_font,
        fill=SILVER,
    )

    rgb = canvas.convert("RGB")
    temporary = output.with_suffix(output.suffix + ".tmp")
    try:
        rgb.save(temporary, format="JPEG", quality=92, optimize=True)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return output
