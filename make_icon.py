"""Generates icon.ico, icon.png and icon.svg for FileFlow. Run: python make_icon.py (needs Pillow)."""
from PIL import Image, ImageDraw

S = 1024
TILE = "#1F6F6B"     # app accent
BACK = "#86C4BE"     # back panel of the folder
FRONT = "#F2F8F7"    # front panel
SHEET = "#FFFFFF"    # the document
FOLD = "#C4E2DE"     # folded corner


def draw_master():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, S - 1, S - 1), radius=224, fill=TILE)

    # folder back panel and tab
    d.rounded_rectangle((176, 256, 452, 400), radius=40, fill=BACK)
    d.rounded_rectangle((176, 304, 848, 800), radius=48, fill=BACK)

    # document with a folded corner
    d.polygon([(344, 200), (608, 200), (704, 296), (704, 640), (320, 640), (320, 224)], fill=SHEET)
    d.rounded_rectangle((320, 200, 380, 260), radius=24, fill=SHEET)
    d.rounded_rectangle((320, 590, 704, 640), radius=12, fill=SHEET)
    d.polygon([(608, 200), (608, 296), (704, 296)], fill=FOLD)
    for y, width in ((336, 260), (408, 200), (480, 140)):
        d.rounded_rectangle((380, y, 380 + width, y + 30), radius=15, fill=TILE)

    # front panel, separated from the document by a gap in the tile colour
    d.rounded_rectangle((164, 548, 860, 812), radius=60, fill=TILE)
    d.rounded_rectangle((176, 560, 848, 800), radius=48, fill=FRONT)
    return img


SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024" width="512" height="512">
  <rect width="1024" height="1024" rx="224" fill="{TILE}"/>
  <rect x="176" y="256" width="276" height="144" rx="40" fill="{BACK}"/>
  <rect x="176" y="304" width="672" height="496" rx="48" fill="{BACK}"/>
  <path d="M344 200H608L704 296V616a24 24 0 0 1-24 24H344a24 24 0 0 1-24-24V224a24 24 0 0 1 24-24Z" fill="{SHEET}"/>
  <path d="M608 200V296H704Z" fill="{FOLD}"/>
  <rect x="380" y="336" width="260" height="30" rx="15" fill="{TILE}"/>
  <rect x="380" y="408" width="200" height="30" rx="15" fill="{TILE}"/>
  <rect x="380" y="480" width="140" height="30" rx="15" fill="{TILE}"/>
  <rect x="164" y="548" width="696" height="264" rx="60" fill="{TILE}"/>
  <rect x="176" y="560" width="672" height="240" rx="48" fill="{FRONT}"/>
</svg>
"""

if __name__ == "__main__":
    master = draw_master()
    master.resize((512, 512), Image.LANCZOS).save("icon.png")
    master.save("icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    with open("icon.svg", "w", encoding="utf-8") as handle:
        handle.write(SVG)
    print("Wrote icon.ico, icon.png, icon.svg")
