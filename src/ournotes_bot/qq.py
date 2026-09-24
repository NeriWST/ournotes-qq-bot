from __future__ import annotations

import asyncio
import base64
import logging

from botpy.http import Route

from .commands import handle_command, locale_for, page_notice, page_slice, parse_query, song_matches
from .data import SongRepository
from .visuals import render_card, render_card_list, render_chart, render_song_list


logger = logging.getLogger(__name__)


def _image_reply(content: str, repository: SongRepository) -> bytes | None:
    parsed = parse_query(content)
    if not parsed:
        return None
    kind, query, difficulty = parsed
    locale = locale_for(content)
    if kind == "songs":
        songs = song_matches(repository, query)
        visible = page_slice(songs, int(difficulty))
        return render_song_list(visible, query, locale, page_notice(kind, query, int(difficulty), len(songs), locale)) if visible else None
    if kind == "chart":
        songs = repository.search(query, limit=1)
        if not songs:
            return None
        charts = tuple(chart for chart in songs[0].charts if difficulty is None or chart.difficulty == difficulty)
        return render_chart(songs[0], charts, locale)
    if kind == "cards":
        cards = repository.search_cards(query, limit=len(repository.cards))
        if not cards:
            return None
        if query.isdigit() and cards[0].id == int(query):
            return render_card(cards[0], locale)
        visible = page_slice(cards, int(difficulty))
        return render_card_list(visible, query, locale, page_notice(kind, query, int(difficulty), len(cards), locale)) if visible else None
    return None


async def _upload_image(api, target_id: str, image: bytes, group: bool):
    path = "/v2/groups/{target_id}/files" if group else "/v2/users/{target_id}/files"
    result = await api._http.request(
        Route("POST", path, target_id=target_id),
        json={"file_type": 1, "file_data": base64.b64encode(image).decode("ascii"), "srv_send_msg": False},
    )
    if not isinstance(result, dict) or not result.get("file_info"):
        raise RuntimeError("QQ 图片上传未返回 file_info")
    return {"file_info": result["file_info"]}


def run_bot(app_id: str, app_secret: str, repository: SongRepository) -> None:
    try:
        import botpy
        from botpy.message import C2CMessage, GroupMessage
    except ImportError as exc:
        raise RuntimeError("缺少 qq-botpy，请先运行 pip install -r requirements.txt") from exc

    class OurNotesClient(botpy.Client):
        async def on_ready(self) -> None:
            logger.info("机器人 %s 已上线", self.robot.name)

        async def _reply_group(self, message: GroupMessage) -> None:
            reply = handle_command(message.content, repository)
            if not reply:
                return
            try:
                image = await asyncio.to_thread(_image_reply, message.content, repository)
                if image:
                    media = await _upload_image(message._api, message.group_openid, image, group=True)
                    await message._api.post_group_message(
                        group_openid=message.group_openid, msg_type=7, msg_id=message.id, media=media,
                    )
                    return
            except Exception:
                logger.exception("群聊图片回复失败，改用文字")
            await message._api.post_group_message(
                group_openid=message.group_openid,
                msg_type=0,
                msg_id=message.id,
                content=reply,
            )

        async def on_group_at_message_create(self, message: GroupMessage) -> None:
            await self._reply_group(message)

        async def on_c2c_message_create(self, message: C2CMessage) -> None:
            reply = handle_command(message.content, repository)
            if not reply:
                return
            try:
                image = await asyncio.to_thread(_image_reply, message.content, repository)
                if image:
                    media = await _upload_image(message._api, message.author.user_openid, image, group=False)
                    await message._api.post_c2c_message(
                        openid=message.author.user_openid, msg_type=7, msg_id=message.id, media=media,
                    )
                    return
            except Exception:
                logger.exception("单聊图片回复失败，改用文字")
            await message._api.post_c2c_message(
                openid=message.author.user_openid,
                msg_type=0,
                msg_id=message.id,
                content=reply,
            )

    async def refresh_loop() -> None:
        while True:
            await asyncio.sleep(6 * 3600)
            try:
                await asyncio.to_thread(repository.refresh)
                logger.info("Ournotes 数据刷新成功，共 %d 首曲目", len(repository.songs))
            except Exception:
                logger.exception("刷新失败，继续使用现有缓存")

    class ClientWithRefresh(OurNotesClient):
        async def on_ready(self) -> None:
            await super().on_ready()
            if not hasattr(self, "_refresh_task"):
                self._refresh_task = asyncio.create_task(refresh_loop())

    intents = botpy.Intents(public_messages=True)
    ClientWithRefresh(intents=intents).run(appid=app_id, secret=app_secret)
