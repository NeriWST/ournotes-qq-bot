# Ournotes QQ 查询机器人原型

面向《BanG Dream! Our Notes》的非官方社区查询机器人原型，使用 QQ 官方机器人接口。项目不包含任何 AppSecret、QQ 登录态或游戏素材。

由于发布者相关经验不足，本项目最初含有大量 Vibe Coding 代码，恳请有经验的开发者指导修改，并欢迎大家提出Issue.

本项目以非商业社区工具的方式运营，不以游戏素材牟利；游戏素材不随本仓库分发。项目与游戏版权方、QQ 平台及数据服务均无官方关联。

目前支持：

- `/查曲 [歌名或ID] [lv等级] [页N]`：带封面的歌曲列表图，每页 16 首；可按谱面等级筛选（例如 `/查曲 lv27`、`/查曲 mygo lv27 页2`）。`lv27` 匹配整数等级 27，包括显示为 27.5 的谱面；`lv27.5` 仅匹配显示等级 27.5。
- `/查谱面 <歌名或ID> [难度]`：封面、谱面等级与 Note 数（例如 `/查谱面 100001 EXPERT`）
- `/查卡 <角色名或卡牌ID> [页N]`：卡牌列表每页 16 张，显示总数和下一页指令；输入卡牌 ID 可看原画、综合力和技能名称（仍兼容 `查卡面`）
- `/查卡 skk`、`/查卡 mtm` 等：可用角色缩写查卡；`/查缩写 <缩写>` 查看对应角色。别名覆盖 Our Notes 的 25 名角色；暂无卡牌数据时会明确提示
- `/查活动`、`/查卡池`、`/ycx`（预测线）：已接入指令与快捷入口；目前上游没有可用数据，回复“该功能暂未上线”
- `数据状态`：当前数据版本、曲目数和上游时间
- 群内 `@机器人` 查询，以及单聊查询
- 本地缓存、远端异常时使用旧缓存、每 6 小时自动刷新
- 中日英名称互通搜索、罗马字对应的假名搜索，以及全角字符归一化
- 中／日／英回复和查询图片本地化；中文指令默认显示中文，英文或日文指令显示对应语言
- 单聊自定义菜单，以及单聊和群聊指令面板
- 点击无参数指令会显示用法；拼错指令或漏输空格时会提示最接近的正确写法

## 数据来源

原型默认读取社区维护的静态 MasterData；[MoeNotes](https://github.com/StarMoe-org/moenotes) 也使用同一数据入口。本机器人直接读取该入口，不抓取 MoeNotes 页面或复制其代码：

```text
https://metadata.bdon.moe
```

这不是 Bushiroad 或 bilibili 提供的正式公开 API。同步时按上游版本获取歌曲、谱面、成员卡、角色、乐队、文本和技能表，并读取 MoeNotes 公开的图片路径清单以定位歌曲封面和卡图；网络异常会重试，缺表、缺图或同版本条数回退时保留旧缓存。仓库不包含下载的数据、封面或卡面；运行时访问上游服务并展示图片，部署者应遵守上游及素材权利方的适用要求。数据更新时间可用 `数据状态` 检查，第三方权利范围见 [THIRD_PARTY.md](THIRD_PARTY.md)。

## 本地运行

需要 Python 3.10 或更新版本。

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .

# 下载数据并验证查询；这两步不需要 QQ 凭证
ournotes-bot sync
ournotes-bot query 查谱 迷星叫
ournotes-bot repl
```

不安装项目也可以这样运行：

```powershell
$env:PYTHONPATH = "src"
python -m ournotes_bot.main sync
python -m ournotes_bot.main query 查曲 100001
python -m ournotes_bot.main repl
```

`repl` 是不连接 QQ 的本地交互测试台，可以连续输入机器人指令；输入 `exit` 退出。

## 多语言查询

所有指令都可使用数据源已收录的简体中文、英文或日文名称查询，曲名还支持可由上游英文罗马字推导出的假名读音。回复语言由**指令**决定，默认中文，不会因为输入了英文或假名就改变回复语言：

| 中文（默认） | English | 日本語 |
| --- | --- | --- |
| `/查曲 迷星叫` | `/song Mayoiuta` | `/曲 まよいうた` |
| `/查谱面 100001` | `/chart 100001 EXPERT` | `/譜面 100001 エキスパート` |
| `/查卡 祥子` | `/card sakiko` | `/カード 祥子` |
| `/帮助` | `/help` | `/ヘルプ` |

发送 `/语言`、`/language` 或 `/言語` 可查看语言说明。若上游没有某项日文或英文文本，该字段会回退到中文；不会自动编造译名。更新旧缓存请运行 `ournotes-bot sync`。

## 接入 QQ

Windows 本地联调可直接按照 [LOCAL_QQ_TEST.md](LOCAL_QQ_TEST.md) 操作，或运行项目内的 `setup-local.ps1` 和 `start-bot.ps1`。

1. 在 [QQ 开放平台](https://q.qq.com/) 创建机器人，取得 `AppID` 与 `AppSecret`。
2. 在机器人后台配置群聊与单聊事件权限。原型监听 `GROUP_AT_MESSAGE_CREATE` 和 `C2C_MESSAGE_CREATE`。
3. 将 `.env.example` 复制为 `.env`，填写：

```dotenv
QQ_APP_ID=你的AppID
QQ_APP_SECRET=你的AppSecret
```

4. 启动：

```powershell
ournotes-bot bot
```

安装 QQ 快捷入口：

```powershell
ournotes-bot setup-menu
```

安装命令会保留既有单聊菜单项，添加 `Our Notes` 和 `活动与卡池` 两组子菜单；单聊和群聊面板会按备注复用或更新。修改 QQ 菜单不需要重启机器人，修改程序代码需要重启。

凭证只放在服务器的 `.env` 中，不要提交到 Git。

服务器部署可参照 [deploy/README.md](deploy/README.md)。本项目只维护 QQ 官方机器人接入。

## 测试

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

## 当前边界

- 当前上游仍可能是测试期数据，开服后的 ID、字段和曲目数量可能变化。
- 社区数据源可能暂时不可用；首次同步失败时应稍后重试。已有缓存时，机器人会继续使用旧缓存。
- 没有接入玩家账户和成绩。未发现可确认的官方玩家数据接口。
- 谱面 MasterData 提供等级、物量及 `musicScoreTextFileName`，当前静态资产源尚未提供可解析的逐条音符谱面文件，因此无法生成类似 Tsugu 的实际谱面预览；图片中会明确标注这一点。
- 当前卡面图使用 `MasterMemberCard` 和 MoeNotes 图片路径清单定位社区静态资产；若清单未收录某张卡，数据同步会保留既有缓存。卡池、活动、觉醒前后对照等关系仍需相应数据源，当前图不展示这些字段。
- 活动、卡池和预测线尚未实现。相应指令目前只返回“该功能暂未上线”，不会把 Bang Dream 旧游戏的榜线当作 Our Notes 数据。
- 部署多个实例时应把缓存同步任务改成独立定时任务，避免重复拉取。

## 许可与公开仓库

本仓库自行编写的代码由 Bilibili @Adeliae 以 [MIT License](LICENSE) 授权。游戏内容、上游数据和第三方软件不属于此许可范围，详见 [THIRD_PARTY.md](THIRD_PARTY.md)。本项目的非商业运营声明不改变 MIT 对代码的授权范围。

提交前检查 Git 暂存区。`.env`、虚拟环境、日志、下载缓存、登录二维码和 QQ 会话均应保持在仓库之外；若凭据曾公开，立即在对应平台轮换。
