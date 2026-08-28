"""Capture real UI screenshots and build portfolio demo GIFs."""
from __future__ import annotations

import asyncio
from pathlib import Path

from PIL import Image
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
TMP = ROOT / "scripts" / "_capture_tmp"
TMP.mkdir(parents=True, exist_ok=True)


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
    frames: list[Path] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1360, "height": 820})
        await page.goto("http://127.0.0.1:8765/", wait_until="networkidle", timeout=120_000)
        await page.wait_for_timeout(4000)
        board = TMP / "nfl-board.png"
        await page.screenshot(path=str(board), full_page=False)
        frames.append(board)

        for label, selector in [
            ("injuries", "text=Injuries"),
            ("injury", "text=Injury"),
            ("settings", "text=Settings"),
            ("leaderboard", "text=Leaderboard"),
        ]:
            try:
                loc = page.locator(selector).first
                if await loc.count() > 0:
                    await loc.click(timeout=5000)
                    await page.wait_for_timeout(2000)
                    shot = TMP / f"nfl-{label}.png"
                    await page.screenshot(path=str(shot), full_page=False)
                    if shot not in frames:
                        frames.append(shot)
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


async def main() -> None:
    ASSETS.mkdir(exist_ok=True)

    wmg_frames = await capture_wmgoldmine()
    pngs_to_gif(wmg_frames[:4], ASSETS / "wmgoldmine-demo.gif")

    nfl_frames = await capture_nfl()
    pngs_to_gif(nfl_frames[:4], ASSETS / "nfl-demo.gif")

    build_wmnavigation_gif()

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
    asyncio.run(main())
