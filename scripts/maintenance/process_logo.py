from pathlib import Path

from PIL import Image


def main():
    src = Path(
        "/Users/regie-302004/.cursor/projects/Users-regie-302004-Desktop-ElisSystem/assets/360125293_743536974446320_4974790108264961455_n__1_-a1cb8fbc-2c08-4611-a3f7-09b6ca092880.png"
    )
    dst = Path("app/static/img/elis-mark.png")
    dst.parent.mkdir(parents=True, exist_ok=True)

    img = Image.open(src).convert("RGBA")

    # Crop only the building mark (remove the text)
    w, h = img.size
    # The source is 120x120; keep only the top mark area (avoid any text below).
    crop_bottom = 66 if h >= 120 else int(h * 0.55)
    crop = img.crop((0, 0, w, crop_bottom)).convert("RGBA")

    # Remove white background -> transparent (works well on dark UI)
    px = crop.load()
    cw, ch = crop.size
    for y in range(ch):
        for x in range(cw):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            if r > 245 and g > 245 and b > 245:
                px[x, y] = (r, g, b, 0)

    # Tight-crop to non-transparent content
    bbox = crop.getbbox()
    if bbox:
        crop = crop.crop(bbox)
        # Remove leftover baseline pixels near the bottom (from original logo text).
        px2 = crop.load()
        cw2, ch2 = crop.size
        for y in range(max(0, ch2 - 14), ch2):
            for x in range(cw2):
                r, g, b, a = px2[x, y]
                if a > 0 and r < 60 and g < 60 and b < 60:
                    px2[x, y] = (r, g, b, 0)

    # Add transparent padding and scale for crisp nav display
    pad = 18
    out = Image.new("RGBA", (crop.size[0] + pad * 2, crop.size[1] + pad * 2), (0, 0, 0, 0))
    out.paste(crop, (pad, pad), crop)
    out = out.resize((256, 256), Image.LANCZOS)

    out.save(dst)
    print(f"Saved: {dst}")


if __name__ == "__main__":
    main()

