# 外挂 KingbaseES / PostgreSQL

应用默认使用 SQLite。开源版 Compose 只包含 `shanque` 应用，不捆绑或启动数据库服务。KingbaseES/PostgreSQL 由数据库管理员独立部署与维护。

## 配置

复制 `.env.example` 为 `.env`，设置初始管理员密码，并修改以下字段：

```dotenv
SHANQUE_IMAGE=ffbum/shanque:1.1
SHANQUE_PORT=5086
SHANQUE_ADMIN_PASSWORD='请设置8至128位初始密码'
SHANQUE_DB_TYPE=kingbase
SHANQUE_DB_HOST=192.168.1.20
SHANQUE_DB_PORT=54321
SHANQUE_DB_NAME=shanque
SHANQUE_DB_SCHEMA=shanque
SHANQUE_DB_USER=shanque_app
SHANQUE_DB_PASSWORD='替换为数据库密码'
SHANQUE_DB_SSLMODE=prefer
SHANQUE_DB_CONNECT_TIMEOUT=10
SHANQUE_DATABASE_URL=
```

| 字段 | 说明 |
| --- | --- |
| `SHANQUE_DB_TYPE` | `sqlite`（默认）、`kingbase`、`postgresql` |
| `SHANQUE_DB_HOST` | 应用容器可访问的数据库地址；容器内的 `127.0.0.1` 是应用容器自身 |
| `SHANQUE_DB_PORT` | 留空时 KingbaseES 使用 54321，PostgreSQL 使用 5432 |
| `SHANQUE_DB_NAME` | 已创建的 database，可与其他应用共用 |
| `SHANQUE_DB_SCHEMA` | 预先创建的业务 schema；默认 public，共用 database 时设置为独立的 shanque schema |
| `SHANQUE_DB_USER` | 对该数据库业务 schema 具有建表、修改表、创建函数/触发器和读写权限的账号 |
| `SHANQUE_DB_PASSWORD` | 数据库密码；使用 Compose `.env` 单引号语法保留 `$`、`#`、空格等字符，包含单引号时按 Compose 规则转义 |
| `SHANQUE_DB_SSLMODE` | 默认 `prefer`；支持 `disable/allow/prefer/require/verify-ca/verify-full`。证书验证模式需要按 libpq 规则向容器配置 CA 文件 |
| `SHANQUE_DB_CONNECT_TIMEOUT` | 连接超时，单位秒，默认 10 |
| `SHANQUE_DATABASE_URL` | 兼容原完整连接串；非空时优先于拆分字段。仅使用原连接串时将类型留空或指定对应外部数据库类型 |

显式选择 `sqlite` 时不能同时设置完整连接串。配置错误或外部数据库不可用会使启动失败，不会退回 SQLite 创建另一份数据。

`.env` 由 Docker Compose 读取并注入应用环境；直接执行 Python 时需自行设置同名环境变量。密码无需手动进行 URL 编码，应用使用 psycopg 构造连接参数。

## 外部数据库准备

KingbaseES 需要在初始化实例时选择 PG 模式。应用选择 `kingbase` 后会在建表前执行 `SHOW database_mode`，只接受 `pg`。数据库版本验证基线为 ARM64 KingbaseES V009R002C016，其他版本需按目标环境验证。

由数据库管理员在专用实例中创建数据库和账号，例如：

```sql
CREATE USER shanque_app WITH PASSWORD '替换为数据库密码';
CREATE DATABASE shanque OWNER shanque_app ENCODING 'UTF8';
```

连接到目标 database 后创建本应用专用 schema：

```sql
CREATE SCHEMA shanque AUTHORIZATION shanque_app;
```

共用已有 database 时，只需创建本应用账号和独立 schema，不需要再建 database。应用只搜索指定 schema，不回退到 public；schema 不存在或无访问权限时启动失败。schema 选择同样适用于完整连接串，并优先于其 search_path 设置。

应用启动会创建及升级业务表，不会创建数据库、数据库账号或调整服务器访问规则。数据库服务需允许应用服务器的网络连接。

## 首次启动

```bash
cp .env.example .env
# 编辑 .env
docker compose pull shanque
docker compose up -d shanque
docker compose ps
docker compose logs --tail=100 shanque
```

默认地址 `http://服务器IP:5086`。新库创建 `manager` 和默认团队；已有数据库不会重置账户密码。即使使用外部数据库，也保留 `shanque-data` 卷中的会话签名密钥。

PostgreSQL 配置将类型改为 `postgresql`，端口改为实际端口（默认 5432）；该类型不会查询 KingbaseES 专有的模式参数。

## 迁移原 SQLite 数据

先停止录入和应用，备份原 SQLite 数据。将 `.env` 改为外部数据库配置，目标 schema 的业务表必须为空；不要先启动应用创建管理员。

如果原 SQLite 就在当前 `shanque-data` 卷中：

```bash
docker compose stop shanque
docker compose pull shanque
docker compose run --rm --no-deps --entrypoint python shanque   scripts/migrate_sqlite_to_pg.py /data/workspace.sqlite3   --backup /data/before-external-db.sqlite3
docker compose up -d shanque
```

每次迁移使用新的 `--backup` 文件名，脚本不会覆盖已有备份。迁移首先生成一致性 SQLite 快照，然后在单个目标事务中导入 9 张业务表、逐行核对并校准自增序列。目标非空时拒绝导入。迁移保留账号、密码哈希、团队权限和任务版本。确认迁移后的页面、筛选和权限后再恢复业务录入。

可使用 `python scripts/export_sqlite_snapshot.py 原数据库路径 新的导出目录` 生成完整快照及校验文件。

从其他目录导入时，可在 `docker compose run` 增加只读挂载并将源路径改为容器中的快照路径。只读快照应使用 SQLite backup API 生成，并设置 `PRAGMA journal_mode=DELETE`，确保不依赖外部 WAL 文件。

## 备份与升级

外部数据库由数据库管理员使用 KingbaseES `sys_dump/sys_restore` 或 PostgreSQL `pg_dump/pg_restore` 维护备份；仅备份 `shanque-data` 卷不包含外部库中的业务数据。升级前同时备份数据库和应用数据卷。

应用账号需保留其创建对象的所有权，以支持后续表结构升级。保持 `.env` 与数据卷，设置目标镜像版本后拉取并启动应用。

## 回归入口

设置 `SHANQUE_TEST_DATABASE_URL` 指向专用测试数据库，KingbaseES 测试额外设置 `SHANQUE_TEST_DB_TYPE=kingbase`，执行：

```bash
python scripts/test_postgres.py
```

测试以独立 schema 隔离并清理自己创建的数据。ARM64 容器仿真测试与目标麒麟服务器实机验收分别记录。

## 验证记录（2026-11-07）

SQLite/配置测试 32 项通过；ARM64 KingbaseES PG 模式业务回归 32 项通过。专用 schema 建表及查询已验证，与同一 database 的 public 表隔离。普通账号（非超级用户）的外部数据库建表、登录、项目读写与 SQLite 迁移已验证。

ARM64 运行使用 Docker Desktop 仿真；麒麟 V10 实机与其他 KingbaseES 版本需按实际部署环境验收。1.0 镜像不包含外部数据库适配，请使用 1.1 或更新版本。
