from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from ournotes_bot.chart_data import ChartDataError, chart_url, load_chart_score
from ournotes_bot.data import Chart, Song
from ournotes_bot.visuals import render_chart


SCORE = {
    "meta": {"version": 100},
    "score": {
        "events": {"bpm": [{"t": 0, "bpm": 190}], "sig": [{"t": 0, "sig": [4, 4]}]},
        "notes": [
            {"t": 9600, "pos": 6, "size": 6},
            {"type": "flick", "t": 10080, "pos": 12, "size": 6, "dir": "right"},
            {"type": "long", "node": [
                {"t": 10560, "pos": 6, "size": 6},
                {"t": 11520, "pos": 12, "size": 6},
            ]},
        ],
    },
}


class ChartDataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.chart = Chart("EXPERT", 25, 25.0, 768, "0001/0001_03")

    def test_public_score_url_and_cache_fallback(self) -> None:
        self.assertEqual(chart_url(self.chart),
                         "https://storage.bdon.moe/moenotes/Live/MusicScore/0001/0001_03/0001_03.json")
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            with patch("ournotes_bot.chart_data.urlopen", return_value=io.BytesIO(json.dumps(SCORE).encode())) as fetch:
                self.assertEqual(load_chart_score(self.chart, cache)["notes"], SCORE["score"]["notes"])
                self.assertEqual(fetch.call_count, 1)
            with patch("ournotes_bot.chart_data.urlopen", side_effect=AssertionError("cache was not used")):
                self.assertEqual(load_chart_score(self.chart, cache)["notes"], SCORE["score"]["notes"])
            os.utime(cache / "0001_0001_03.json", (0, 0))
            with patch("ournotes_bot.chart_data.urlopen", side_effect=OSError("offline")):
                self.assertEqual(load_chart_score(self.chart, cache)["notes"], SCORE["score"]["notes"])

    def test_invalid_or_unrecognized_score_is_rejected(self) -> None:
        with self.assertRaises(ChartDataError):
            chart_url(Chart("EXPERT", 25, 25.0, 768, "../private"))
        with tempfile.TemporaryDirectory() as directory:
            with patch("ournotes_bot.chart_data.urlopen", return_value=io.BytesIO(b'{"score":{"notes":[]}}')):
                with self.assertRaises(ChartDataError):
                    load_chart_score(self.chart, Path(directory))

    def test_rendered_score_is_an_image_with_note_timeline(self) -> None:
        song = Song(100001, "Test", ("Test",), "MyGO!!!!!", "Composer", "Lyricist", "Arranger",
                    "2026-01-01", "https://example.invalid/jacket.png", (self.chart,))
        with patch("ournotes_bot.visuals._asset", return_value=None):
            result = render_chart(song, (self.chart,), "zh", SCORE["score"], "EXPERT")
        with Image.open(io.BytesIO(result)) as image:
            self.assertEqual(image.width, 900)
            self.assertGreater(image.height, 2000)
            self.assertNotEqual(image.getpixel((100, 1000)), image.getpixel((100, 600)))


if __name__ == "__main__":
    unittest.main()
