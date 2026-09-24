# 在本机连接 QQ 测试

本项目使用 QQ 官方机器人 API 的 WebSocket 长连接。程序从本机主动连接 QQ，因此本地测试无需域名、HTTPS 和路由器端口映射；运行期间电脑不能休眠或断网。

## 1. 创建 QQ 测试机器人

1. 登录 [QQ 开放平台](https://q.qq.com/)，创建机器人。
2. 在机器人的“开发设置”中保存 `AppID` 和 `AppSecret`。
3. 在权限或功能配置中启用群聊与单聊消息能力。代码监听 `GROUP_AT_MESSAGE_CREATE` 和 `C2C_MESSAGE_CREATE`。
4. 如果控制台要求 IP 白名单，加入当前网络的公网出口 IP。PowerShell 可执行：

   ```powershell
   Invoke-RestMethod https://api.ipify.org
   ```

   应填写命令返回的公网地址，不要填写 `192.168.x.x`。家庭宽带公网出口可能变化，连接突然失效时重新检查。

5. 在“沙箱配置”或“测试人员”中加入自己的 QQ 号。不同主体和机器人权限显示的测试场景可能不同：有测试群选项时配置一个自己管理的群；没有时先用机器人单聊完成联调。

## 2. 准备本地环境

在项目目录打开 PowerShell：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup-local.ps1
notepad .env
```

在 `.env` 中填写：

```dotenv
QQ_APP_ID=开放平台中的AppID
QQ_APP_SECRET=开放平台中的AppSecret
OURNOTES_DATA_BASE=https://metadata.bdon.moe
OURNOTES_CACHE_FILE=data/ournotes-cache.json
OURNOTES_CACHE_TTL_HOURS=6
```

不要把 `.env` 截图、上传或提交到 Git。项目的 `.gitignore` 已排除该文件。

## 3. 启动机器人

```powershell
.\start-bot.ps1
```

看到类似“机器人 xxx 已上线”的日志后保持终端开启。首次设置快捷按钮可另开 PowerShell 执行：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m ournotes_bot.main setup-menu
```

## 4. 在 QQ 中验证

单聊机器人发送：

```text
帮助
/查曲 迷星叫
/查谱面 100001 EXPERT
/查卡 51
/查卡 高松灯
/查活动
/查卡池
/ycx
数据状态
```

测试群中需要明确 `@机器人`：

```text
@你的机器人 查谱面 100001 EXPERT
```

预期图片回复包含 `EXPERT Lv.27 · 818 Notes`。`/查曲` 返回歌曲列表图，`/查卡 51` 返回卡牌原画和数值图。`/查活动`、`/查卡池`、`/ycx` 当前会回复“该功能暂未上线”。输入 `/查卡`、`/查谱面` 等不带参数的指令时，会收到用法说明；输入 `查谱面1` 会收到补空格提示。

## 5. 常见问题

### 启动后立即鉴权失败

重新核对 `QQ_APP_ID`、`QQ_APP_SECRET`。修改 `.env` 后需要重启程序。

### 日志显示来源 IP 不在白名单

重新执行 `Invoke-RestMethod https://api.ipify.org`，把结果添加到开放平台白名单，然后重启。

### 机器人上线但不回复

依次检查：

1. 发送消息的 QQ 号是否已加入测试人员。
2. 对话或群是否处于机器人沙箱范围。
3. 群里是否真正选择并 @ 了机器人。
4. 是否开通群聊与单聊消息事件权限。
5. 本地终端是否仍在运行，以及电脑是否休眠。

### 私聊正常，群聊不工作

通常是机器人尚未获得群聊权限，或者当前账号的沙箱没有开放测试群。先保留私聊测试；群聊能力需要按照开放平台控制台当前显示的申请或审核流程开通。
