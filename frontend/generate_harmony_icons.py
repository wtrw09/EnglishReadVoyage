#!/usr/bin/env python3
"""
生成 HarmonyOS App 图标（与 Android 完全一致的莫兰迪极简字母标）
设计理念：
  - 背景：莫兰迪暖灰（#B5A89A），低饱和高级感
  - 主体：象牙白（#F2EBE0）E 字母，横臂由三条书页线组成，形似翻开的书
  - 点缀：一条细金线（#C9A876）贯穿中臂，象征阅读航程

生成文件：
  - background.png  → 纯色背景（供 layered_image 使用）
  - foreground.png  → E 字母前景（透明背景，供 layered_image 使用）
  - startIcon.png   → 完整图标（背景+前景合并，供启动窗口使用）
"""

from PIL import Image, ImageDraw, ImageFilter
from pathlib import Path

# 路径配置
HARMONY_ENTRY_MEDIA = Path(
    r"F:\PyProject\EnglishReadVoyage\harmony\entry\src\main\resources\base\media"
)
HARMONY_APPSCOPE_MEDIA = Path(
    r"F:\PyProject\EnglishReadVoyage\harmony\AppScope\resources\base\media"
)

# 图标输出尺寸（足够大，适配各种 DPI）
ICON_SIZE = 1024

# 莫兰迪配色（与 Android 完全一致）
BG_COLOR  = "#B5A89A"            # 暖灰驼（背景）
BG_COLOR_DEEP = (160, 146, 132)  # 阴影用深一档
FG_IVORY  = (242, 235, 224)      # 象牙白（主字母）
FG_SHADOW = (120, 108, 96, 60)   # 柔和投影
ACCENT_GOLD = (201, 168, 118)    # 金线点缀


def _draw_E_monogram(draw: ImageDraw.ImageDraw, cx: float, cy: float, unit: float,
                     stem_color, arm_color, gold_color):
    """在 (cx, cy) 周围以 unit 为单位绘制 E 字母书本
    设计：左侧一条粗竖条（书脊），右侧三条横线（书页/E 横臂），上短、中带金线、下长
    """
    # --- 书脊（E 的竖笔） ---
    stem_w = 1.6 * unit
    stem_h = 7.2 * unit
    stem_x = cx - 2.6 * unit
    stem_top = cy - stem_h / 2
    stem_bottom = cy + stem_h / 2
    r = 0.5 * unit
    draw.rounded_rectangle(
        [stem_x, stem_top, stem_x + stem_w, stem_bottom],
        radius=r, fill=stem_color,
    )

    # --- 三条横臂（书页） ---
    arm_x0 = stem_x + stem_w + 0.25 * unit
    arm_h = 1.15 * unit
    arm_r = arm_h / 2

    # 上臂（较短）
    top_y = stem_top + 0.05 * unit
    top_len = 3.6 * unit
    draw.rounded_rectangle(
        [arm_x0, top_y, arm_x0 + top_len, top_y + arm_h],
        radius=arm_r, fill=arm_color,
    )

    # 中臂（最短，配金线）
    mid_len = 2.9 * unit
    mid_y = cy - arm_h / 2
    draw.rounded_rectangle(
        [arm_x0, mid_y, arm_x0 + mid_len, mid_y + arm_h],
        radius=arm_r, fill=arm_color,
    )
    # 金线点缀：贴着中臂顶部的细线，延伸略长
    gold_h = 0.28 * unit
    gold_len = 3.4 * unit
    gold_y = mid_y - gold_h - 0.35 * unit
    draw.rounded_rectangle(
        [arm_x0, gold_y, arm_x0 + gold_len, gold_y + gold_h],
        radius=gold_h / 2, fill=gold_color,
    )

    # 下臂（最长）
    bot_len = 4.0 * unit
    bot_y = stem_bottom - arm_h - 0.05 * unit
    draw.rounded_rectangle(
        [arm_x0, bot_y, arm_x0 + bot_len, bot_y + arm_h],
        radius=arm_r, fill=arm_color,
    )


def draw_background(size: int) -> Image.Image:
    """绘制纯色背景"""
    return Image.new('RGBA', (size, size), BG_COLOR)


def draw_foreground(size: int) -> Image.Image:
    """绘制 E 字母前景（透明背景，用于 layered_image 前景层）"""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 使用较大的 unit 使字母居中占满画布约 60%
    unit = size / 22

    # 柔和投影
    shadow = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    _draw_E_monogram(
        sdraw, size / 2 + unit * 0.12, size / 2 + unit * 0.22, unit,
        stem_color=(60, 50, 42, 70),
        arm_color=(60, 50, 42, 70),
        gold_color=(60, 50, 42, 70),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=max(1.0, size * 0.010)))
    img.alpha_composite(shadow)

    _draw_E_monogram(
        draw, size / 2, size / 2, unit,
        stem_color=FG_IVORY,
        arm_color=FG_IVORY,
        gold_color=ACCENT_GOLD,
    )
    return img


def draw_start_icon(size: int) -> Image.Image:
    """绘制完整的启动图标（背景 + 前景合并）"""
    bg = draw_background(size)

    # 背景细微径向过渡
    overlay = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    odraw.ellipse(
        [-size * 0.2, -size * 0.2, size * 0.9, size * 0.9],
        fill=(255, 255, 255, 22),
    )
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=size * 0.08))
    bg.alpha_composite(overlay)

    fg = draw_foreground(size)
    bg.alpha_composite(fg)
    return bg


def main():
    print("=" * 50)
    print("开始生成 HarmonyOS 图标（莫兰迪极简字母标）")
    print("=" * 50)

    # 1. 生成 Entry 模块图标
    print("\n--- Entry 模块图标 ---")
    for name, fn in [("background.png", draw_background),
                     ("foreground.png", draw_foreground)]:
        img = fn(ICON_SIZE)
        path = HARMONY_ENTRY_MEDIA / name
        img.save(path, 'PNG')
        print(f"  生成: {path.name} ({ICON_SIZE}x{ICON_SIZE})")

    # 2. 生成 AppScope 图标
    print("\n--- AppScope 图标 ---")
    for name, fn in [("background.png", draw_background),
                     ("foreground.png", draw_foreground)]:
        img = fn(ICON_SIZE)
        path = HARMONY_APPSCOPE_MEDIA / name
        img.save(path, 'PNG')
        print(f"  生成: {path.name} ({ICON_SIZE}x{ICON_SIZE})")

    # 3. 生成 startIcon（启动窗口图标，完整背景+前景合并）
    print("\n--- 启动窗口图标 ---")
    start_icon = draw_start_icon(ICON_SIZE)
    start_path = HARMONY_ENTRY_MEDIA / "startIcon.png"
    start_icon.save(start_path, 'PNG')
    print(f"  生成: startIcon.png ({ICON_SIZE}x{ICON_SIZE})")

    print("\n" + "=" * 50)
    print("✓ HarmonyOS 图标生成完成!")
    print("=" * 50)


if __name__ == "__main__":
    main()
