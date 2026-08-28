"""Capture real UI screenshots and build portfolio demo GIFs."""
from __future__ import annotations

import argparse
import asyncio
import json
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
TMP = ROOT / "scripts" / "_capture_tmp"
TMP.mkdir(parents=True, exist_ok=True)


NFL_URL = "http://127.0.0.1:8765/"
NFL_CAPTURE_USERNAME = "capture-demo"
NFL_SESSION_CACHE = TMP / "nfl-session.json"
NFL_FALLBACK_KEYS = (
    "WMN-NGDB-HJ4N-K7YT-SA75-XUAW",
    "WMN-W6PV-AR69-L94N-S2QM-6F97",
    "WMN-VY65-BS4X-SCE2-S2SA-88LN",
    "WMN-ZDQL-3ZUS-2TTC-MQT7-ZSGU",
)


def _nfl_post(path: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{NFL_URL.rstrip('/')}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_nfl_session_token() -> str:
    if NFL_SESSION_CACHE.exists():
        cached = json.loads(NFL_SESSION_CACHE.read_text(encoding="utf-8"))
        token = cached.get("token")
        if token:
            validated = _nfl_post("/api/auth/validate", {"token": token})
            if validated.get("ok"):
                return str(token)

    last_error = "NFL activation failed"
    for key in NFL_FALLBACK_KEYS:
        data = _nfl_post(
            "/api/auth/activate",
            {"username": NFL_CAPTURE_USERNAME, "activation_key": key},
        )
        if data.get("ok") and data.get("token"):
            NFL_SESSION_CACHE.write_text(
                json.dumps({"token": data["token"], "username": NFL_CAPTURE_USERNAME}),
                encoding="utf-8",
            )
            return str(data["token"])
        last_error = data.get("error") or last_error

    raise RuntimeError(last_error)


def crop_portfolio_frame(src: Path, dest: Path) -> Path:
    """Tight crop on app UI; hide Whiskey Mike's chair branding in header/background."""
    img = Image.open(src).convert("RGB")
    w, h = img.size
    # Trim outer chrome; keep nav + main content below compact header row.
    left = max(0, int(w * 0.01))
    top = max(0, int(h * 0.055))
    right = min(w, int(w * 0.995))
    bottom = min(h, int(h * 0.985))
    cropped = img.crop((left, top, right, bottom))
    cropped.save(dest)
    return dest


def pngs_to_gif(png_paths: list[Path], out_path: Path, duration_ms: int = 900) -> None:
    frames = [Image.open(p).convert("RGB") for p in png_paths if p.exists()]
    if not frames:
        raise FileNotFoundError(f"No frames for {out_path}")
    w, h = frames[0].size
    resized = []
    for frame in frames:
        if frame.size != (w, h):
            frame = frame.resize((w, h), Image.Resampling.LANCZOS)
        resized.append(frame)
    resized[0].save(
        out_path,
        save_all=True,
        append_images=resized[1:],
        duration=duration_ms,
        loop=0,
        optimize=True,
    )
    print(f"Wrote {out_path} ({len(resized)} frames)")


async def capture_url(name: str, url: str, out_png: Path, width: int = 1280, height: int = 720) -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": width, "height": height})
        await page.goto(url, wait_until="networkidle", timeout=120_000)
        await page.wait_for_timeout(2500)
        await page.screenshot(path=str(out_png), full_page=False)
        await browser.close()
    print(f"Captured {name} -> {out_png}")


async def capture_wmgoldmine() -> list[Path]:
    frames: list[Path] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1360, "height": 820})
        await page.goto("http://127.0.0.1:8787/", wait_until="networkidle", timeout=120_000)
        await page.wait_for_timeout(3000)
        dash = TMP / "wmgoldmine-dashboard.png"
        await page.screenshot(path=str(dash), full_page=False)
        frames.append(dash)

        for label, selector in [
            ("challenge", "text=Challenge"),
            ("connect", "text=Connect"),
            ("signal", "text=Signal"),
        ]:
            try:
                loc = page.locator(selector).first
                if await loc.count() > 0:
                    await loc.click(timeout=5000)
                    await page.wait_for_timeout(1500)
                    shot = TMP / f"wmgoldmine-{label}.png"
                    await page.screenshot(path=str(shot), full_page=False)
                    frames.append(shot)
            except Exception as exc:
                print(f"WMGOLDMINE tab {label} skip: {exc}")

        await browser.close()
    return frames


