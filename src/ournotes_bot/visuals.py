"""Notebook styled image replies using the existing Our Notes assets."""

from __future__ import annotations

import io
import asyncio
import hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen

import aiohttp

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .data import Card, Chart, Song, localized_text


PAPER = "#FFF9F1"
INK = "#353D4B"
MUTED = "#7B8190"
PINK = "#EE718F"
MINT = "#70C9B0"
BLUE = "#7AA9DE"
BORDER = "#E9DCCF"
FONT_PATHS = [
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
]
IMAGE_TEXT = {
    "zh": {"songs": "曲目检索", "song_list": "歌曲列表", "chart": "谱面资料", "card": "卡面档案", "cards": "卡牌检索", "card_list": "卡牌列表", "composer": "作曲", "lyricist": "作词", "preview": "谱面预览资源尚未开放；当前展示等级与物量。", "image_missing": "图片暂不可用", "power": "综合力", "performance": "演出", "technic": "技巧", "visual": "表现", "skill": "技能", "type": "属性"},
    "en": {"songs": "Song search", "song_list": "Songs", "chart": "Chart details", "card": "Card details", "cards": "Card search", "card_list": "Cards", "composer": "Composer", "lyricist": "Lyrics", "preview": "Chart preview is unavailable; showing level and note count.", "image_missing": "Image unavailable", "power": "Total power", "performance": "Performance", "technic": "Technique", "visual": "Visual", "skill": "Skill", "type": "Type"},
    "ja": {"songs": "楽曲検索", "song_list": "楽曲一覧", "chart": "譜面情報", "card": "カード情報", "cards": "カード検索", "card_list": "カード一覧", "composer": "作曲", "lyricist": "作詞", "preview": "譜面プレビューは未公開です。レベルとノーツ数を表示します。", "image_missing": "画像を取得できません", "power": "総合力", "performance": "パフォーマンス", "technic": "テクニック", "visual": "ビジュアル", "skill": "スキル", "type": "属性"},
}


def _label(locale: str, key: str) -> str:
    return IMAGE_TEXT.get(locale, IMAGE_TEXT["zh"])[key]


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_PATHS:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _canvas(width: int, height: int, label: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (width, height), PAPER)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((24, 24, width - 24, height - 24), radius=32, fill="#FFFFFF", outline=BORDER, width=3)
    draw.rounded_rectangle((48, 45, 260, 95), radius=23, fill=PINK)
    draw.text((72, 50), label, fill="white", font=_font(27))
    draw.line((50, 126, width - 50, 126), fill=BORDER, width=2)
    draw.ellipse((width - 112, 48, width - 85, 75), fill=MINT)
    draw.ellipse((width - 80, 75, width - 60, 95), fill="#F3D28C")
    return image, draw


def _write(draw: ImageDraw.ImageDraw, text: str, x: int, y: int, max_width: int, size: int, color: str = INK) -> None:
    font = _font(size)
    while text and draw.textlength(text, font=font) > max_width:
        text = text[:-2] + "…"
    draw.text((x, y), text, font=font, fill=color)


def _asset(url: str, size: tuple[int, int]) -> Image.Image | None:
    try:
        cache = Path(__file__).resolve().parents[2] / "data" / "asset-cache"
        cache.mkdir(parents=True, exist_ok=True)
        path = cache / (hashlib.sha256(url.encode()).hexdigest() + ".png")
        if path.exists():
            raw = path.read_bytes()
        else:
            try:
                with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=12) as response:
                    raw = response.read(6_000_000)
            except Exception:
                async def download() -> bytes:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, timeout=aiohttp.ClientTimeout(total=18)) as response:
                            response.raise_for_status()
                            return await response.read()
                raw = asyncio.run(download())
            if len(raw) > 6_000_000:
                return None
            path.write_bytes(raw)
        with Image.open(io.BytesIO(raw)) as image:
            return ImageOps.fit(image.convert("RGB"), size, method=Image.Resampling.LANCZOS)
    except Exception:
        return None


