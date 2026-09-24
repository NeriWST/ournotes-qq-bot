from __future__ import annotations

import json
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen


DIFFICULTIES = (
    ("EASY", "easyID"),
    ("NORMAL", "normalID"),
    ("HARD", "hardID"),
    ("EXPERT", "expertID"),
)
CARD_ASSET_MANIFEST = "https://raw.githubusercontent.com/StarMoe-org/moenotes/main/src/lib/assets/generated/images.json"
CARD_RELEASE_BASE = "https://storage.bdon.moe/moenotes"


@dataclass(frozen=True)
class Chart:
    difficulty: str
    level: int
    display_level: float
    notes: int
    chart_file: str


@dataclass(frozen=True)
class Song:
    id: int
    title: str
    titles: tuple[str, ...]
    band: str
    composer: str
    lyricist: str
    arranger: str
    start_at: str
    jacket_url: str
    charts: tuple[Chart, ...]
    localized: dict[str, dict[str, str]] = field(default_factory=dict)


@dataclass(frozen=True)
class Card:
    id: int
    asset_id: int
    title: str
    character: str
    band: str
    rarity: int
    card_type: int
    performance: int
    technic: int
    visual: int
    start_at: str
    skill_name: str
    full_url: str
    thumbnail_url: str
    localized: dict[str, dict[str, str]] = field(default_factory=dict)


class DataError(RuntimeError):
    pass


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    value = value.translate(str.maketrans({"灯": "燈", "爱": "愛"}))
    # Match Japanese hiragana and katakana spellings of the same title.
    value = "".join(chr(ord(char) - 0x60) if "ァ" <= char <= "ヶ" else char for char in value)
    return "".join(char for char in value if not char.isspace() and char not in "-_·・!！?？'\"“”‘’")


def localized_text(item: Song | Card, field_name: str, locale: str = "zh") -> str:
    original = str(getattr(item, field_name))
    return item.localized.get(field_name, {}).get(locale) or original


_ROMAJI = {
    "kya": "きゃ", "kyu": "きゅ", "kyo": "きょ", "sha": "しゃ", "shu": "しゅ", "sho": "しょ",
    "cha": "ちゃ", "chu": "ちゅ", "cho": "ちょ", "nya": "にゃ", "nyu": "にゅ", "nyo": "にょ",
    "hya": "ひゃ", "hyu": "ひゅ", "hyo": "ひょ", "mya": "みゃ", "myu": "みゅ", "myo": "みょ",
    "rya": "りゃ", "ryu": "りゅ", "ryo": "りょ", "gya": "ぎゃ", "gyu": "ぎゅ", "gyo": "ぎょ",
    "ja": "じゃ", "ju": "じゅ", "jo": "じょ", "bya": "びゃ", "byu": "びゅ", "byo": "びょ",
    "pya": "ぴゃ", "pyu": "ぴゅ", "pyo": "ぴょ", "shi": "し", "chi": "ち", "tsu": "つ", "fu": "ふ",
    "ya": "や", "yu": "ゆ", "yo": "よ", "wa": "わ", "wo": "を",
    "a": "あ", "i": "い", "u": "う", "e": "え", "o": "お",
}
for _consonant, _kana in {
    "k": "かきくけこ", "s": "さしすせそ", "t": "たちつてと", "n": "なにぬねの",
    "h": "はひふへほ", "m": "まみむめも", "r": "らりるれろ",
    "g": "がぎぐげご", "z": "ざじずぜぞ", "d": "だぢづでど",
    "b": "ばびぶべぼ", "p": "ぱぴぷぺぽ",
}.items():
    _ROMAJI.update({f"{_consonant}{vowel}": character for vowel, character in zip("aiueo", _kana) if character != " "})


