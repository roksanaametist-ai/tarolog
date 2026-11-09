# Frensy Run (`/run`) — brief for Claude

Goal: make the easter-egg runner **lighter, prettier, better** while keeping the angel→demon fantasy and Frensy brand.

Local preview: `http://127.0.0.1:5000/run`  
Repo: `C:\Users\roxan\Projects\TarGPT3` (currently often on `main`; game files may be restored from `feature/reading-topics-day` / checkpoint `8628c2b`).

---

## Product / fantasy

Chrome-dino-style **2D canvas runner**, matte black + silver Frensy aesthetic, marble sticker characters (white cherubs / crimson imps, gold accents).

### Phase 1 — Angel (player left)
- Hold **Space / click / touch** to **fly up** (not jump).
- Score **counts up** while alive.
- Obstacles: **3 red imp jump variants** come from the right.
- First hit → transform into demon (invulnerability flash).

### Phase 2 — Demon (player right)
- Grounded runner facing left; world scrolls the other way.
- Score **counts down**; hit 0 → game over.
- Obstacles: **3 cherubs with gold hearts** (fly / stand / back-to-demon).
- Click = **trident stab** hitbox that removes cherubs.
- Second hit (or score 0) → game over (“пауза судьбы”).

### Meta
- Pause: button / **P** / **Esc**
- High score in `localStorage` key `frensy-run-hi`
- `noindex`, intended as footer easter egg (“Ходилка”), `robots` Disallow `/run`
- Not a product surface — keep playful, short, brand-aligned

---

## Tech stack

| Piece | Path |
|--------|------|
| Flask route | `landing/SiteApp.py` → `@app.route("/run")` → `run.html` |
| Page | `landing/templates/run.html` |
| CSS | `landing/static/css/run.css` (+ `main.css` brand tokens) |
| Game logic | `landing/static/js/run.js` (~540 lines, vanilla JS, no libs) |
| Sprites | `landing/static/images/run/sheets/*.png` (4-frame horizontal strips) |
| FolAI source mp4 | `_folai/run-clip-*.mp4` (8 Kling I2V clips) |
| Prompts | `_folai/run_prompts.json`, `_folai/run_trio.json` |
| Pipeline | `scripts/folai_run_*.py`, `scripts/normalize_run_sheets.py` |

Canvas logical size: **1600×640**, CSS max-width **1280px**, DPR capped at 2.

Sprite draw size: `SPRITE_W=102`, `SPRITE_H=128` for everyone.

---

## Assets (what exists)

### In-game FolAI sheets (used by `run.js`) — ~4.4 MB total
| File | Role |
|------|------|
| `sheets/angel-fly.png` | Player phase 1 |
| `sheets/imp-jump-{a,b,c}.png` | Obstacles phase 1 |
| `sheets/cherub-{fly,stand,back}.png` | Obstacles phase 2 |
| `sheets/demon-stab.png` | Player phase 2 |
| `sheets/cherub-hover.png` | **legacy, unused** (~1 MB) — safe to delete |

Each sheet: **4 frames**, normalized to **512×512** cells, feet-aligned, **one shared scale per sheet** (do not re-scale frames independently — that caused size “breathing”).

### Extra / unused weight (candidates to drop from deploy)
- `run/angel-fly.png`, `imp-stand.png`, `cherub-stand.png`, `demon-trident.png` — early stills
- `run/obstacles/*.png` — stills when JS used bob instead of sheets
- `run/run-sheet-*-trio.png` — design composites
- `_folai/run-clip-*.mp4` (~48 MB) — source only, **do not ship to prod**

### FolAI clips (source of truth for motion)
1. angel fly  
2–4. imp jump A / B / C (different jump styles)  
5–7. cherub fly / stand / back (with heart)  
8. demon stab  

Art lock: Telegram sticker, marble sculpture on `#050505`, locked camera, tiny gold stars. See `_folai/run_prompts.json`.

---

## Current gameplay numbers (from `run.js`)

- Angel spawn X ≈ 110; demon X ≈ `W - 168`
- Ground `H - 72`; ceiling 36
- Speed starts ~7.4 (5.2 if reduced motion), ramps to max ~13.5
- Spawn interval ~70–134 ticks
- Angel physics: hold = lift, gravity, clamp vy
- Demon: gravity, ground, stab window 18 ticks, reach ~90–130px left
- Invuln after transform: 55 ticks + flash
- Score = `floor(scoreTicks / 5)` (up in angel, down in demon)
- Collision: naive AABB on full sprite boxes (generous / floaty)

