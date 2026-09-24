from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from ournotes_bot.commands import handle_command, parse_query, song_matches
from ournotes_bot.data import Card, Chart, DataError, Song, SongRepository, _rows, normalize, resolve_character_alias, roman_to_hiragana
from ournotes_bot.qq import _image_reply


class CommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo = SongRepository("https://example.invalid", Path(self.temp_dir.name) / "cache.json")
        self.repo.songs = [
            Song(
                id=100001,
                title="迷星叫",
                titles=("迷星叫", "Mayoiuta"),
                band="MyGO!!!!!",
                composer="藤原优树",
                lyricist="藤原优树",
                arranger="未知",
                start_at="2025/01/01 0:00:00",
                jacket_url="https://example.invalid/jacket.png",
                charts=(Chart("EXPERT", 27, 27.0, 818, "0001/0001_03"),),
                localized={"title": {"zh": "迷星叫", "ja": "迷星叫", "en": "Mayoiuta"},
                           "band": {"zh": "MyGO!!!!!", "ja": "MyGO!!!!!", "en": "MyGO!!!!!"}},
            )
        ]
        self.repo.metadata = {"data_version": "test", "song_count": 1}
        self.repo.cards = [Card(
            id=51, asset_id=51, title="流星に放つ叫び", character="高松 燈", band="MyGO!!!!!",
            rarity=4, card_type=4, performance=39830, technic=30495, visual=30807,
            start_at="2024-08-01", skill_name="スコアUP", full_url="https://example.invalid/full.png",
            thumbnail_url="https://example.invalid/thumb.png",
            localized={"character": {"zh": "高松 燈", "ja": "高松 燈", "en": "Tomori Takamatsu"},
                       "title": {"zh": "流星に放つ叫び", "ja": "流星に放つ叫び", "en": "A Cry to the Shooting Star"}},
        )]

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_full_width_and_case_are_normalized(self) -> None:
        self.assertEqual(normalize("ＭｙＧＯ！！！！！"), normalize("mygo!!!!!"))

    def test_query_chart_by_title(self) -> None:
        reply = handle_command("查谱 迷星叫", self.repo)
        self.assertIn("EXPERT", reply or "")
        self.assertIn("818 Notes", reply or "")

    def test_query_song_by_id(self) -> None:
        reply = handle_command("查曲 100001", self.repo)
        self.assertIn("迷星叫", reply or "")
        self.assertIn("歌曲列表", reply or "")

    def test_song_level_filter_and_combined_search(self) -> None:
        base = replace(self.repo.songs[0], charts=(Chart("EXPERT", 27, 27.5, 818, "chart"),))
        same_band = replace(base, id=100002, title="Second song", titles=("Second song",),
                            charts=(Chart("HARD", 27, 27.0, 600, "chart"),))
        other_band = replace(base, id=100003, title="Other song", titles=("Other song",),
                             band="Afterglow", localized={"band": {"zh": "Afterglow"}},
                             charts=(Chart("EXPERT", 27, 27.5, 700, "chart"),))
        self.repo.songs = [base, same_band, other_band]
        self.assertEqual([song.id for song in song_matches(self.repo, "lv27")], [100001, 100002, 100003])
        self.assertEqual(song_matches(self.repo, "27"), song_matches(self.repo, "lv27"))
        self.assertEqual(song_matches(self.repo, "２７"), song_matches(self.repo, "lv27"))
        self.assertEqual([song.id for song in song_matches(self.repo, "lv27.5")], [100001, 100003])
        self.assertEqual(song_matches(self.repo, "27.5"), song_matches(self.repo, "lv27.5"))
        self.assertEqual([song.id for song in song_matches(self.repo, "lv27.0")], [100002])
        self.assertEqual([song.id for song in song_matches(self.repo, "mygo LV 27.5")], [100001])
        self.assertEqual(song_matches(self.repo, "mygo 27.5"), song_matches(self.repo, "mygo lv27.5"))
        self.assertEqual([song.id for song in song_matches(self.repo, "100001 lv27")], [100001])
        self.assertIn("共 1首", handle_command("/查曲 mygo lv27.5", self.repo) or "")
        self.assertEqual(handle_command("/查曲 mygo 27.5", self.repo),
                         handle_command("/查曲 mygo lv27.5", self.repo).replace("mygo lv27.5", "mygo 27.5"))
        self.assertIn("1 songs", handle_command("/song mygo lv27.5", self.repo) or "")
        self.assertIn("1 songs", handle_command("/song mygo 27.5", self.repo) or "")
        self.assertIn("全1曲", handle_command("/曲 mygo lv27.5", self.repo) or "")
        self.assertIn("全1曲", handle_command("/曲 mygo 27.5", self.repo) or "")
        self.assertIn("没有找到", handle_command("/查曲 lv29", self.repo) or "")

    def test_bare_number_preserves_exact_song_id(self) -> None:
        base = self.repo.songs[0]
        self.repo.songs.append(replace(base, id=27, title="ID 27", titles=("ID 27",),
                                       localized={"title": {"zh": "ID 27"}},
                                       charts=(Chart("EXPERT", 20, 20.0, 700, "chart"),)))
        self.assertEqual([song.id for song in song_matches(self.repo, "27")], [27])
        self.assertEqual([song.id for song in song_matches(self.repo, "lv27")], [100001])
        self.assertIn("ID 27", handle_command("/查曲 27", self.repo) or "")

    def test_song_level_filter_paginates_text_and_image(self) -> None:
        base = self.repo.songs[0]
        self.repo.songs = [replace(base, id=100001 + index, title=f"Song {index}",
                                   charts=(Chart("EXPERT", 27 if index % 2 == 0 else 26,
                                                 27.5 if index % 2 == 0 else 26.5, 800, "chart"),))
                           for index in range(35)]
        self.assertEqual(parse_query("/查曲 lv27 页2"), ("songs", "lv27", 2))
        self.assertEqual(parse_query("/查曲 27 页2"), ("songs", "27", 2))
        first = handle_command("/查曲 lv27", self.repo) or ""
        second = handle_command("/查曲 lv27 页2", self.repo) or ""
        plain = handle_command("/查曲 27 页2", self.repo) or ""
        self.assertIn("共 18首", first)
        self.assertIn("/查曲 lv27 页2", first)
        self.assertIn("100035", second)
        self.assertNotIn("100034", second)
        self.assertIn("100035", plain)
        self.assertIn("共 18首", plain)
        with patch("ournotes_bot.qq.render_song_list", return_value=b"image") as render:
            self.assertEqual(_image_reply("/查曲 27 页2", self.repo), b"image")
            self.assertEqual(len(render.call_args.args[0]), 2)
            self.assertIn("共 18首", render.call_args.args[3])

    def test_slash_chart_difficulty(self) -> None:
        self.assertEqual(parse_query("/查谱面 100001 ex"), ("chart", "100001", "EXPERT"))
        self.assertIn("818 Notes", handle_command("/查谱面 100001 ex", self.repo) or "")

    def test_bare_panel_commands_explain_required_arguments(self) -> None:
        for command, example in (("/查谱面", "/查谱面 100001"), ("/查曲", "/查曲 迷星叫"), ("/查卡", "/查卡 51")):
            with self.subTest(command=command):
                self.assertIn(example, handle_command(command, self.repo) or "")

    def test_joined_argument_and_typo_get_suggestions(self) -> None:
        self.assertIn("/查谱面 1", handle_command("查谱面1", self.repo) or "")
        self.assertIn("/查谱面 100001", handle_command("查普面 100001", self.repo) or "")

    def test_nearby_song_title_gets_candidate(self) -> None:
        reply = handle_command("/查曲 迷星吚", self.repo) or ""
        self.assertIn("迷星叫", reply)
        self.assertIn("用法", reply)

    def test_card_id_and_simplified_name(self) -> None:
        self.assertIn("流星に放つ叫び", handle_command("查卡面 51", self.repo) or "")
        self.assertIn("高松 燈", handle_command("查卡面 高松灯", self.repo) or "")

    def test_unavailable_commands_do_not_fall_through_to_card_search(self) -> None:
        for message in ("/查活动", "查活动 1", "/查卡池", "查卡池 51", "/ycx", "ycx 1000", "预测线"):
            with self.subTest(message=message):
                self.assertEqual(handle_command(message, self.repo), "该功能暂未上线")

    def test_help_lists_unavailable_features(self) -> None:
        help_text = handle_command("/帮助", self.repo) or ""
        for command in ("/查活动", "/查卡池", "/ycx"):
            self.assertIn(command, help_text)

    def test_unknown_chat_is_ignored(self) -> None:
        self.assertIsNone(handle_command("今天吃什么", self.repo))

    def test_unrelated_romanization_does_not_false_match(self) -> None:
        reply = handle_command("查曲 completely-unrelated", self.repo)
        self.assertIn("没有找到", reply or "")

    def test_names_cross_languages_while_chinese_is_default(self) -> None:
        self.assertIn("迷星叫", handle_command("/查曲 Mayoiuta", self.repo) or "")
        self.assertIn("Mayoiuta", handle_command("/song 迷星叫", self.repo) or "")
        self.assertIn("迷星叫", handle_command("/曲 まよいうた", self.repo) or "")
        self.assertIn("楽曲一覧", handle_command("/曲 Mayoiuta", self.repo) or "")
        self.assertIn("高松 燈", handle_command("/查卡 tomori", self.repo) or "")
        self.assertIn("Tomori Takamatsu", handle_command("/card ともり", self.repo) or "")

    def test_localized_help_and_chart(self) -> None:
        self.assertIn("Our Notes commands", handle_command("/help", self.repo) or "")
        self.assertIn("コマンド", handle_command("/ヘルプ", self.repo) or "")
        self.assertIn("Chart", handle_command("/chart まよいうた EXPERT", self.repo) or "")
        self.assertIn("譜面", handle_command("/譜面 Mayoiuta エキスパート", self.repo) or "")
        self.assertIn("Chinese is the default", handle_command("/language", self.repo) or "")

    def test_upstream_underscore_columns_and_phonetics(self) -> None:
        self.assertEqual(_rows({"_allData": [{"_id": "x", "_english": "Mayoiuta"}]}),
                         [{"id": "x", "english": "Mayoiuta"}])
        self.assertEqual(roman_to_hiragana("Mayoiuta"), "まよいうた")
        self.assertEqual(normalize("マヨイウタ"), normalize("まよいうた"))
        self.assertIsNotNone(resolve_character_alias("ともり"))
        self.assertIsNotNone(resolve_character_alias("さきこ"))

    def test_image_reply_uses_command_language(self) -> None:
        with patch("ournotes_bot.qq.render_song_list", return_value=b"image") as render:
            self.assertEqual(_image_reply("/song 迷星叫", self.repo), b"image")
            self.assertEqual(render.call_args.args[2], "en")
            self.assertEqual(_image_reply("/曲 Mayoiuta", self.repo), b"image")
            self.assertEqual(render.call_args.args[2], "ja")

    def test_song_and_card_search_pages_cover_all_matches(self) -> None:
        self.repo.songs = [replace(self.repo.songs[0], id=100001 + index, title=f"Song {index}")
                           for index in range(23)]
        self.repo.cards = [replace(self.repo.cards[0], id=51 + index) for index in range(20)]
        self.assertEqual(parse_query("/查曲 mygo 页2"), ("songs", "mygo", 2))
        self.assertEqual(parse_query("/song mygo page 2"), ("songs", "mygo", 2))
        self.assertEqual(parse_query("/カード mygo ページ2"), ("cards", "mygo", 2))
        self.assertIn("共 23首", handle_command("/查曲 mygo", self.repo) or "")
        self.assertIn("100023", handle_command("/查曲 mygo 页2", self.repo) or "")
        self.assertIn("70", handle_command("/查卡 mygo 页2", self.repo) or "")
        self.assertIn("页码超出范围", handle_command("/查曲 mygo 页3", self.repo) or "")
        with patch("ournotes_bot.qq.render_song_list", return_value=b"image") as render:
            self.assertEqual(_image_reply("/查曲 mygo 页2", self.repo), b"image")
            self.assertEqual(len(render.call_args.args[0]), 7)
            self.assertIn("共 23首", render.call_args.args[3])
        with patch("ournotes_bot.qq.render_card_list", return_value=b"image") as render:
            self.assertEqual(_image_reply("/查卡 mygo 页2", self.repo), b"image")
            self.assertEqual(len(render.call_args.args[0]), 4)

    def test_song_builder_uses_multilingual_master_text(self) -> None:
        tables = {
            "MasterText": [{"id": "Music_Tilte_100001", "simplifiedChinese": "迷星叫",
                            "japanese": "迷星叫", "english": "Mayoiuta"}],
            "MasterLiveMusic": [{"id": 100001, "titleTextID": "obsolete", "bandIDs": [],
                                 "jacketAssetName": "sample"}],
            "MasterLiveMusicScore": [], "MasterBand": [],
        }
        song = self.repo._build_songs(tables, {"Image/Jacket/sample": "Image/Jacket/sample/sample__00000.png"})[0]
        self.assertEqual(song.localized["title"]["en"], "Mayoiuta")
        self.assertIn("Mayoiuta", song.titles)

    def test_refresh_pins_master_tables_to_manifest_and_keeps_complete_cache(self) -> None:
        version = "snapshot-1"
        tables = {
            "MasterLiveMusic": [{"id": 100001, "titleTextID": "song", "bandIDs": [], "jacketAssetName": "a"}],
            "MasterLiveMusicScore": [],
            "MasterText": [{"id": "song", "simplifiedChinese": "测试曲"}],
            "MasterBand": [],
            "MasterMemberCard": [{"id": 51, "assetID": 51}, {"id": 52, "assetID": 52}],
            "MasterCharacter": [],
            "MasterLiveSkill": [],
        }
        requested = []

        def fetch(url: str):
            requested.append(url)
            if url.endswith("/version/latest.json"):
                return {"version": version, "fetchedAt": "today"}
            if url.endswith("/src/lib/assets/generated/images.json"):
                return {
                    "Image/Jacket/a": "Image/Jacket/a/a__00000.png",
                    **{f"MemberCard/{card_id}/{kind}": f"MemberCard/{card_id}/{kind}/{kind}__00000.png"
                       for card_id in (51, 52) for kind in ("member_full", "member_thumbnail")},
                }
            name = url.split("/master/", 1)[1].split(".json", 1)[0]
            return {"_allData": tables[name]}

        with patch("ournotes_bot.data._fetch_json", side_effect=fetch):
            self.repo.refresh()
        self.assertEqual((len(self.repo.songs), len(self.repo.cards)), (1, 2))
        self.assertEqual(self.repo.metadata["data_version"], version)
        self.assertEqual(self.repo.songs[0].jacket_url,
                         "https://storage.bdon.moe/moenotes/Image/Jacket/a/a__00000.png")
        self.assertEqual(len([url for url in requested if f"?v={version}" in url]), 7)
        self.assertEqual(self.repo.cards[0].full_url,
                         "https://storage.bdon.moe/moenotes/MemberCard/51/member_full/member_full__00000.png")

        old_cache = self.repo.cache_file.read_bytes()
        tables["MasterMemberCard"] = [{"id": 51, "assetID": 51}]
        with patch("ournotes_bot.data._fetch_json", side_effect=fetch):
            with self.assertRaises(DataError):
                self.repo.refresh()
        self.assertEqual(self.repo.cache_file.read_bytes(), old_cache)

    def test_missing_release_card_art_does_not_replace_cache(self) -> None:
        tables = {"MasterMemberCard": [{"id": 11, "assetID": 11}], "MasterText": [],
                  "MasterCharacter": [], "MasterBand": [], "MasterLiveSkill": []}
        with self.assertRaises(DataError):
            self.repo._build_cards(tables, {})


if __name__ == "__main__":
    unittest.main()
