"""Install discoverable QQ commands without removing unrelated menu entries."""

from __future__ import annotations

import aiohttp
from botpy.robot import Token


BASE = "https://api.sgroup.qq.com"
MENU_NAME = "Our Notes"
MORE_MENU_NAME = "活动与卡池"
MENU_ITEMS = [
    {"type": "send_message", "name": "查谱面", "send_message": "/查谱面 "},
    {"type": "send_message", "name": "查曲", "send_message": "/查曲 "},
    {"type": "send_message", "name": "查卡", "send_message": "/查卡 "},
    {"type": "send_message", "name": "数据状态", "send_message": "/数据状态"},
    {"type": "send_message", "name": "帮助", "send_message": "/帮助"},
]
MORE_MENU_ITEMS = [
    {"type": "send_message", "name": "查活动", "send_message": "/查活动"},
    {"type": "send_message", "name": "查卡池", "send_message": "/查卡池"},
    {"type": "send_message", "name": "预测线", "send_message": "/ycx"},
]
PANEL_ITEMS = [
    # QQ stores the command name without '/', then adds the slash in the client UI.
    {"type": "command", "name": "查谱面", "desc": "按歌曲 ID 查询谱面资料"},
    {"type": "command", "name": "查曲", "desc": "按歌名、ID 或 lv 等级查询歌曲"},
    {"type": "command", "name": "查卡", "desc": "按角色或卡牌 ID 查询"},
    {"type": "command", "name": "查活动", "desc": "活动资料暂未上线"},
    {"type": "command", "name": "查卡池", "desc": "卡池资料暂未上线"},
    {"type": "command", "name": "ycx", "desc": "预测线暂未上线"},
    {"type": "command", "name": "数据状态", "desc": "查看当前数据版本"},
    {"type": "command", "name": "帮助", "desc": "查看指令说明与示例"},
]


async def setup_menu(app_id: str, app_secret: str) -> list[str]:
    token = Token(app_id, app_secret)
    await token.update_access_token()
    headers = {"Authorization": token.get_string()}
    messages = []
    async with aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as session:
        async def api(method: str, path: str, **kwargs):
            async with session.request(method, BASE + path, **kwargs) as response:
                body = await response.json(content_type=None)
                if response.status >= 400:
                    raise RuntimeError(f"QQ {method} {path}: HTTP {response.status}: {body}")
                return body

        menu = await api("GET", "/v2/menu")
        items = list((menu.get("menu") or {}).get("items") or [])
        changed = False
        for name, sub_items in ((MENU_NAME, MENU_ITEMS), (MORE_MENU_NAME, MORE_MENU_ITEMS)):
            ours = {"type": "menu", "name": name, "sub_menu_items": sub_items}
            existing = next((i for i, item in enumerate(items) if item.get("name") == name), None)
            if existing is not None:
                current_menu = items[existing]
                if current_menu.get("type") != "menu" or current_menu.get("sub_menu_items") != sub_items:
                    items[existing] = ours
                    changed = True
            elif len(items) < 10:
                items.append(ours)
                changed = True
            else:
                messages.append(f"单聊菜单已达 10 项上限，未添加{name}")
        if changed:
            await api("PUT", "/v2/menu", json={"menu": {"items": items}})
            messages.append("单聊菜单已更新")
        else:
            messages.append("单聊菜单已存在")

        for scope in ("c2c", "group"):
            listing = await api("GET", "/v2/panels", params={"scope": scope, "limit": 50})
            records = listing.get("records") or []
            remark = f"ournotes-qq-bot-{scope}"
            current = next((row for row in records if (row.get("panel") or {}).get("remark") == remark), None)
            panel = {"items": PANEL_ITEMS, "remark": remark}
            if current:
                if current.get("panel", {}).get("items") != PANEL_ITEMS:
                    await api("PUT", f"/v2/panels/{current['panel_id']}", json={"panel": panel})
                    messages.append(f"{scope} 指令面板已更新")
                else:
                    messages.append(f"{scope} 指令面板已存在")
            else:
                await api("POST", "/v2/panels", json={"scope": scope, "target_type": "all", "panel": panel})
                messages.append(f"{scope} 指令面板已创建")
    return messages
