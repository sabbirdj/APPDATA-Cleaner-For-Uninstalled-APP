"""
Generates high-resolution application icons for AppData Orphan Cleaner:
- assets/app_icon.png (256x256 high-DPI)
- assets/app_icon.ico (multi-resolution: 16x16, 24x24, 32x32, 48x48, 64x64, 128x128, 256x256)
"""

import os
import math
from PIL import Image, ImageDraw, ImageFilter

def create_app_icon(output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    png_path = os.path.join(output_dir, "app_icon.png")
    ico_path = os.path.join(output_dir, "app_icon.ico")

    # High-resolution canvas
    size = 512
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    # 1. Outer subtle drop shadow
    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(shadow)
    s_draw.rounded_rectangle([36, 40, size - 36, size - 32], radius=110, fill=(0, 0, 0, 90))
    shadow = shadow.filter(ImageFilter.GaussianBlur(16))
    img.paste(shadow, (0, 0), shadow)

    # 2. Main rounded squircle container with Windows 11 Fluent gradient
    # Gradient from #005A9E (Fluent Blue) to #00B4D8 (Electric Cyan)
    base_rect = [40, 36, size - 40, size - 44]
    radius = 100

    mask = Image.new("L", (size, size), 0)
    m_draw = ImageDraw.Draw(mask)
    m_draw.rounded_rectangle(base_rect, radius=radius, fill=255)

    gradient = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    g_draw = ImageDraw.Draw(gradient)
    for y in range(size):
        ratio = y / size
        r = int(0 * (1 - ratio) + 0 * ratio)
        g = int(90 * (1 - ratio) + 180 * ratio)
        b = int(170 * (1 - ratio) + 225 * ratio)
        g_draw.line([(0, y), (size, y)], fill=(r, g, b, 255))

    img.paste(gradient, (0, 0), mask)

    # 3. Inner border highlight (Fluent light reflection)
    highlight = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    h_draw = ImageDraw.Draw(highlight)
    h_draw.rounded_rectangle(base_rect, radius=radius, outline=(255, 255, 255, 75), width=3)
    img = Image.alpha_composite(img, highlight)

    # 4. Folder Glyph Silhouette in center
    draw = ImageDraw.Draw(img)
    # Folder tab
    draw.rounded_rectangle([130, 160, 240, 200], radius=12, fill=(255, 255, 255, 230))
    # Folder main body
    draw.rounded_rectangle([130, 185, 382, 350], radius=24, fill=(255, 255, 255, 245))

    # Inner folder pocket accent (slight darker contrast inside folder)
    draw.rounded_rectangle([150, 215, 362, 330], radius=16, fill=(225, 238, 252, 255))

    # 5. Magic Sparkle / Broom Cleaner Emblem (Cyan / Emerald Glow)
    # Sparkle 1 (Large 4-pointed star)
    cx, cy = 295, 245
    r_outer, r_inner = 52, 16
    points = []
    for i in range(8):
        angle = i * (math.pi / 4)
        r = r_outer if (i % 2 == 0) else r_inner
        px = cx + r * math.cos(angle)
        py = cy + r * math.sin(angle)
        points.append((px, py))
    draw.polygon(points, fill=(14, 165, 233, 255))

    # Inner core of sparkle
    core_points = []
    for i in range(8):
        angle = i * (math.pi / 4)
        r = (r_outer * 0.45) if (i % 2 == 0) else (r_inner * 0.45)
        px = cx + r * math.cos(angle)
        py = cy + r * math.sin(angle)
        core_points.append((px, py))
    draw.polygon(core_points, fill=(255, 255, 255, 255))

    # Sparkle 2 (Mini companion sparkle)
    cx2, cy2 = 215, 290
    r_outer2, r_inner2 = 24, 7
    points2 = []
    for i in range(8):
        angle = i * (math.pi / 4)
        r = r_outer2 if (i % 2 == 0) else r_inner2
        px = cx2 + r * math.cos(angle)
        py = cy2 + r * math.sin(angle)
        points2.append((px, py))
    draw.polygon(points2, fill=(16, 185, 129, 255))

    # Downsample to 256x256 high-quality anti-aliased image
    img_256 = img.resize((256, 256), Image.Resampling.LANCZOS)
    img_256.save(png_path, "PNG")

    # Generate multi-size ICO
    icon_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img_256.save(ico_path, format="ICO", sizes=icon_sizes)

    print(f"[OK] Generated: {png_path}")
    print(f"[OK] Generated: {ico_path}")

if __name__ == "__main__":
    assets_folder = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
    create_app_icon(assets_folder)