---

## Known problems / debt

1. **Heavy**: ~4+ MB sheets on a tiny easter egg; `cherub-hover` unused; many unused PNGs.
2. **Looks sparse**: flat `#050505` canvas, single ground line + tick marks — not “pretty”.
3. **Feel**: AABB + large sprites = unfair hits; angel flight can feel floaty; demon phase only horizontal.
4. **Scale history**: per-frame normalize made characters breathe — fixed with shared scale; keep that rule.
5. **Cross-character scale**: different sheets still have different body sizes vs each other (imps vs cherubs) — only intra-clip scale is locked.
6. **Deploy**: on `main` the game was missing until restored; footer link / robots Disallow may be absent on current `main` index — wire carefully as easter egg.
7. **No sound**, no particles, no parallax, no juice on transform/stab/death.
8. **Mobile**: canvas scales CSS-wide; touch works via click handlers but HUD/chrome not tuned as a polished mobile game.

---

## Brand / design constraints (Frensy)

- Site: Follow the Frensy — Roxana Amethyst, matte black, silver/ink text, restrained luxury (not purple-glow AI sludge).
- Fonts on page: Cormorant + site UI stack from `main.css`.
- Characters: marble putti / crimson marble imps — sticker pack language already established on landing/jelly.
- Keep **noindex** and easter-egg energy; don’t turn into a marketed mini-game hub.
- Prefer one composition, little chrome clutter.

---

## What “lighter / prettier / better” should mean

### Lighter
- Ship only the **8** active sheets; delete or exclude unused PNG/mp4 from deploy.
- Re-export sheets smaller: e.g. **256×256** cells or WebP/AVIF; strip to ~1–1.5 MB total.
- Optional: 2–3 frames if motion still reads; or atlas packing.
- Lazy-load sheets; don’t block first paint on all 8.

### Prettier
- Atmosphere: subtle gradient/stars/parallax dust matching marble stickers (not busy dashboard).
- HUD: quieter typography, brand-first kicker already exists — refine spacing.
- Juice: transform flash with silver/crimson, stab trail, soft screen shake (respect `prefers-reduced-motion`).
- Ground/horizon less “programmer line”.
- Pause / game-over as elegant Frensy overlay, not raw boxes.

### Better (feel)
- Tighter hitboxes (inset AABB or circle on torso).
- Clearer tutorial beat (first 2s).
- Demon phase: slightly more readable cherub variants; stab feedback.
- Difficulty curve: spawn gaps vs speed tuned so average player reaches demon with a peak score.
- Keep core loop: fly → hit → become demon → stab / survive countdown.

---

## Files Claude should touch first

1. `landing/static/js/run.js` — feel, hitboxes, juice, loading  
2. `landing/static/css/run.css` + `run.html` — chrome / polish  
3. Asset pipeline / export sizes under `landing/static/images/run/sheets/`  
4. `landing/SiteApp.py` — keep `/run` route; optional feature flag `LANDING_RUN_GAME` existed on feature branch  
5. Footer easter egg on `index.html` only if deliberate  

Do **not** regenerate FolAI videos unless art is wrong; prefer reprocessing existing mp4 → smaller sheets.

---

## How to regenerate sheets (if needed)

```powershell
# FAL_KEY lives in OneDrive Desktop TarGPT3\.env (not always in Projects\.env)
# Throne VPN proxy required for fal.ai on this PC: scripts/throne.ps1
python scripts/folai_run_extract.py --all   # mp4 → raw 4-frame sheets (cv2 ok)
python scripts/normalize_run_sheets.py      # ONE scale per sheet, feet align
# bump ASSET_V in run.js + ?v= on script in run.html
```

Normalize rule: **never** scale each frame to the same height independently.

---

## Acceptance checklist

- [ ] Load under ~1.5–2 MB for `/run` static (sheets+css+js) ideally  
- [ ] Angel flight + demon stab still readable on phone  
- [ ] No scale pulsing inside a clip  
- [ ] Hitboxes feel fair  
- [ ] Visual polish matches Frensy black/silver, not generic game UI  
- [ ] Reduced-motion path still playable  
- [ ] `noindex` + easter-egg access preserved  
- [ ] Unused assets removed from ship path  

---

## One-sentence pitch for Claude

> Refactor Frensy’s `/run` canvas easter-egg into a lighter, fairer, more beautiful angel→demon marble-sticker runner: keep the loop and FolAI art, cut weight, tighten feel, and polish chrome to match the matte-black Frensy landing.
