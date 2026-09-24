from __future__ import annotations

import asyncio
import base64
import unittest

from ournotes_bot.qq import _upload_image


class FakeHttp:
    def __init__(self) -> None:
        self.route = None
        self.payload = None

    async def request(self, route, **kwargs):
        self.route = route
        self.payload = kwargs["json"]
        return {"file_info": "uploaded-image"}


class FakeApi:
    def __init__(self) -> None:
        self._http = FakeHttp()


class MediaTests(unittest.TestCase):
    def test_local_image_is_uploaded_for_group(self) -> None:
        api = FakeApi()
        media = asyncio.run(_upload_image(api, "group-123", b"\x89PNG", group=True))
        self.assertEqual(api._http.route.url, "https://api.sgroup.qq.com/v2/groups/group-123/files")
        self.assertEqual(base64.b64decode(api._http.payload["file_data"]), b"\x89PNG")
        self.assertEqual(media, {"file_info": "uploaded-image"})
