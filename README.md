# EsayAD

**在 Altium Designer 中快速使用立创元件。**

EsayAD 是一个 Windows 桌面助手：搜索元件，预览原理图符号与 PCB 封装，生成配套的 Altium 库，再将元件放入原理图。适合希望减少查找、下载和手动整理元件库步骤的 AD 用户。

[下载程序](https://github.com/xieeeeeeeeee/EsayAD/releases) · [反馈问题](https://github.com/xieeeeeeeeee/EsayAD/issues) · [验证记录](docs/verification.md)

## 功能

- **元件搜索**：支持立创 C 料号、厂家型号与关键词，支持结果分页。
- **符号与封装预览**：查看引脚、焊盘和编号匹配情况。
- **配套库生成**：同时导出 `.SchLib`、`.PcbLib`，保留料号、厂家型号与来源链接。
- **AD 交互放置**：调用 AD 脚本安装库，将符号附着到光标，由用户点击放置。
- **本地缓存**：复用已获取的模型；每次导出保存到独立目录，保留旧文件。
- **紧凑界面**：默认 900 × 650，支持缩至 760 × 560；主要操作固定在底部，设置与日志收在“更多”菜单。

> 关键词搜索使用 **JLCPCB 贴片元件目录**，不覆盖立创商城的全部商品。C 料号通过 EasyEDA 模型库精确查询。商品能搜到，不代表一定具有可转换的完整模型。

## 快速开始

### 1. 打开程序

从 [Releases](https://github.com/xieeeeeeeeee/EsayAD/releases) 下载 `EsayAD.exe`，放到可写的独立文件夹，双击运行。

- EXE 版无需安装 Python。
- 使用 Windows，并安装可正常运行的 Altium Designer。
- 搜索和首次获取模型需要网络。
- 程序在自身所在目录创建 `data` 文件夹，请保留写入权限。
- 更新前关闭旧版窗口。可在原目录替换程序，保留 `data` 中的库与设置。

### 2. 选择 AD 安装路径

程序会尝试发现本机 AD。若没有识别到，或需要切换版本，打开：

**更多 → 设置 AD 路径 → 选择安装目录中的 `X2.EXE`**

选择会保存，重启后仍有效。“更多 → AD 版本与兼容信息”可查看当前路径和版本。

### 3. 搜索并选择元件

输入 C 料号、型号或关键词，按 Enter 或点击“搜索”。例如：

| 输入 | 用途 |
| --- | --- |
| `C25804` | 精确查询立创料号 |
| `NE555DR` | 按厂家型号查找 |
| `ESP8266` | 按关键词查找 |
| `capacitor` | 按英文类别查找 |

选择结果后，等待模型加载。模型完整且引脚、焊盘编号匹配时，生成库与导入按钮可用。转换限制和详细错误可在 **更多 → 查看日志** 中查看。

### 4. 生成库或导入 AD

- **生成库**：只生成本地 `.SchLib` 和 `.PcbLib`；点击“输出目录”查看。
- **导入 AD 并放置**：先在 AD 中打开并激活目标 `.SchDoc`，再点击按钮。切回 AD，点击放下元件，按 Esc 结束放置。

状态栏会区分库已生成、请求已发送和 AD 放置回执。等待期间不要重复运行脚本。

### 5. 将封装更新到 PCB

符号放到原理图以后，按 AD 的标准工程流程执行：

**Design / 设计 → Update PCB Document / 更新 PCB 文档 → 检查并应用 ECO**

原理图与目标 PCB 需要属于相应工程。EsayAD 不会自动向现有 PCB 添加或移动器件。


## AD 版本与验证状态

适配目标为 **AD20–AD26.12.2**。程序使用传统 DelphiScript 和文件库接口，不绑定新版 SDK DLL；这不代表所有版本均已验证通过。

| 版本 / 环节 | 状态 |
| --- | --- |
| AD24.0.1.36 | 已实测符号放置、封装模型关联、PCB 库打开及焊盘读取 |
| AD20、21、22、23、25、26 | 已提供版本无关的接口接入与安装路径选择，尚未逐版本实测 |
| 完整 Update PCB / ECO 流程 | 仍需在实际工程中验证 |

已验证的 AD24 样本包括 `C3209113`（9 焊盘）与 `C534876`（25 焊盘）。当前有 31 项自动化测试，详细范围见 [验证记录](docs/verification.md)。

转换后请根据数据手册核对引脚功能与编号、焊盘尺寸、方向、极性和封装关联，再用于实际设计。

## 图元支持范围

| 类型 | 当前处理方式 |
| --- | --- |
| 普通矩形、圆形与长圆焊盘 | 转换为对应的 AD 焊盘 |
| 用多边形顶点描述的长圆焊盘 | 轮廓校核通过后还原为原生长圆焊盘，例如 BTT6200-4ESA |
| 直线与圆弧构成的单轮廓实心区域 | 保留原始层；圆弧离散为闭合多边形 |
| 任意自定义多边形焊盘、槽孔 | 暂不支持，明确阻止导出 |
| 多单元符号、重复引脚编号、未知图元 | 暂不支持，明确阻止导出 |
| 椭圆弧、贝塞尔曲线、相对路径、区域内多个轮廓 | 暂不支持，明确阻止导出 |
| 部分文字、3D 图元、外观层挖空 | 不转换，并给出提示 |

圆弧区域的最大弓高离散误差为 0.001 mm；多边形长圆焊盘按 0.001 mm 轮廓偏差上限校核，另有坐标取整误差。预览用于快速识别，实际输出仍需在 AD 中核对。当前不提供 3D 模型转换。

## 常见问题

### 提示 Another script executing now

AD 中上一次脚本可能仍在运行或因错误暂停。

1. 关闭 AD 的错误提示，在脚本编辑界面选择 **运行 → 停止**。
2. 确认脚本停止后，在 EsayAD 选择 **更多 → 解除导入等待**。
3. 激活目标原理图，再发送一次导入请求。

程序不会自动超时重发，以免旧脚本尚未结束时产生冲突。

### 已生成库，但 AD 没有响应

检查“更多”中的 AD 路径和运行日志。确认没有其他脚本占用 AD 后，可在 AD 的 **File → Run Script** 中打开 `data/requests` 对应请求目录里的 `Import_*.PrjScr`，运行 `ImportPart`。

手动运行期间不要再从助手发送导入请求。

### Footprint is missing / Name is missing

先用当前版本重新生成库，并更新或重新放置旧器件。在 AD 的 **Properties → Footprints** 中确认具体封装名称和库位置。

符号与封装库存在关联路径。生成库后不要单独移动、重命名或删除关联的 `.PcbLib`；若更换存放位置，请重新生成并更新器件。

### 搜不到元件或模型无法导入

优先尝试准确的 C 料号。关键词结果受贴片目录范围与服务状态影响；无模型、引脚编号不匹配或图元不支持时，助手会说明原因。

模型缓存在 `data/cache`。需要刷新某个元件时，可关闭助手，删除对应料号的缓存 JSON，再重新查询。

### 搜索失败或超时

检查网络与代理。程序使用已有系统代理；只有 HTTP 代理而没有 HTTPS 专用配置时，会将该代理用于 HTTPS 请求，并保持证书校验。程序不修改系统代理设置。

### 单文件 EXE 的“使用说明”打不开

“使用说明”读取程序旁边的 `README.md`。只下载 EXE 时，可直接阅读 [仓库说明](https://github.com/xieeeeeeeeee/EsayAD#readme)，或把此文件放在 EXE 旁边。

## 文件与数据

```text
data/
├── settings.json                   # AD 安装路径设置
├── cache/                          # 按料号缓存的原始模型
├── libraries/<料号>/<唯一目录>/
│   ├── <料号>.SchLib               # 原理图库
│   ├── <料号>.PcbLib               # PCB 封装库
│   ├── source.json                 # 保留的来源数据
│   └── manifest.json               # 编号检查、来源、警告与生成状态
└── requests/<请求编号>/             # AD 导入脚本与状态回执
```

`data` 是本地工作数据，默认不提交到 Git。删除库之前，请确认现有工程不再引用它。

## 从源码运行

需要 Windows、Python 3.10+，以及带 Tk 支持的 Python 安装。

```powershell
git clone https://github.com/xieeeeeeeeee/EsayAD.git
cd EsayAD
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\pythonw.exe .\launch.pyw
```

运行测试：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
```

其中一项安装版本测试依赖开发机的 `E:\AD24\X2.EXE`；其他电脑需要调整该测试路径，测试全集不是完全独立于 AD 安装环境的。

打包独立 EXE（在项目根目录执行）：

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --onefile --windowed --name EsayAD --icon "assistant/assets/app.ico" --add-data "assistant/assets;assistant/assets" --add-data "vendor/jlc2ad;vendor/jlc2ad" --add-data "README.md;." --paths "vendor/jlc2ad" launch.pyw
```

输出位于 `dist/EsayAD.exe`。`ad/Launcher.PrjScr` 提供从 AD 打开助手的脚本入口；使用前需将 `ad/Launcher.pas` 中的路径改成自己的 EXE 路径。

## 来源与致谢

元件模型来源：**嘉立创EDA/EasyEDA官方库**。

- [嘉立创EDA](https://lceda.cn/)
- [EasyEDA](https://easyeda.com/)
- [JLCPCB 元件目录](https://jlcpcb.com/parts)

库转换代码基于 [NatsumiAi/jlc2ad](https://github.com/NatsumiAi/jlc2ad)，固定提交为 `7bb2d0f83790430d9aae892ecc2f67755c348b9d`。该第三方代码采用 MIT 许可证，随源码保留 [许可证](vendor/jlc2ad/LICENSE) 与 [第三方声明](THIRD_PARTY_NOTICES.txt)。第三方代码的许可证不代表元件模型数据的使用授权；模型及相关数据的权利归对应提供方所有。

EsayAD 为独立项目，与 Altium、嘉立创或 EasyEDA 无官方隶属关系。

## 反馈问题

请通过 [Issues](https://github.com/xieeeeeeeeee/EsayAD/issues) 提供 EsayAD 版本、AD 完整版本、元件 C 料号、操作步骤和错误截图。附上运行日志时，请先移除个人路径与工程中的非公开信息。
