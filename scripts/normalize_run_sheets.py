"""Normalize /run FolAI sheets: ONE scale per sheet (no per-frame resize)."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SHEETS = ROOT / "landing" / "static" / "images" / "run" / "sheets"

FRAME = 512
CHAR_H = 420
FEET_PAD = 28
FRAMES = 4

NAMES = [
    "angel-fly.png",
    "imp-jump-a.png",
    "imp-jump-b.png",
    "imp-jump-c.png",
    "cherub-fly.png",
    "cherub-stand.png",
    "cherub-back.png",
    "demon-stab.png",
]


def punch(im: Image.Image) -> Image.Image:
    im = im.convert("RGBA")
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if r < 28 and g < 28 and b < 28:
                px[x, y] = (r, g, b, 0)
            elif r < 45 and g < 45 and b < 45:
                px[x, y] = (r, g, b, int(a * ((max(r, g, b) - 18) / 27)))
    return im


def normalize_sheet(path: Path) -> None:
    im = Image.open(path).convert("RGBA")
    fw = im.width // FRAMES
    fh = im.height
    raw = [punch(im.crop((i * fw, 0, (i + 1) * fw, fh))) for i in range(FRAMES)]
    boxes = [fr.getbbox() for fr in raw]
    if not any(boxes):
        raise SystemExit(f"empty sheet {path.name}")

    # One scale for the whole clip: tallest silhouette → CHAR_H
    max_h = max((b[3] - b[1]) for b in boxes if b)
    max_w = max((b[2] - b[0]) for b in boxes if b)
    scale = CHAR_H / max_h
    if max_w * scale > FRAME - 8:
        scale = (FRAME - 8) / max_w

    out = Image.new("RGBA", (FRAME * FRAMES, FRAME), (0, 0, 0, 0))
    heights = []
    for i, fr in enumerate(raw):
        box = boxes[i]
        cell = Image.new("RGBA", (FRAME, FRAME), (0, 0, 0, 0))
        if box:
            crop = fr.crop(box)
            nw = max(1, int(round(crop.width * scale)))
            nh = max(1, int(round(crop.height * scale)))
            crop = crop.resize((nw, nh), Image.Resampling.LANCZOS)
            x = (FRAME - nw) // 2
            y = FRAME - FEET_PAD - nh
            cell.paste(crop, (x, y), crop)
            heights.append(nh)
        else:
            heights.append(0)
        out.paste(cell, (i * FRAME, 0), cell)

    out.save(path, optimize=True)
    print(
        path.name,
        f"{out.size[0]}x{out.size[1]}",
        f"scale={scale:.3f}",
        f"h={heights}",
    )


def main() -> None:
    for name in NAMES:
        path = SHEETS / name
        if not path.is_file():
            raise SystemExit(f"missing {path}")
        normalize_sheet(path)


if __name__ == "__main__":
    main()
