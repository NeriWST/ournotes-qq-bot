# GitHub 发布核对

维护者：Bilibili @Adeliae。项目为非官方、非商业社区查询工具。

## 仓库内容

- `src/ournotes_bot/`：本项目代码，适用根目录 MIT 许可证；官方 QQ 机器人是唯一维护的消息接入方式。
- `tests/`：本项目测试代码，适用同一许可证。
- `README.md`、`LOCAL_QQ_TEST.md`、`deploy/README.md`：使用与部署说明，不包含真实凭据。
- `.env.example`：仅含空白凭据字段和公开的数据源示例；真实配置应保存在未跟踪的 `.env`。
- `data/.gitkeep`：只保留空目录；下载的 MasterData、封面和卡面不上传。
- `THIRD_PARTY.md`：列明游戏内容、上游数据、QQ 平台和依赖包的独立权利范围。

## 发布前检查

- [x] 版权署名与 README 维护者名称均为 Bilibili @Adeliae。
- [x] README 和第三方说明标明非官方、非商业运营，以及游戏素材不受 MIT 授权。
- [x] 私人 QQ / NapCat 接入及部署示例已从公开源码中移除。
- [x] 仅发布项目源码、测试、说明和配置模板，不附带运行缓存、游戏图片或 QQ 登录状态。
- [x] 项目测试通过；发布时仍应查看 `git status --short` 与 `git diff --cached --name-only`。
- [x] 在 GitHub 创建空的公开仓库 `NeriWST/ournotes-qq-bot`，核对名称与简介；仓库头像和截图暂无需附加。
- [x] 首次推送后核对 GitHub 上的 LICENSE、README 和实际文件列表：25 个预期文件均可读取，未发现凭据或运行数据。

**许可边界：**本项目的非商业运营声明只描述维护者对游戏内容的使用方式；MIT 仍允许他人商业复用本项目代码。游戏素材、数据及其使用要求由相应权利方决定，使用者需自行遵守。