def roman_to_hiragana(value: str) -> str:
    """Add phonetic search aliases for romanized Japanese names, not translations."""
    text = value.casefold().split("(", 1)[0].replace(" ", "")
    if not re.fullmatch(r"[a-z]+", text):
        return ""
    result = []
    index = 0
    while index < len(text):
        if index + 1 < len(text) and text[index] == text[index + 1] and text[index] not in "aeioun":
            result.append("っ")
            index += 1
            continue
        if text[index] == "n" and (index + 1 == len(text) or text[index + 1] not in "aeiouy"):
            result.append("ん")
            index += 1
            continue
        match = next((text[index:index + size] for size in (3, 2, 1) if text[index:index + size] in _ROMAJI), None)
        if not match:
            return ""
        result.append(_ROMAJI[match])
        index += len(match)
    return "".join(result)


@dataclass(frozen=True)
class CharacterAlias:
    display: str
    search_terms: tuple[str, ...]


# The roster follows https://bang-dream-on.bushimo.jp/ . Short Latin forms include
# user-requested nicknames and unambiguous abbreviations of the official names.
# Ave Mujica members need both their civilian and stage names for card search.
CHARACTER_GROUPS: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("灯", ("高松燈",), ("tmr", "tomori", "灯", "燈")),
    ("爱音", ("千早愛音",), ("anon", "爱音", "愛音")),
    ("乐奈", ("要楽奈",), ("rana", "乐奈", "楽奈")),
    ("素世", ("長崎そよ",), ("soyo", "素世", "そよ")),
    ("立希", ("椎名立希",), ("rikki", "rkk", "taki", "立希")),
    ("初华", ("三角初華", "ドロリス"), ("uika", "uik", "doloris", "dls", "初华", "初華")),
    ("睦", ("若葉睦", "モーティス"), ("mtm", "mutsumi", "mortis", "睦", "若叶睦", "若葉睦")),
    ("海铃", ("八幡海鈴", "ティモリス"), ("umiri", "umr", "timoris", "海铃", "海鈴")),
    ("喵梦", ("祐天寺にゃむ", "アモーリス"), ("nyamu", "nym", "amoris", "にゃむ", "喵梦")),
    ("祥子", ("豊川祥子", "オブリビオニス"), ("skk", "saki", "sakiko", "oblivionis", "祥子")),
    ("阿拉蕾", ("仲町あられ",), ("arl", "arale", "阿拉蕾", "あられ")),
    ("野乃花", ("宮永ののか",), ("nnk", "nonoka", "野乃花", "ののか")),
    ("峰月律", ("峰月律",), ("rts", "ritsu", "峰月律")),
    ("藤都子", ("藤都子",), ("myk", "miyako", "藤都子")),
    ("千石由乃", ("千石ユノ",), ("yuno", "千石由乃", "千石ユノ")),
    ("汐见萤", ("汐見蛍",), ("htr", "hotaru", "汐见萤", "汐見蛍")),
    ("伊泽夏目", ("伊沢なつめ",), ("ntsm", "natsume", "伊泽夏目", "伊沢なつめ")),
    ("琴平凪", ("琴平凪",), ("nagi", "琴平凪")),
    ("滨崎真幌", ("浜崎まほろ",), ("mhr", "mahoro", "滨崎真幌", "浜崎まほろ")),
    ("和泉朋花", ("和泉朋花",), ("hka", "houka", "和泉朋花")),
    ("须贺蕾叶", ("須賀蕾叶",), ("raika", "rka", "须贺蕾叶", "須賀蕾叶")),
    ("马桥心玖", ("馬橋心玖",), ("miku", "mku", "马桥心玖", "馬橋心玖")),
    ("矢仓蓬咲", ("矢倉蓬咲",), ("ymg", "yomogi", "矢仓蓬咲", "矢倉蓬咲")),
    ("梅里千绘里", ("梅里ちえり",), ("chr", "chieri", "梅里千绘里", "梅里ちえり")),
    ("四宫宁月", ("四宮寧月",), ("szk", "shizuku", "四宫宁月", "四宮寧月")),
)

