# 立创元件助手 · AD24

双击项目目录里的 **Start.cmd** 打开独立窗口。当前新版也可直接双击 dist/LCSC-AD24-Assistant-0.2.2.exe；窗口标题显示 0.2.2。旧版进程不会因更新被强制关闭，请使用前先退出旧窗口。

## 使用

1. 输入立创料号（如 C25804）、厂家型号（如 NE555DR），或英文关键词（如 capacitor），按回车搜索。
2. 选择一行，等待符号与封装预览。只有模型完整、引脚与焊盘编号匹配时才能导出。
3. **生成 AD 库**：将 SchLib / PcbLib 保存到 data/libraries/料号/唯一目录，不覆盖以前的库。
4. **导入 AD 并放置**：先在 AD24 中打开并激活目标 SchDoc，再点击。AD 收到请求后安装两份库并进入交互放置；点击落下器件，Esc 结束。
5. 状态栏显示 AD 回执。只有 AD 确认原理图器件数量增加才显示已放置。没有回执表示尚未验证成功。

默认 AD 路径 E:\AD24\X2.EXE，可用“设置 AD 路径”调整（当前会话有效）。

## AD 没有响应

自动唤起依赖 AD 的命令行 RunScript 接口。不要把“已发送请求”当成已导入成功，也不要重复点击运行。

如果提示 **Another script executing now**：

1. 关闭 AD 的错误提示框，在脚本编辑界面选择 **运行 → 停止**，退出之前暂停的脚本。此操作停止脚本，不关闭你的工程。
2. 关闭旧版助手，重新从 Start.cmd 打开新版。若新版还显示等待，在确认 AD 脚本已停止后点击“解除导入等待”。
3. 激活目标 SchDoc，再点击一次“导入 AD 并放置”。放置期间点击原理图，Esc 结束。

新版通过一个共享导入锁阻止重复请求，回执改为独立状态标记文件，助手只检查文件存在性，避免和 AD 写入冲突。等待不会自动超时重试，因为旧脚本可能仍在 AD 中运行。

如果自动唤起没有回执，先停止 AD 中旧脚本。确需手工运行时，再在 AD 的 File → Run Script 中浏览 data/requests/相应请求目录的 Import_*.PrjScr，运行 ImportPart；运行期间不要再发送自动请求。

配套的 ad/Launcher.PrjScr 可从 AD 启动独立窗口：File → Run Script → 浏览此文件 → 运行 OpenAssistant。常用时可在 AD Preferences → Scripting System → Global Projects 加入该工程，再按 AD 的脚本菜单/工具栏流程绑定 OpenAssistant。

## 覆盖范围与限制

- **关键词搜索来源是 JLCPCB 贴片元件目录，非立创商城全量商品库**；支持完整型号与关键词，但中文搜索效果取决于此目录。C 料号通过 EasyEDA 模型库精确查找。
- 模型来源为 [嘉立创EDA/EasyEDA官方库](https://lceda.cn/) / [EasyEDA](https://easyeda.com/)。保留来源数据与元件参数。
- 原理图与封装预览用于快速识别，部分文本、3D 图元及外观层挖空没有转换，会明确提示。初版不提供 3D 模型；复杂焊盘、槽孔、多单元符号、未知图元会阻止导出。
- 0.2.2 支持区域路径中的绝对圆弧指令 A，将圆弧按最大弓高误差 0.001 mm 离散为闭合多边形，保持原始层。另有坐标取整误差。暂不支持椭圆弧、贝塞尔曲线、相对指令及同一区域内多个轮廓，遇到时明确阻止。
- 转换器是固定版本的第三方代码，详见 THIRD_PARTY_NOTICES.txt 与 vendor/jlc2ad/LICENSE。转换后需在 AD 核对电气类型、引脚名称/编号、焊盘尺寸、极性和封装关联。
- 实际 AD24 加载与放置验证状态以 docs/verification.md 为准；单元测试通过不代表所有器件都能正确生产。
- 原始数据缓存位于 data/cache。需要重新获取某个模型时，可删除该料号缓存文件再查询；不自动修改系统网络配置。系统只有 HTTP 代理时，程序对 HTTPS 也使用该代理，并保持证书校验。

## 开发

Python 3.10+。程序运行依赖 olefile；Tk 随常规 Windows Python 安装提供。转换部分不调用第三方 GUI 或联网客户端。

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
.\.venv\Scripts\pythonw.exe .\launch.pyw
```

输出：SchLib、PcbLib、保留原数据的 source.json、校验与状态 manifest.json；AD 导入请求和回执单独存放在 data/requests。
