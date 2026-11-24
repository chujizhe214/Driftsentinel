# DriftSentinel V1

本地优先的模型漂移压力测试与监控配置工作台。完整包含用户前端和业务后端，界面参考 `html/sonnet5.5.html`。当前版本没有管理后台、多用户权限或持续生产监控。

## 快速启动

推荐使用 **Docker Desktop（Linux 容器模式）**。Docker 方式不需要在电脑上单独安装 Python 或 Node.js。

Windows 双击 `start.bat`，或在 PowerShell 运行：

```powershell
.\scripts\start-docker.ps1
```

`start.bat` 会检查 Docker，必要时尝试启动 Docker Desktop；首次自动构建镜像，之后复用已有镜像。前后端在同一个 `DriftSentinel` 容器中运行，健康检查通过后自动打开 **http://127.0.0.1:8000**。启动窗口可以关闭，容器继续运行。

| 入口 | 用途 |
|---|---|
| `start.bat` | 日常启动 Docker 版，已启动时直接打开网页 |
| `stop.bat` | 停止本项目容器，数据保留 |
| `rebuild.bat` | 修改前端、后端或依赖后，重新构建并启动 |
| `start-local.bat` | 使用电脑上的 Python / Node.js 本地启动，无需 Docker |

首次构建需要联网下载基础镜像和依赖；之后日常启动与实验无需外部服务。Docker 使用 `restart: unless-stopped`，Docker Desktop 重启后会恢复此前保持运行的容器；手动停止后的容器可再双击 `start.bat` 启动。

`start.bat` 放在项目根目录，是因为它负责整个项目的启动，并通过自己的路径定位脚本和 Compose 配置；无需放在 `backend/` 中。

## 不使用 Docker 的本地启动

需要 **Python 3.11+** 和 **Node.js 22.12+**（也支持 Node.js 20.19+）。双击 `start-local.bat`，或运行 `.\start.ps1`。本地模式会创建 `.venv`、安装依赖、构建前端并启动 Python 服务，终端窗口需要保持打开，按 Ctrl+C 停止。

Docker 模式与本地模式都使用 8000 端口，选择一种运行即可。

也可以手动启动：

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
npm ci
npm run build
.\.venv\Scripts\python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

开发模式下，双击 `dev-backend.bat` 启动本地后端，保存 `backend/` 下的 Python 文件后会自动重载。如果项目的 Docker 容器正在运行，先双击 `stop.bat` 释放 8000 端口。另开一个终端在项目目录运行 `npm run dev` 启动前端。

前端开发地址为 http://127.0.0.1:5173，`/api` 由 Vite 代理到 Python 服务。生产构建由同一个 FastAPI 服务提供，无需额外 Web 服务器。API 文档：http://127.0.0.1:8000/docs。

## 第一次实验

1. 在“实验工作台”点击“加载示例”。
2. 选择变化字段、强度与随机种子。五类场景都可单独启用，也可增加一个多字段组合压力场景。
3. 点击“运行压力测试”。默认运行 0.5×、1×、1.5× 独立强度和无变化对照组。
4. 在“结果分析”切换场景、查看字段分布、F1 / Recall / AUC、预测正类比例与混淆矩阵。
5. 在“阈值校准”比较真实误报、漏报和召回率，采用推荐值。
6. 在“报告与导出”下载 Markdown 报告和 JSON / YAML 监控配置。

所有结果都来自实际计算。页面初次没有实验时显示空状态，不使用静态分数冒充已运行结果。

## 对比每天实际采集的数据

1. 在工作台切换到“实际数据对比”。
2. 选择或导入正常时期的“基准数据”，作为固定参照。
3. 在“待检测数据”中导入当天的 CSV，或选择已经导入的数据集。此操作不会替换基准。
4. 尚未获得真实业务结果时，待检测数据的真实标签保持“无”；只检测数据漂移时，模型选择“仅分析数据漂移”。
5. 点击“运行实际检测”，查看每个字段的 PSI、KS / 卡方、基准与待检测缺失率、分布图和风险。
6. 下一天保留同一基准，更换待检测数据再运行。每次结果自动保存在“实验历史”，可查看、下载报告或按原配置复现。