def _prefetch_assets(urls: list[str], size: tuple[int, int]) -> dict[str, Image.Image | None]:
    unique = list(dict.fromkeys(urls))
    with ThreadPoolExecutor(max_workers=6) as pool:
        return dict(zip(unique, pool.map(lambda url: _asset(url, size), unique)))


def _paste_loaded_asset(canvas: Image.Image, draw: ImageDraw.ImageDraw, image: Image.Image | None,
                        box: tuple[int, int, int, int], locale: str = "zh") -> None:
    x0, y0, x1, y1 = box
    if image:
        canvas.paste(image, (x0, y0))
    else:
        draw.rounded_rectangle(box, radius=12, fill="#F5EEE7")
        _write(draw, _label(locale, "image_missing"), x0 + 14, y0 + 14, x1 - x0 - 28, 20, MUTED)


def _paste_asset(canvas: Image.Image, draw: ImageDraw.ImageDraw, url: str, box: tuple[int, int, int, int], locale: str = "zh") -> None:
    x0, y0, x1, y1 = box
    _paste_loaded_asset(canvas, draw, _asset(url, (x1 - x0, y1 - y0)), box, locale)


def _bytes(image: Image.Image) -> bytes:
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=86, optimize=True)
    return out.getvalue()


def render_song_list(songs: list[Song], query: str, locale: str = "zh", footer: str = "") -> bytes:
    width = 900
    height = 260 + len(songs) * 125 + (80 if footer else 0)
    image, draw = _canvas(width, height, _label(locale, "songs"))
    _write(draw, f"{_label(locale, 'song_list')} · {query}", 50, 146, width - 100, 32)
    jackets = _prefetch_assets([song.jacket_url for song in songs], (86, 86))
    for index, song in enumerate(songs):
        top = 208 + index * 125
        draw.rounded_rectangle((48, top, width - 48, top + 110), radius=18, fill="#FBF7F2", outline=BORDER, width=2)
        _paste_loaded_asset(image, draw, jackets[song.jacket_url], (64, top + 12, 150, top + 98), locale)
        _write(draw, localized_text(song, "title", locale), 170, top + 14, 470, 27)
        _write(draw, f"#{song.id}  ·  {localized_text(song, 'band', locale)}", 170, top + 55, 470, 20, MUTED)
        xs = (670, 720, 770, 820)
        colors = (BLUE, MINT, "#F3D28C", PINK)
        for x, chart, color in zip(xs, song.charts, colors):
            draw.ellipse((x - 18, top + 38, x + 18, top + 74), fill=color)
            value = f"{chart.display_level:g}"
            draw.text((x - draw.textlength(value, font=_font(19)) / 2, top + 42), value, fill=INK, font=_font(19))
    if footer:
        for index, line in enumerate(footer.splitlines()[:2]):
            _write(draw, line, 55, height - 95 + index * 31, width - 110, 21, MUTED)
    return _bytes(image)


def render_chart(song: Song, charts: tuple[Chart, ...], locale: str = "zh") -> bytes:
    image, draw = _canvas(900, 760, _label(locale, "chart"))
    _paste_asset(image, draw, song.jacket_url, (54, 155, 284, 385), locale)
    _write(draw, localized_text(song, "title", locale), 315, 172, 520, 37)
    _write(draw, f"#{song.id}  ·  {localized_text(song, 'band', locale)}", 315, 232, 520, 24, MUTED)
    _write(draw, f"{_label(locale, 'composer')}  {localized_text(song, 'composer', locale)}", 315, 290, 520, 21)
    _write(draw, f"{_label(locale, 'lyricist')}  {localized_text(song, 'lyricist', locale)}", 315, 327, 520, 21)
    draw.line((54, 420, 846, 420), fill=BORDER, width=2)
    colors = {"EASY": BLUE, "NORMAL": MINT, "HARD": "#E7BA66", "EXPERT": PINK}
    for index, chart in enumerate(charts):
        top = 443 + index * 54
        draw.rounded_rectangle((58, top, 240, top + 42), radius=18, fill=colors.get(chart.difficulty, BLUE))
        _write(draw, chart.difficulty, 82, top + 5, 160, 22, "white")
        _write(draw, f"Lv.{chart.display_level:g}", 298, top + 3, 150, 27)
        _write(draw, f"{chart.notes} Notes", 535, top + 5, 250, 23)
    draw.line((54, 675, 846, 675), fill=BORDER, width=2)
    _write(draw, _label(locale, "preview"), 65, 687, 760, 18, MUTED)
    return _bytes(image)


