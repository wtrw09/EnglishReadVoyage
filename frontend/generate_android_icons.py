#!/usr/bin/env python3
"""
生成 Android App 图标（莫兰迪极简字母标）
设计理念：
  - 背景：莫兰迪暖灰（#B5A89A），低饱和高级感
  - 主体：象牙白（#F2EBE0）E 字母，横臂由三条书页线组成，形似翻开的书
  - 点缀：一条细金线（#C9A876）贯穿中臂，象征阅读航程
"""

from PIL import Image, ImageDraw, ImageFilter
from pathlib import Path

# 路径配置
ANDROID_RES_DIR = Path(r"F:\PyProject\EnglishReadVoyage\android\app\src\main\res")

# Android 启动图标尺寸（传统图标）
LAUNCHER_SIZES = {
    "mipmap-mdpi": 48,
    "mipmap-hdpi": 72,
    "mipmap-xhdpi": 96,
    "mipmap-xxhdpi": 144,
    "mipmap-xxxhdpi": 192,
}

# 自适应图标前景尺寸（每 dpi 对应的前景 PNG 像素尺寸，108dp 基准）
FOREGROUND_SIZES = {
    "mipmap-mdpi": 108,
    "mipmap-hdpi": 162,
    "mipmap-xhdpi": 216,
    "mipmap-xxhdpi": 324,
    "mipmap-xxxhdpi": 432,
}

# Capacitor 启动屏尺寸 (宽, 高)
SPLASH_SIZES = {
    "drawable": (480, 320),
    "drawable-port-mdpi": (320, 480),
    "drawable-port-hdpi": (480, 800),
    "drawable-port-xhdpi": (720, 1280),
    "drawable-port-xxhdpi": (960, 1600),
    "drawable-port-xxxhdpi": (1280, 1920),
    "drawable-land-mdpi": (480, 320),
    "drawable-land-hdpi": (800, 480),
    "drawable-land-xhdpi": (1280, 720),
    "drawable-land-xxhdpi": (1600, 960),
    "drawable-land-xxxhdpi": (1920, 1280),
}

# splash 背景（与 capacitor.config.json 的 backgroundColor 一致，纯白）
SPLASH_BG = (255, 255, 255, 255)

# 莫兰迪配色
BG_COLOR = "#B5A89A"           # 暖灰驼（背景）
BG_COLOR_DEEP = (160, 146, 132) # 阴影用深一档
FG_IVORY = (242, 235, 224)     # 象牙白（主字母）
FG_SHADOW = (120, 108, 96, 60) # 柔和投影
ACCENT_GOLD = (201, 168, 118)  # 金线点缀


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
    # 带圆角的竖条
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

    # 下臂（最长，与上臂对称偏长一点，形成稳重感）
    bot_len = 4.0 * unit
    bot_y = stem_bottom - arm_h - 0.05 * unit
    draw.rounded_rectangle(
        [arm_x0, bot_y, arm_x0 + bot_len, bot_y + arm_h],
        radius=arm_r, fill=arm_color,
    )


def draw_launcher_icon(size: int) -> Image.Image:
    """绘制带背景的传统启动图标（legacy icon，整图包含背景+前景）"""
    img = Image.new('RGBA', (size, size), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # 背景细微径向过渡：右下角稍暗，增强高级感
    # 用一层半透明柔化椭圆模拟光晕
    overlay = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    odraw.ellipse(
        [-size * 0.2, -size * 0.2, size * 0.9, size * 0.9],
        fill=(255, 255, 255, 22),
    )
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=size * 0.08))
    img.alpha_composite(overlay)

    # 先画柔和投影
    shadow = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    unit = size / 16  # 以 16 份为基准单位
    _draw_E_monogram(
        sdraw, size / 2 + unit * 0.12, size / 2 + unit * 0.22, unit,
        stem_color=(60, 50, 42, 70),
        arm_color=(60, 50, 42, 70),
        gold_color=(60, 50, 42, 70),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=max(1.0, size * 0.012)))
    img.alpha_composite(shadow)

    # 再画主体
    _draw_E_monogram(
        draw, size / 2, size / 2, unit,
        stem_color=FG_IVORY,
        arm_color=FG_IVORY,
        gold_color=ACCENT_GOLD,
    )
    return img


def draw_round_icon(size: int) -> Image.Image:
    """绘制圆形启动图标"""
    base = draw_launcher_icon(size)
    mask = Image.new('L', (size, size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size, size], fill=255)
    out = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    out.paste(base, (0, 0), mask)
    return out