async def capture_nfl() -> list[Path]:
    token = fetch_nfl_session_token()
    frames: list[Path] = []
    tab_targets = [
        ("board", "Weekly Board"),
        ("injuries", "Injuries"),
        ("game-lab", "Game Lab"),
        ("props", "Player Props"),
        ("leaderboard", "Leaderboard"),
    ]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1360, "height": 820})
        await context.add_init_script(
            f"""
            localStorage.setItem('elite_session_token', {json.dumps(token)});
            localStorage.setItem('elite_username', {json.dumps(NFL_CAPTURE_USERNAME)});
            """
        )
        page = await context.new_page()
        await page.goto(NFL_URL, wait_until="networkidle", timeout=120_000)
        await page.wait_for_selector(".app-shell", timeout=60_000)
        await page.add_style_tag(
            content="""
            .brand-mark { display: none !important; }
            .activation-gate { background-image: none !important; }
            """
        )
        await page.wait_for_timeout(3500)

        nav = page.locator("nav.app-nav")
        for label, tab_label in tab_targets:
            try:
                btn = nav.get_by_role("button", name=tab_label, exact=True)
                await btn.click(timeout=8000)
                await page.wait_for_timeout(2200)
                raw = TMP / f"nfl-{label}-raw.png"
                cropped = TMP / f"nfl-{label}.png"
                await page.locator(".app-shell").screenshot(path=str(raw))
                crop_portfolio_frame(raw, cropped)
                frames.append(cropped)
                print(f"Captured NFL {label} -> {cropped}")
            except Exception as exc:
                print(f"NFL tab {label} skip: {exc}")

        await browser.close()
    return frames


def build_wmnavigation_gif() -> None:
    """Use real WMNavigation project imagery (splash + map concept)."""
    src_splash = Path(r"C:\Users\mikej\OneDrive\Desktop\WMNavigation\assets\splash.png")
    src_map = Path(r"C:\Users\mikej\OneDrive\Desktop\WMNavigation_satellite_map_concept.png")
    src_banner = Path(r"C:\Users\mikej\OneDrive\Desktop\WMNavigation\assets\brand_banner.png")
    frames: list[Path] = []
    for src in (src_splash, src_map, src_banner):
        if src.exists():
            out = TMP / f"wmnav-{src.stem}.png"
            img = Image.open(src).convert("RGB")
            img.thumbnail((1280, 720), Image.Resampling.LANCZOS)
            canvas = Image.new("RGB", (1280, 720), (10, 10, 10))
            ox = (1280 - img.width) // 2
            oy = (720 - img.height) // 2
            canvas.paste(img, (ox, oy))
            canvas.save(out)
            frames.append(out)
    if not frames:
        raise FileNotFoundError("No WMNavigation source images found")
    pngs_to_gif(frames, ASSETS / "wmnavigation-demo.gif", duration_ms=1200)


async def main(only: str | None = None) -> None:
    ASSETS.mkdir(exist_ok=True)

    if only in (None, "wmgoldmine"):
        wmg_frames = await capture_wmgoldmine()
        pngs_to_gif(wmg_frames[:4], ASSETS / "wmgoldmine-demo.gif")

    if only in (None, "nfl"):
        nfl_frames = await capture_nfl()
        if not nfl_frames:
            raise RuntimeError("No NFL frames captured")
        pngs_to_gif(nfl_frames[:5], ASSETS / "nfl-demo.gif", duration_ms=900)

    if only in (None, "wmnavigation"):
        build_wmnavigation_gif()

    if only is None:
        # WMMods GIF already in repo from prior capture
        wmmods = ASSETS / "wmmods-demo.gif"
        if not wmmods.exists():
            alt = Path(r"C:\Users\mikej\OneDrive\Desktop\Mike-Schartner-Portfolio-main\assets\wmmods-demo.gif")
            if alt.exists():
                wmmods.write_bytes(alt.read_bytes())

    print("Done. Assets:")
    for name in ("nfl-demo.gif", "wmgoldmine-demo.gif", "wmmods-demo.gif", "wmnavigation-demo.gif"):
        p = ASSETS / name
        print(f"  {p}: {p.stat().st_size if p.exists() else 'MISSING'} bytes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Capture portfolio demo GIFs from live apps")
    parser.add_argument(
        "--only",
        choices=("nfl", "wmgoldmine", "wmnavigation"),
        help="Capture a single demo instead of all",
    )
    args = parser.parse_args()
    asyncio.run(main(only=args.only))