实际对比使用两份数据的全部样本，不采样、不生成模拟场景。待检测数据必须包含基准的全部非标签字段，按字段名对齐；数值字段包含不可转换的文字时会提示错误，额外字段会列为未参与对比。两份数据可以有不同的行数，待检测数据也可以没有标签列。样本少于监控规则的最小样本数时，结果中会提示。

基准和待检测数据的真实标签分别选择，标签不参与特征漂移检测。只有接入模型并提供有效标签才计算对应数据的性能；F1 下降需要两份数据都有有效标签。两批样本的性能差异不能单独证明由漂移导致。单次实际对比不自动推荐阈值，可使用已保存规则，或先在模拟压力测试中校准。此功能是手动批次检测，不会自动采集或定时监控业务数据。

## 第一版功能

| 需求 | 实现 |
|---|---|
| F1 示例项目 | UCI Bank Marketing 公开二分类数据、独立训练/测试拆分、固定逻辑回归模型、一键加载 |
| F2 数据导入 | 本地 CSV（UTF-8/GB18030）、分隔符识别、标签选择、字段类型、缺失/重复/唯一值/数值统计、数据预览 |
| F3 模型适配 | 内置模型、本地 Python 适配器、输出长度/维度/类别/概率校验 |
| F4 漂移场景 | 均值偏移、方差变化、类别比例重采样、目标缺失率、极端值注入；随机种子、强度梯度与多字段组合 |
| F5 漂移检测 | PSI、KS、卡方、每字段风险、基准/场景分布图 |
| F6 模型评估 | Accuracy / Precision / Recall / F1 / AUC、ROC、混淆矩阵、预测比例；无有效标签时不作性能结论 |
| F7 阈值校准 | 按 PSI、p 值、缺失率分别扫描阈值；混淆计数、误报/漏报/精确率/召回率；无影响正例时不给无依据的推荐 |
| F8 配置导出 | JSON / YAML、模型标识、字段检测方法、预警/严重阈值、缺失率、窗口和最小样本；Markdown 实验报告 |

另含实验任务进度、取消、失败说明、历史搜索/筛选/分页、原参数复现、数据/模型管理、规则持久化、移动端布局。

## 自定义模型

在“模型”中点击“适配器模板”，按模型的实际能力选择下载：

- **仅类别预测**：下载 `model_adapter.py`，只包含 `predict(X)`，适用于没有概率接口或不需要概率的模型。
- **支持概率预测**：下载 `model_adapter_proba.py`，包含 `predict(X)` 和 `predict_proba(X)`。可分析预测概率分布；有有效真实标签时可计算 AUC / ROC。

模板以 joblib / scikit-learn 为例，不能自动给模型增加概率预测能力；其他框架仍需修改加载和预测代码。没有概率接口的模型应使用“仅类别预测”，避免调用不存在的方法。下载后放到模型文件旁，修改模型文件名并保持训练时的输入和预处理一致。例如支持概率预测的适配器：

```python
from pathlib import Path
from joblib import load

model = load(Path(__file__).parent / "model.joblib")

def predict(X):
    return model.predict(X)

def predict_proba(X):
    return model.predict_proba(X)
```

登记适配器绝对路径和实际正/负类值，再使用当前基准数据“校验输出”。适配器在本地 Python 服务执行，只接入自己信任的代码；相关依赖应安装在服务使用的 Python 环境。`predict` 返回 `(n,)`；概率可为 `(n,)` 或 `(n, 2)`，两列时第二列必须是配置的正类。所有输入字段必须与模型训练时匹配。

导入其他结构的数据后，默认切换为“仅分析数据漂移”，可继续运行数据实验；接入匹配模型后再评估预测。标签缺失、不是二分类、类别与模型配置不匹配时，真实性能指标保持为空。没有概率输出时 AUC / ROC 保持为空。

## 实验与统计说明