CHARACTER_ALIASES: dict[str, CharacterAlias] = {
    normalize(name): CharacterAlias(display, search_terms)
    for display, search_terms, names in CHARACTER_GROUPS
    for name in names
}
for _display, _terms, _names in CHARACTER_GROUPS:
    for _term in _names:
        if _term.isascii() and len(_term) > 3:
            _kana = roman_to_hiragana(_term)
            if _kana:
                CHARACTER_ALIASES.setdefault(normalize(_kana), CharacterAlias(_display, _terms))


def resolve_character_alias(query: str) -> CharacterAlias | None:
    return CHARACTER_ALIASES.get(normalize(query))


def _fetch_json(url: str, timeout: int = 30, attempts: int = 4) -> Any:
    request = Request(url, headers={"User-Agent": "ournotes-qq-bot/0.1"})
    for attempt in range(1, attempts + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except Exception as exc:
            if attempt == attempts:
                raise DataError(f"获取数据失败：{url} ({exc})") from exc
            time.sleep(attempt * 0.5)


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        value = value.get("_allData")
    if not isinstance(value, list):
        raise DataError("远端 MasterData 格式无法识别")
    # Upstream tables may use either id/name or _id/_name column names.
    return [{key.removeprefix("_"): entry for key, entry in row.items()} for row in value]


def _text_variants(row: dict[str, Any] | None) -> tuple[str, ...]:
    if not row:
        return ()
    keys = ("simplifiedChinese", "traditionalChinese", "japanese", "english", "korean")
    return tuple(dict.fromkeys(str(row.get(key, "")).strip() for key in keys if str(row.get(key, "")).strip()))


def _localized_fields(**rows: dict[str, Any] | None) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for field_name, row in rows.items():
        if not row:
            continue
        variants = {
            locale: str(row.get(key, "")).strip()
            for locale, key in (("zh", "simplifiedChinese"), ("ja", "japanese"), ("en", "english"))
            if str(row.get(key, "")).strip()
        }
        if variants:
            result[field_name] = variants
    return result


def _display_text(row: dict[str, Any] | None, fallback: str = "") -> str:
    variants = _text_variants(row)
    return variants[0] if variants else fallback


class SongRepository:
    def __init__(self, data_base: str, cache_file: Path, cache_ttl_hours: float = 6) -> None:
        self.data_base = data_base.rstrip("/")
        self.cache_file = cache_file
        self.cache_ttl_hours = cache_ttl_hours
        self.songs: list[Song] = []
        self.cards: list[Card] = []
        self.metadata: dict[str, Any] = {}

    def load(self, refresh: bool = False) -> None:
        if refresh:
            self.refresh()
            return
        if not self._cache_is_fresh():
            try:
                self.refresh()
                return
            except DataError:
                if not self.cache_file.exists():
                    raise
        self._load_cache()

    def refresh(self) -> None:
        manifest = _fetch_json(f"{self.data_base}/version/latest.json")
        version = manifest.get("dataVersion") or manifest.get("version")
        if not version:
            raise DataError("远端主数据版本信息缺失，已保留现有缓存")
        table_names = (
            "MasterLiveMusic",
            "MasterLiveMusicScore",
            "MasterText",
            "MasterBand",
            "MasterMemberCard",
            "MasterCharacter",
            "MasterLiveSkill",
        )
        # MoeNotes pins every master table to the manifest version. Fetching the
        # tables together also avoids one slow table blocking all the others.
        def fetch_table(name: str) -> list[dict[str, Any]]:
            url = f"{self.data_base}/master/{name}.json?v={quote(str(version), safe='')}"
            return _rows(_fetch_json(url))

        with ThreadPoolExecutor(max_workers=6) as pool:
            tables = dict(zip(table_names, pool.map(fetch_table, table_names)))
        asset_paths = _fetch_json(CARD_ASSET_MANIFEST)
        if not isinstance(asset_paths, dict):
            raise DataError("卡图素材清单格式无法识别，已保留现有缓存")
        songs = self._build_songs(tables, asset_paths)
        cards = self._build_cards(tables, asset_paths)
        if not songs or not cards:
            raise DataError("远端歌曲或卡牌表为空，已拒绝覆盖本地缓存")
        if self.cache_file.exists():
            try:
                previous = json.loads(self.cache_file.read_text(encoding="utf-8"))
                old_version = previous.get("metadata", {}).get("data_version")
                if old_version == version and (
                    len(songs) < len(previous.get("songs", []))
                    or len(cards) < len(previous.get("cards", []))
                ):
                    raise DataError("同版本远端数据条数减少，已保留现有缓存")
            except (OSError, ValueError, TypeError):
                pass

        self.songs = songs
        self.cards = cards
        self.metadata = {
            "source": self.data_base,
            "data_version": version,
            "upstream_fetched_at": manifest.get("fetchedAt"),
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "song_count": len(songs),
            "card_count": len(cards),
            "translation_schema": 1,
        }
        self._save_cache()

    def _save_cache(self) -> None:
        payload = {
            "metadata": self.metadata,
            "songs": [
                {**asdict(song), "charts": [asdict(chart) for chart in song.charts]}
                for song in self.songs
            ],
            "cards": [asdict(card) for card in self.cards],
        }
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.cache_file.with_suffix(self.cache_file.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.cache_file)

    def enrich_translations(self) -> None:
        """Upgrade an old cache using only MasterText when other tables are unavailable."""
        rows = _rows(_fetch_json(f"{self.data_base}/master/MasterText.json"))
        by_id = {str(row.get("id")): row for row in rows}
        by_value: dict[str, dict[str, Any]] = {}
        for row in rows:
            for value in _text_variants(row):
                if len(normalize(value)) >= 2:
                    by_value.setdefault(normalize(value), row)

        def row_for(value: str) -> dict[str, Any] | None:
            return by_value.get(normalize(value))

        upgraded_songs = []
        for song in self.songs:
            title_row = by_id.get(f"Music_Tilte_{song.id}") or row_for(song.title)
            localized = _localized_fields(
                title=title_row, band=row_for(song.band), composer=row_for(song.composer),
                lyricist=row_for(song.lyricist), arranger=row_for(song.arranger),
            )
            localized = {**song.localized, **localized}
            titles = tuple(dict.fromkeys((*song.titles, *_text_variants(title_row))))
            upgraded_songs.append(replace(song, titles=titles, localized=localized))
        self.songs = upgraded_songs

        self.cards = [replace(card, localized={**card.localized, **_localized_fields(
            title=row_for(card.title), character=row_for(card.character), band=row_for(card.band),
            skill_name=row_for(card.skill_name),
        )}) for card in self.cards]
        self.metadata["translation_schema"] = 1
        self._save_cache()

    def _build_songs(self, tables: dict[str, list[dict[str, Any]]],
                     asset_paths: dict[str, str]) -> list[Song]:
        texts = {str(row.get("id")): row for row in tables["MasterText"]}
        scores = {int(row["id"]): row for row in tables["MasterLiveMusicScore"] if "id" in row}
        bands = {int(row["id"]): row for row in tables["MasterBand"] if "id" in row}

        result: list[Song] = []
        for music in tables["MasterLiveMusic"]:
            music_id = int(music["id"])
            title_row = texts.get(f"Music_Tilte_{music_id}") or texts.get(str(music.get("titleTextID", "")))
            titles = _text_variants(title_row)
            title = _display_text(title_row, f"曲目 {music_id}")
            band_ids = music.get("bandIDs") or []
            band_row = bands.get(int(band_ids[0])) if band_ids else None
            band_text = texts.get(str((band_row or {}).get("nameTextID", "")))
            band = _display_text(band_text, "未知乐队")
            composer_text = texts.get(str(music.get("composerTextID", "")))
            lyricist_text = texts.get(str(music.get("lyricistTextID", "")))
            arranger_text = texts.get(str(music.get("arrangerTextID", "")))

            charts: list[Chart] = []
            for difficulty, key in DIFFICULTIES:
                score_id = music.get(key)
                score = scores.get(int(score_id)) if score_id is not None else None
                if not score:
                    continue
                charts.append(Chart(
                    difficulty=difficulty,
                    level=int(score.get("musicScoreLevel", 0)),
                    display_level=float(score.get("musicScoreDisplayLevel", 0)),
                    notes=int(score.get("fullComboCount", 0)),
                    chart_file=str(score.get("musicScoreTextFileName", "")),
                ))

            asset_name = str(music.get("jacketAssetName", ""))
            jacket_path = asset_paths.get(f"Image/Jacket/{asset_name}")
            prefix = f"Image/Jacket/{asset_name}/"
            if not isinstance(jacket_path, str) or not jacket_path.startswith(prefix) or not jacket_path.endswith(".png") or ".." in jacket_path:
                raise DataError(f"歌曲 {music_id} 缺少可信的封面路径，已保留现有缓存")
            result.append(Song(
                id=music_id,
                title=title,
                titles=titles or (title,),
                band=band,
                composer=_display_text(composer_text, "未知"),
                lyricist=_display_text(lyricist_text, "未知"),
                arranger=_display_text(arranger_text, "未知"),
                start_at=str(music.get("startAt", "")),
                jacket_url=f"{CARD_RELEASE_BASE}/{jacket_path}",
                charts=tuple(charts),
                localized=_localized_fields(title=title_row, band=band_text, composer=composer_text,
                                            lyricist=lyricist_text, arranger=arranger_text),
            ))
        return sorted(result, key=lambda song: song.id)

    def _build_cards(self, tables: dict[str, list[dict[str, Any]]], asset_paths: dict[str, str]) -> list[Card]:
        texts = {str(row.get("id")): row for row in tables["MasterText"]}
        characters = {int(row["id"]): row for row in tables["MasterCharacter"]}
        bands = {int(row["id"]): row for row in tables["MasterBand"]}
        skills = {int(row["id"]): row for row in tables["MasterLiveSkill"]}
        result = []
        for row in tables["MasterMemberCard"]:
            character = characters.get(int(row.get("characterID", 0)), {})
            band = bands.get(int(character.get("bandID", 0)), {})
            skill = skills.get(int(row.get("liveSkillID", 0)), {})
            asset_id = int(row["assetID"])
            full_path = asset_paths.get(f"MemberCard/{asset_id}/member_full")
            thumbnail_path = asset_paths.get(f"MemberCard/{asset_id}/member_thumbnail")
            prefix = f"MemberCard/{asset_id}/"
            if not all(isinstance(path, str) and path.startswith(prefix) and path.endswith(".png")
                       and ".." not in path for path in (full_path, thumbnail_path)):
                raise DataError(f"卡牌 {row['id']} 缺少可信的卡图路径，已保留现有缓存")
            title_text = texts.get(str(row.get("subtitleTextID", "")))
            character_text = texts.get(str(row.get("nameTextID", "")))
            band_text = texts.get(str(band.get("nameTextID", "")))
            skill_text = texts.get(str(skill.get("nameTextID", "")))
            result.append(Card(
                id=int(row["id"]),
                asset_id=asset_id,
                title=_display_text(title_text, "未命名卡牌"),
                character=_display_text(character_text, "未知角色"),
                band=_display_text(band_text, "未知乐队"),
                rarity=int(row.get("rarity", 0)),
                card_type=int(row.get("cardType", 0)),
                performance=int(row.get("performancePowerMax", 0)),
                technic=int(row.get("technicPowerMax", 0)),
                visual=int(row.get("visualPowerMax", 0)),
                start_at=str(row.get("startAt", "")),
                skill_name=_display_text(skill_text, "暂无技能名称"),
                full_url=f"{CARD_RELEASE_BASE}/{full_path}",
                thumbnail_url=f"{CARD_RELEASE_BASE}/{thumbnail_path}",
                localized=_localized_fields(title=title_text, character=character_text,
                                            band=band_text, skill_name=skill_text),
            ))
        return sorted(result, key=lambda card: card.id)

    def _cache_is_fresh(self) -> bool:
        if not self.cache_file.exists():
            return False
        age_hours = (time.time() - self.cache_file.stat().st_mtime) / 3600
        return age_hours < self.cache_ttl_hours

    def _load_cache(self) -> None:
        try:
            payload = json.loads(self.cache_file.read_text(encoding="utf-8"))
            self.metadata = payload["metadata"]
            self.songs = [
                Song(
                    **{key: value for key, value in row.items() if key not in {"charts", "titles"}},
                    titles=tuple(row["titles"]),
                    charts=tuple(Chart(**chart) for chart in row["charts"]),
                )
                for row in payload["songs"]
            ]
            self.cards = [Card(**row) for row in payload.get("cards", [])]
        except Exception as exc:
            raise DataError(f"本地缓存损坏：{self.cache_file} ({exc})") from exc
        if self.metadata.get("translation_schema") != 1:
            try:
                self.enrich_translations()
            except DataError:
                # Keep the existing cache usable if the translation table is offline.
                pass

    def search(self, query: str, limit: int = 5) -> list[Song]:
        needle = normalize(query)
        if not needle:
            return []
        if needle.isdigit():
            exact = [song for song in self.songs if song.id == int(needle)]
            if exact:
                return exact

        ranked: list[tuple[float, Song]] = []
        for song in self.songs:
            variants = [name for fields in song.localized.values() for name in fields.values()]
            phonetic = roman_to_hiragana(song.localized.get("title", {}).get("en", ""))
            choices = [normalize(title) for title in (*song.titles, song.band, *variants, phonetic) if title]
            if needle in choices:
                score = 1.0
            elif any(needle in choice for choice in choices):
                score = 0.9
            else:
                score = max((SequenceMatcher(None, needle, choice).ratio() for choice in choices), default=0)
            fuzzy_threshold = 0.75 if len(needle) <= 3 else 0.62
            if score >= fuzzy_threshold:
                ranked.append((score, song))
        ranked.sort(key=lambda pair: (-pair[0], pair[1].id))
        return [song for _, song in ranked[:limit]]

    def search_cards(self, query: str, limit: int = 8) -> list[Card]:
        alias = resolve_character_alias(query)
        needle = normalize(query)
        if not needle:
            return []
        if needle.isdigit():
            exact = [card for card in self.cards if card.id == int(needle)]
            if exact:
                return exact
        if alias:
            terms = tuple(normalize(term) for term in alias.search_terms)
            matches = [
                card for card in self.cards
                if any(term in normalize(name) for term in terms
                       for name in (card.character, *card.localized.get("character", {}).values()))
            ]
            matches.sort(key=lambda card: (-card.rarity, card.id))
            return matches[:limit]
        ranked = []
        for card in self.cards:
            variants = [name for fields in card.localized.values() for name in fields.values()]
            choices = [normalize(name) for name in (card.title, card.character, card.band, *variants)]
            if needle in choices:
                score = 1.0
            elif any(needle in choice for choice in choices):
                score = 0.9
            else:
                score = max((SequenceMatcher(None, needle, choice).ratio() for choice in choices), default=0)
            if score >= (0.75 if len(needle) <= 3 else 0.62):
                ranked.append((score, card))
        ranked.sort(key=lambda pair: (-pair[0], -pair[1].rarity, pair[1].id))
        return [card for _, card in ranked[:limit]]
