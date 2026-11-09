"""Extract 4 frames from FolAI run mp4 clips into horizontal sprite sheets."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLAI = ROOT / "_folai"
PACK = FOLAI / "run_prompts.json"
OUT = ROOT / "landing" / "static" / "images" / "run" / "sheets"
FRAMES = 4


def pack() -> dict:
    return json.loads(PACK.read_text(encoding="utf-8"))


def have_ffmpeg() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def extract_sheet_cv2(mp4: Path, sheet: Path) -> None:
    import cv2
    from PIL import Image

    cap = cv2.VideoCapture(str(mp4))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if total < FRAMES:
        cap.release()
        sys.exit(f"too few frames in {mp4}: {total}")
    idxs = [int(i * (total - 1) / (FRAMES - 1)) for i in range(FRAMES)]
    parts: list[Image.Image] = []
    for idx in idxs:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if not ok:
            cap.release()
            sys.exit(f"read fail {mp4} frame {idx}")
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        parts.append(Image.fromarray(rgb).convert("RGBA"))
    cap.release()
    fw = parts[0].size[0]
    fh = max(im.size[1] for im in parts)
    sheet_im = Image.new("RGBA", (fw * FRAMES, fh), (0, 0, 0, 0))
    for i, im in enumerate(parts):
        sheet_im.paste(im, (i * fw, 0))
    px = sheet_im.load()
    w, h = sheet_im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if r < 28 and g < 28 and b < 28:
                px[x, y] = (r, g, b, 0)
    sheet_im.save(sheet)
    print("sheet", sheet.name, sheet_im.size, "(cv2)")


def extract_sheet(mp4: Path, sheet: Path) -> None:
    if have_ffmpeg():
        extract_sheet_ffmpeg(mp4, sheet)
    else:
        extract_sheet_cv2(mp4, sheet)


def extract_sheet_ffmpeg(mp4: Path, sheet: Path) -> None:
    tmp = sheet.parent / ("_tmp_" + sheet.stem)
    tmp.mkdir(parents=True, exist_ok=True)
    pattern = str(tmp / "f%02d.png")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(mp4),
            "-vf",
            f"select='not(mod(n\\,{max(1, 30 // FRAMES)}))',scale=384:-1",
            "-frames:v",
            str(FRAMES),
            pattern,
        ],
        check=True,
        capture_output=True,
    )
    from PIL import Image

    parts = sorted(tmp.glob("f*.png"))[:FRAMES]
    if len(parts) < FRAMES:
        sys.exit(f"only {len(parts)} frames from {mp4}")
    fw = parts[0].size[0]
    fh = max(im.size[1] for im in (Image.open(p) for p in parts))
    sheet_im = Image.new("RGBA", (fw * FRAMES, fh), (0, 0, 0, 0))
    for i, p in enumerate(parts):
        im = Image.open(p).convert("RGBA")
        sheet_im.paste(im, (i * fw, 0))
    px = sheet_im.load()
    w, h = sheet_im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if r < 28 and g < 28 and b < 28:
                px[x, y] = (r, g, b, 0)
    sheet_im.save(sheet)
    for p in parts:
        p.unlink(missing_ok=True)
    tmp.rmdir()
    print("sheet", sheet.name, sheet_im.size)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clip", action="append", default=[])
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    wanted = None if args.all else set(args.clip) if args.clip else None
    for clip in pack()["clips"]:
        if wanted is not None and clip["id"] not in wanted:
            continue
        mp4 = FOLAI / clip["file"]
        if not mp4.is_file():
            print("skip", clip["id"], "no", mp4.name)
            continue
        extract_sheet(mp4, OUT / clip["sheet"])


if __name__ == "__main__":
    main()
