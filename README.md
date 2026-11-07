# 山雀企业项目工作台

**面向企业各类项目的轻量项目跟踪与协作工具。**

当前发布版本：**1.0**。

团队成员可围绕项目、关键节点和任务，集中呈现计划、实际进展与时间差距，帮助团队在日常跟踪和例会上掌握全局。

适用于科研、工程、固定资产投资、自研和预研等各类企业项目。

## 功能与特点

### 多项目总览

- 在同一张台账中查看项目与下级任务，默认展开，支持收起。
- 集中展示当前状态、任务完成情况、上一个与下一个关键节点、节点日期及最新进展。
- 按项目类型和项目状态筛选，快速定位需要关注的工作。

### 甘特图

- 在同一时间轴上展示项目周期、节点阶段与任务起止日期。
- 项目、节点和任务分层展示，可展开查看任务名称、执行人、日期与状态。
- 固定日期刻度，长周期项目横向滚动；支持拖动顶部日期栏，默认定位今天。
- 项目条显示节点达成比例，任务完成数量另行统计，便于区分阶段进展与日常工作量。

### 关键节点与滚动任务

- 项目支持多个负责人、多个节点；任务支持多个执行人以及独立的开始日和截止日。
- 每个节点最多指定一个节点任务，节点任务完成后自动达成节点；未设置时由有权限的人员手动确认。
- 强制达成节点时，关联的未完成任务同步完成。
- 任务支持未开始、进行中、受阻、已完成四种状态，可直接更新状态并填写说明。

### 团队协作

- 一个人可以加入多个团队，同一个项目也可以共享给多个团队。
- 共享项目使用同一份节点、任务与进展，避免重复维护。
- 快速切换团队，总览、甘特图和团队人员随之切换。
- “我的待办”跨团队汇总个人任务，同一任务只显示一次。
- 管理员统一维护用户账户，支持 Excel 导入、修改密码和设置系统管理员；团队主管从已有账户中添加团队成员。

### 轻量部署

- Python 后端、React 前端、SQLite 数据库，一个服务提供页面和业务接口。
- 浏览器访问，无需安装客户端；运行服务器无需常驻 Node.js 服务。
- 使用 SQLite WAL 和任务版本校验处理多人读写与过期页面提交。
- 深绿主题、紧凑表格和统一图标，优先呈现项目状态与进展。

## 角色与权限

| 身份 | 职责范围 |
| --- | --- |
| 系统管理员 | 维护用户账户、创建团队、设置团队角色、关联团队项目 |
| 团队总监 | 查看当前团队项目，掌握整体进展 |
| 团队主管 | 维护团队内项目、节点和任务，增减本团队普通成员 |
| 项目负责人 | 维护负责项目的进展和任务，分派工作；不能变更节点计划 |
| 任务执行人 | 更新获派任务的状态与完成情况 |

团队总监、团队主管和团队成员角色按团队设置，管理员可直接在角色列选择并保存；项目负责人按项目指定。同一人在不同团队和项目中可以承担不同职责。

## 技术栈

| 层次 | 当前实现 |
| --- | --- |
| 前端 | Ant Design Pro 6、React 19、Ant Design 6、Umi Max 4 |
| 后端 | Python、Flask 3、Waitress 3 |
| 数据库 | SQLite，启用 WAL 模式 |
| 账户导入 | Excel / openpyxl |

当前版本使用 SQLite，不需要单独安装数据库服务。

## Docker 部署