def render_card(card: Card, locale: str = "zh") -> bytes:
    image, draw = _canvas(900, 1810, _label(locale, "card"))
    _write(draw, localized_text(card, "band", locale), 56, 145, 460, 27, PINK)
    _write(draw, localized_text(card, "character", locale), 56, 190, 760, 39)
    _write(draw, localized_text(card, "title", locale), 56, 250, 760, 29)
    _paste_asset(image, draw, card.full_url, (64, 315, 836, 1345), locale)
    draw.rounded_rectangle((63, 1370, 837, 1730), radius=22, fill="#FBF7F2", outline=BORDER, width=2)
    _write(draw, f"{'★' * card.rarity}    ID {card.id}    {_label(locale, 'type')} {card.card_type}", 88, 1393, 720, 28, PINK)
    total = card.performance + card.technic + card.visual
    _write(draw, f"{_label(locale, 'power')}  {total:,}", 88, 1447, 720, 31)
    values = [(_label(locale, "performance"), card.performance, PINK), (_label(locale, "technic"), card.technic, BLUE), (_label(locale, "visual"), card.visual, MINT)]
    for index, (label, value, color) in enumerate(values):
        y = 1504 + index * 55
        _write(draw, f"{label}  {value:,}", 88, y, 270, 22)
        draw.rounded_rectangle((365, y + 7, 780, y + 28), radius=10, fill="#E9E3DE")
        draw.rounded_rectangle((365, y + 7, 365 + int(415 * value / max(1, max(v for _, v, _ in values))), y + 28), radius=10, fill=color)
    _write(draw, f"{_label(locale, 'skill')}  {localized_text(card, 'skill_name', locale)}", 88, 1671, 700, 20, MUTED)
    return _bytes(image)


def render_card_list(cards: list[Card], query: str, locale: str = "zh", footer: str = "") -> bytes:
    height = 225 + len(cards) * 165 + (80 if footer else 0)
    image, draw = _canvas(900, height, _label(locale, "cards"))
    _write(draw, f"{_label(locale, 'card_list')} · {query}", 52, 142, 790, 31)
    thumbnails = _prefetch_assets([card.thumbnail_url for card in cards], (93, 125))
    for index, card in enumerate(cards):
        top = 195 + index * 165
        draw.rounded_rectangle((50, top, 850, top + 145), radius=18, fill="#FBF7F2", outline=BORDER, width=2)
        _paste_loaded_asset(image, draw, thumbnails[card.thumbnail_url], (68, top + 10, 161, top + 135), locale)
        _write(draw, localized_text(card, "character", locale), 190, top + 13, 590, 27)
        _write(draw, localized_text(card, "title", locale), 190, top + 55, 590, 22)
        _write(draw, f"#{card.id}  ·  {'★' * card.rarity}  ·  {_label(locale, 'power')} {card.performance + card.technic + card.visual:,}", 190, top + 101, 590, 20, MUTED)
    if footer:
        for index, line in enumerate(footer.splitlines()[:2]):
            _write(draw, line, 55, height - 95 + index * 31, 790, 21, MUTED)
    return _bytes(image)