def draw_splash(width: int, height: int) -> Image.Image:
    """绘制启动屏：白底 + 中央莫兰迪 E 字母书本 logo
    logo 尺寸约为短边的 30%，保持视觉上的留白感
    """
    img = Image.new('RGBA', (width, height), SPLASH_BG)

    short = min(width, height)
    logo_size = int(short * 0.30)
    # 以 draw_launcher_icon 输出为基础（带莫兰迪背景的完整图标），再做圆角裁切
    logo = draw_launcher_icon(logo_size)

    # 圆角遮罩，使 logo 呈圆角方形，与现代启动屏美学一致
    radius = int(logo_size * 0.22)
    mask = Image.new('L', (logo_size, logo_size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, logo_size, logo_size], radius=radius, fill=255,
    )

    cx = (width - logo_size) // 2
    cy = (height - logo_size) // 2
    img.paste(logo, (cx, cy), mask)
    return img


def draw_foreground(size: int) -> Image.Image:
    """绘制自适应图标前景（透明背景，主体位于中心 66dp 安全区内）
    Android adaptive icon: 108dp 画布中心 66dp 为安全区，外圈 21dp 可能被裁剪。
    因此这里把 E 字母缩小到大约 60% 画布宽度。
    """
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # 自适应图标中，内容需要更小——限制在约 60dp 区域内
    unit = size / 22  # 比 legacy(16) 更小，预留外圈裁剪空间

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


def main():
    print("开始生成 Android 图标（莫兰迪极简字母标）...")

    # 1. 更新自适应图标背景颜色为莫兰迪暖灰
    bg_color_file = ANDROID_RES_DIR / "values" / "ic_launcher_background.xml"
    bg_color_content = f"""<?xml version="1.0" encoding="utf-8"?>
<resources>
    <color name="ic_launcher_background">{BG_COLOR}</color>
</resources>
"""
    with open(bg_color_file, 'w', encoding='utf-8') as f:
        f.write(bg_color_content)
    print(f"✓ 更新自适应图标背景颜色为 {BG_COLOR}")

    # 2. 生成 legacy 启动图标（方形 + 圆形）
    for dir_name, size in LAUNCHER_SIZES.items():
        mipmap_dir = ANDROID_RES_DIR / dir_name
        mipmap_dir.mkdir(parents=True, exist_ok=True)

        legacy = draw_launcher_icon(size)
        legacy.save(mipmap_dir / "ic_launcher.png", 'PNG')
        print(f"  生成: {dir_name}/ic_launcher.png ({size}x{size})")

        round_img = draw_round_icon(size)
        round_img.save(mipmap_dir / "ic_launcher_round.png", 'PNG')
        print(f"  生成: {dir_name}/ic_launcher_round.png ({size}x{size})")

    # 3. 生成自适应图标前景（所有密度都要覆盖）
    for dir_name, fg_size in FOREGROUND_SIZES.items():
        mipmap_dir = ANDROID_RES_DIR / dir_name
        fg = draw_foreground(fg_size)
        fg.save(mipmap_dir / "ic_launcher_foreground.png", 'PNG')
        print(f"  生成: {dir_name}/ic_launcher_foreground.png ({fg_size}x{fg_size})")

    # 4. 兼容旧的 drawable 目录前景（若存在）
    for drawable_dir in ("drawable", "drawable-v24"):
        d = ANDROID_RES_DIR / drawable_dir
        if d.exists():
            fg = draw_foreground(432)
            fg.save(d / "ic_launcher_foreground.png", 'PNG')
            print(f"  生成: {drawable_dir}/ic_launcher_foreground.png (432x432)")

    # 5. 生成启动屏 splash.png（覆盖 Capacitor 默认蓝色 X 图案）
    for dir_name, (w, h) in SPLASH_SIZES.items():
        splash_dir = ANDROID_RES_DIR / dir_name
        splash_dir.mkdir(parents=True, exist_ok=True)
        splash = draw_splash(w, h)
        splash.save(splash_dir / "splash.png", 'PNG')
        print(f"  生成: {dir_name}/splash.png ({w}x{h})")

    print("\n✓ 图标生成完成!")
    print("\n请在 Android Studio 中执行:")
    print("  Build → Clean Project")
    print("  Build → Rebuild Project")
    print("  然后重新安装 APK")


if __name__ == "__main__":
    main()