山雀通过 Docker Compose 运行，镜像发布在 [Docker Hub](https://hub.docker.com/r/ffbum/shanque)，当前版本为 `ffbum/shanque:1.0`。服务器安装 Docker Engine 和 Docker Compose v2 即可，无需单独安装 Python、Node.js 或数据库。

### 首次启动

先克隆仓库：

```sh
git clone https://github.com/ffbum/shanque.git
cd shanque
```

打开 `compose.yaml`，将 `SHANQUE_ADMIN_PASSWORD` 的 `CHANGE_ME_BEFORE_STARTING` 替换为 8 至 128 位的初始管理员密码。新数据库首次启动时用它创建 `manager`，之后密码保存在数据卷的数据库中。不要提交包含实际密码的 `compose.yaml`。

```sh
docker compose pull
docker compose up -d
docker compose ps
```

打开 `http://服务器地址:5086`，用账号 `manager` 和刚设置的密码登录。新数据库只创建管理员和默认团队，不含演示项目。随后在左下角的用户菜单中添加人员、设置团队，并创建项目。

Compose 将数据库和会话密钥保存在名为 `shanque-data` 的 Docker 数据卷中，容器重建或更新镜像时会保留。修改访问端口可设置 `SHANQUE_PORT`，例如 Linux `SHANQUE_PORT=8080 docker compose up -d`，PowerShell `$env:SHANQUE_PORT = "8080"; docker compose up -d`。

### 更新

在仓库目录执行：

```sh
docker compose pull
docker compose up -d
```

Compose 固定使用版本标签，更新版本时先将 `compose.yaml` 中的镜像标签改为目标版本，再执行上述命令。数据卷独立于镜像，更新不会覆盖已有台账。

## 数据维护与升级

数据目录包含：

| 文件 | 用途 |
| --- | --- |
| `workspace.sqlite3` | 用户、团队、项目、节点和任务数据 |
| `local.key` | 会话签名密钥 |
| SQLite 日志文件（如存在） | WAL 等数据库运行文件 |

### 备份与恢复

停止容器后备份数据卷，再启动服务。Linux/macOS 示例：

```sh
docker compose stop shanque
mkdir -p backups
docker run --rm -v shanque-data:/data -v "$(pwd)/backups:/backup" alpine:3.22 \
  tar -czf /backup/shanque-data.tar.gz -C /data .
docker compose start shanque
```

数据卷包含 `workspace.sqlite3`、`local.key` 和 SQLite 日志文件。恢复时先停止服务，再将备份内容写回 `shanque-data` 卷。

### 版本升级

1. 停止服务，备份 `shanque-data` 数据卷。
2. 拉取新镜像并重建容器：`docker compose pull && docker compose up -d`。
3. 程序会在启动时执行数据库结构升级逻辑。
4. 登录核对团队、项目、节点与任务。

如需回退，应配套恢复升级前的镜像和数据备份。迁移服务器时，复制完整数据卷并启动 Compose 服务；只有新建空数据卷时才需要设置初始管理员密码。

业务数据、密钥、依赖目录和构建产物均不应提交到源码仓库。对外发布时使用源码及构建流程，不附带实际企业台账。

## 开发与验证

开发时需要 Python 3.11、Node.js 22 和 npm。前端代码、页面接口和开发说明见 [前端文档](frontend/README.md)。在仓库根目录安装依赖：

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm ci
npm --prefix frontend ci

# 前端规范与类型检查
npm run frontend:check

# 构建生产页面
npm run frontend:build

# 后端业务测试（Linux）
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

Windows 测试命令：

```powershell
py -3.11 -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

测试使用独立临时数据库。浏览器业务验证脚本为 `scripts/verify_pro_ui.py`，需要额外安装 Playwright 并准备 Chrome；它会启动临时数据库和随机端口，不写入正式业务数据。

### 目录结构

```text
frontend/          前端页面、组件、主题和构建配置
workspace/         Python 业务、权限、数据模型和页面接口
tests/             业务与接口测试
scripts/           前端构建及浏览器验证脚本
run.py             服务启动入口
requirements.txt   Python 依赖
```

## 参与贡献

欢迎提交问题和改进建议。反馈问题时，请提供版本、部署方式、复现步骤及必要截图，并移除账号密码和业务敏感信息。

提交代码前，请运行与改动相关的业务测试、`npm run frontend:check` 和 `npm run frontend:build`。界面改动应同时检查项目总览、项目详情与甘特图的状态表达是否一致。

## 许可证

本项目的原创代码和文档采用 **[Apache License 2.0](LICENSE)**，允许商业使用、修改与分发，具体条件以许可证全文为准。

第三方代码及资源保留各自的许可证和版权声明。前端基于 Ant Design Pro v6.0.3，其原始 MIT 许可证及 `Copyright (c) 2019-present Alipay.inc` 声明完整保留在 [frontend/LICENSE](frontend/LICENSE)。项目归属说明见 [NOTICE](NOTICE)。

分发源码或构建产物时，请一并保留适用的许可证与版权声明；依赖组件的许可不因本项目采用 Apache-2.0 而改变。
