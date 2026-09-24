# 部署示例

这些文件仅是模板，不包含登录信息、服务器地址或 QQ 会话。先完成根目录 README 的本地测试，再按环境调整路径和用户。

在服务器部署 Python 项目，创建仅本机可读的 `.env`，填写自己的 `QQ_APP_ID` 和 `QQ_APP_SECRET`，然后运行 `ournotes-bot bot`。可用进程管理器保持运行。切勿把 `.env`、日志或缓存加入 Git。

代码更新后重启官方机器人进程。若需更新 QQ 指令面板，另运行 `ournotes-bot setup-menu`；修改数据源后运行 `ournotes-bot sync` 重建缓存。