- 数值均值偏移：相对基准均值绝对值偏移；零均值时使用标准差或 1。
- 方差变化：保持均值，按 `sqrt(1 + 强度 / 100)` 缩放。
- 类别比例变化：重采样**完整行**以达到目标比例，保留样本特征与标签配对。
- 缺失值：提高到目标总缺失率；不会反向填充已有缺失。
- 极端值：按指定比例注入距均值 5–10 个标准差的数值。
- PSI：使用基准分位数分箱，数值两端含超范围样本，缺失单独一箱，epsilon 平滑避免无穷值。
- KS / 卡方：分别提供统计量和 p 值，与 PSI 单独判断。KS 使用渐近 p 值；未进行多重检验校正，样本量会影响显著性。
- F1 下降标准是绝对差（默认 0.03，即 3pp），不是相对百分比。输入扰动保留原始标签，只研究受控压力场景下的稳健性，不把它当作真实概念漂移的证明。
- 阈值推荐只适用于当前数据、模型与场景。检测延迟、多窗口漂移属于后续版本。

## 存储与边界

- `localdata/workspace.db`：SQLite 数据集元信息、模型登记、实验参数/结果、规则。
- `localdata/datasets/`：服务内部生成的基准数据快照，不加载用户提供的 pickle。
- 浏览器 `localStorage`：当前选择与未运行的场景参数。
- 可通过 `DRIFTSENTINEL_DATA_DIR` 修改后端存储位置。
- CSV 限制：30–50,000 行、2–200 列、最大 30 MB。实验串行执行；运行中可以取消。
- 适配器执行是本地受信任代码执行，不提供容器沙箱或公网多租户能力。
- 删除源数据集或模型登记后，已有结果快照仍可查阅；复现需要原数据和模型仍可用。适配器文件本身由用户维护，修改文件会影响之后的实验。

## 验证

```powershell
python -m pytest -q
npm run build
npm run test:e2e
```

浏览器测试使用单独的 `test-workspace/`，不污染正常工作区。Windows 优先使用已安装的 Chrome；其他环境先执行 `npx playwright install chromium`。覆盖示例实验、分布详情、导出、刷新恢复、复现、CSV 导入、无标签边界、错误提示、规则保存和移动端。

## Docker

配置文件位于项目根目录：`Dockerfile`、`compose.yaml`、`.dockerignore`。容器和网络名称为 `DriftSentinel`；Compose 项目名为 `driftsentinel`，镜像为 `driftsentinel:1.0.0`（Compose 项目名与镜像仓库名必须使用小写，因此 Docker Desktop 的项目分组仍显示小写）。

```powershell
docker compose up -d --build --wait
```

访问 http://127.0.0.1:8000。`localdata/` 持久化到宿主机；`models/` 只读挂载到 `/app/models`，Docker 中接入适配器时填写容器内路径，例如 `/app/models/model_adapter.py`。自定义模型需要的额外 Python 包应加入 `requirements.txt` 后运行 `rebuild.bat`。

常用命令：

```powershell
docker compose ps                 # 查看项目与健康状态
docker compose logs --tail 100     # 查看最近日志
docker compose stop               # 停止，保留容器与本地数据
```

前后端是分别编写的：`src/` 是 Vue 前端，`backend/` 是 Python 后端。构建时，Node.js 把前端源码生成到 `dist/`；运行时，FastAPI 向浏览器发送 `dist/` 中的 HTML、CSS、JavaScript，并处理 `/api` 请求。因此前后端可以在同一个容器、同一个 8000 端口提供服务，前端代码仍在浏览器里执行。

## 工程结构

```text
src/                  Vue 3 + TypeScript 前端
  pages/              工作台、数据集、模型、历史、规则、设置
  components/         图表、分布详情、校准、报告、弹窗
  api.ts / store.ts   业务接口、应用状态和任务轮询
backend/              FastAPI 业务服务
  analytics.py        画像、场景、统计检验、模型调用、评估、校准
  app.py              业务 API、任务调度、配置导出、静态前端
  storage.py          SQLite 与本地数据快照
  schemas.py          参数与规则校验
public/demo/          公开基准数据、固定模型权重、来源说明
scripts/prepare_demo.py  示例数据与模型复现脚本（无需在正常启动时运行）
tests/                算法、业务 API 和浏览器测试
html/                 原始设计参考及旧原型
```
