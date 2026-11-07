# 山雀企业项目工作台 · Ant Design Pro 网页版

基于官方 Ant Design Pro v6.0.3，使用 React 19、Ant Design 6、ProComponents 3、Umi Max 4。采用深绿色侧栏与主操作、标准表格、表单、状态标签和确认交互，统一使用山雀 Logo。

## 启动

在仓库根目录执行：

```powershell
npm ci
npm --prefix frontend ci
npm run frontend:build
.\.venv\Scripts\python.exe run.py --server
```

服务器上访问 http://127.0.0.1:5086，其他成员通过服务器 IP 访问。首次启动在终端设置管理员密码。根目录的构建脚本使用项目本地 Node 22.22.2。Python 直接提供 frontend/dist 静态文件，无需额外的前端服务。

开发时启动 Python 后执行 `npm run frontend:dev`。Umi 将 `/api/page/*` 转发为 Python 的原页面路径；生产环境直接访问相同路径。开发不启用 mock。

## 页面与业务

- Workbench.tsx：ProLayout、登录、会话、左下角团队切换、菜单和路由数据加载。
- Overview.tsx：项目指标、默认展开的项目台账、节点日期差和进展更新。
- Project.tsx、Tasks.tsx、RecordEditor.tsx：项目设置、成员、节点、多人任务、内嵌日历和状态说明。
- Gantt.tsx：项目／节点／任务树、固定 24 像素日刻度、拖动日期栏、默认定位今天、筛选及展开收起。
- People.tsx：当前团队人员、管理员团队维护、项目共享和底层用户账户／Excel 导入。

GET 页面请求带 `Accept: application/json` 返回 `{data, context, messages}`。POST 使用 FormData，继续经过 Python 原有的权限、CSRF、当前团队校验、任务版本校验和数据库事务；成功返回 `{redirect, messages, context}`，失败返回原 HTTP 状态及 message。`/api/session` 提供会话和 CSRF，不返回密码。

保存后保留当前页面；团队切换后重新加载当前团队的数据。我的待办始终汇总全部团队。JSON 与旧模板共用业务规则，构建产物存在时网页版默认提供 React 页面。`FRONTEND_ENABLED=False` 用于旧模板回归测试及兼容运行。

## 验证

```powershell
npm run frontend:check
npm run frontend:build
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

浏览器验收脚本 scripts/verify_pro_ui.py 使用独立临时 SQLite 台账并启动随机本地端口，需要安装 requirements.txt、Playwright 及 Chrome 的 Python 环境。执行 `python scripts/verify_pro_ui.py`；截图与结果写入 instance/pro-validation，不写真实台账。

Ant Design CLI 已安装于仓库：`npm run antd -- info Table`、`npm run antd -- lint frontend/src`。

设计与 API 参考：[Ant Design 设计语言](https://ant.design/docs/spec/introduce-cn/)、[Ant Design CLI](https://ant.design/docs/react/cli-cn/)、[Ant Design Pro](https://pro.ant.design/)。

## 许可证与第三方声明

山雀原创代码和修改采用根目录的 [Apache-2.0 许可证](../LICENSE)。Ant Design Pro 模板的原始 MIT 许可及版权声明保留于本目录的 [LICENSE](LICENSE)，参见根目录 [NOTICE](../NOTICE)。
