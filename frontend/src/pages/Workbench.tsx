import {
  ApartmentOutlined,
  CalendarOutlined,
  CheckSquareOutlined,
  DownOutlined,
  HomeOutlined,
  LockOutlined,
  LogoutOutlined,
  TeamOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { PageContainer, ProLayout } from '@ant-design/pro-components';
import { history, useLocation } from '@umijs/max';
import {
  App,
  Avatar,
  Button,
  Card,
  Dropdown,
  Form,
  Input,
  Result,
  Spin,
  Tabs,
} from 'antd';
import { useCallback, useEffect, useState } from 'react';
import { type ApiError, readPage, save, sessionInfo } from '../api';
import PageTitle from '../components/PageTitle';
import RecordEditor from '../components/RecordEditor';
import Tasks from '../components/Tasks';
import { WorkspaceContext } from '../context';
import type { PageData, Session, Values } from '../types';
import Gantt from './Gantt';
import Overview from './Overview';
import People from './People';
import ProjectPage from './Project';

export default function Workbench() {
  const location = useLocation();
  const path = location.pathname;
  const { message } = App.useApp();
  const [session, setSession] = useState<Session>();
  const [data, setData] = useState<PageData>();
  const [dataPath, setDataPath] = useState('');
  const [dataTeam, setDataTeam] = useState<number>();
  const [error, setError] = useState<ApiError>();
  const [version, setVersion] = useState(0);
  const [busy, setBusy] = useState(false);
  const [todoFilter, setTodoFilter] = useState('pending');
  const reload = useCallback(() => setVersion((v) => v + 1), []);
  useEffect(() => {
    const controller = new AbortController();
    setError(undefined);
    (async () => {
      const current = await sessionInfo(controller.signal);
      setSession(current);
      if (!current.user && path !== '/login') {
        history.replace('/login');
        return;
      }
      if (current.user && path === '/login') {
        history.replace('/');
        return;
      }
      const result = await readPage(path + location.search, controller.signal);
      setSession(result.context);
      setData(result.data);
      setDataPath(path + location.search);
      setDataTeam(result.context.team?.id);
    })().catch((e) => {
      if (e.name === 'AbortError') return;
      if (e.status === 401 && path !== '/login') {
        history.replace('/login');
        return;
      }
      setError(e);
    });
    return () => controller.abort();
  }, [path, location.search, version]);
  const submit = async (
    url: string,
    values: Values | FormData,
    navigate = true,
  ) => {
    if (!session) return;
    try {
      const result = await save(url, values, session);
      for (const text of result.messages || []) message.success(text);
      // Authentication and team mutations take effect on the next request.
      const next = await sessionInfo();
      setSession(next);
      if (!next.user) {
        history.replace('/login');
        reload();
        return;
      }
      if (
        navigate &&
        result.redirect &&
        result.redirect !== path + location.search
      )
        history.push(result.redirect);
      else reload();
    } catch (e) {
      message.error((e as Error).message);
      throw e;
    }
  };
  if (!session)
    return (
      <div className="page-loading">
        {error ? (
          <Result
            status="error"
            title={error.message}
            extra={<Button onClick={reload}>重试</Button>}
          />
        ) : (
          <Spin size="large" />
        )}
      </div>
    );
  const login = path === '/login';
  const password = path === '/password';
  const authForm = (
    <Card className="auth-card" title={login ? undefined : '修改密码'}>
      {login && <h1 className="login-heading">登录工作台</h1>}
      <Form
        layout="vertical"
        onFinish={async (values) => {
          setBusy(true);
          try {
            await submit(path, values);
          } catch {
          } finally {
            setBusy(false);
          }
        }}
      >
        {login ? (
          <Form.Item name="login" label="账号" rules={[{ required: true }]}>
            <Input autoComplete="username" autoFocus />
          </Form.Item>
        ) : (
          <Form.Item name="old" label="当前密码" rules={[{ required: true }]}>
            <Input.Password autoComplete="current-password" />
          </Form.Item>
        )}
        <Form.Item
          name="password"
          label={login ? '密码' : '新密码'}
          rules={[
            { required: true },
            ...(!login ? [{ min: 8, max: 128 }] : []),
          ]}
        >
          <Input.Password
            autoComplete={login ? 'current-password' : 'new-password'}
          />
        </Form.Item>
        <Button block type="primary" htmlType="submit" loading={busy}>
          {login ? '登录' : '保存新密码'}
        </Button>
      </Form>
    </Card>
  );
  if (login)
    return (
      <main className="login-page">
        <div className="login-panel">
          <section className="login-brand" aria-label="山雀企业项目工作台">
            <div className="login-wordmark">
              <img className="login-mark" src="/static/mark.svg" alt="山雀" />
              <strong>山雀</strong>
            </div>
            <div className="login-intro">
              <h2>企业项目工作台</h2>
              <div className="login-timeline" aria-hidden="true">
                <i />
                <i />
                <i />
                <i />
                <i />
                <i />
              </div>
            </div>
          </section>
          <section className="login-fields" aria-label="账号登录">
            {authForm}
          </section>
        </div>
      </main>
    );
  const menu = [
    { path: '/', name: '项目总览', icon: <HomeOutlined /> },
    { path: '/gantt', name: '甘特图', icon: <CalendarOutlined /> },
    { path: '/todo', name: '我的待办', icon: <CheckSquareOutlined /> },
    { path: '/team/members', name: '团队人员', icon: <TeamOutlined /> },
  ];
  const teamNext =
    path === '/gantt'
      ? 'work.gantt'
      : path === '/todo'
        ? 'work.todo'
        : path === '/team/members'
          ? 'teams.members'
          : 'work.overview';
  let content: React.ReactNode;
  if (error)
    content = (
      <Result
        status={
          error.status === 403 ? '403' : error.status === 404 ? '404' : 'error'
        }
        title={error.message}
        extra={<Button onClick={reload}>刷新页面</Button>}
      />
    );
  else if (
    !data ||
    dataPath !== path + location.search ||
    dataTeam !== session.team?.id
  )
    content = (
      <div className="page-loading">
        <Spin size="large" />
      </div>
    );
  else if (path === '/') content = <Overview data={data} />;
  else if (path === '/gantt' && data.chart)
    content = <Gantt data={data} chart={data.chart} />;
  else if (path === '/todo')
    content = (
      <PageContainer title={<PageTitle kind="todo">我的待办</PageTitle>}>
        <Card>
          <Tabs
            activeKey={todoFilter}
            onChange={setTodoFilter}
            items={[
              {
                key: 'pending',
                label: `未完成 ${(data.items || []).filter((t) => t.status !== '已完成').length}`,
              },
              { key: 'done', label: '已完成' },
              { key: 'all', label: '全部' },
            ]}
          />
          <Tasks
            todo
            tasks={(data.items || []).filter(
              (t) =>
                todoFilter === 'all' ||
                (todoFilter === 'done'
                  ? t.status === '已完成'
                  : t.status !== '已完成'),
            )}
          />
        </Card>
      </PageContainer>
    );
  else if (/^\/projects\/\d+$/.test(path) && data.p)
    content = <ProjectPage data={data} p={data.p} />;
  else if (path.startsWith('/projects/'))
    content = (
      <PageContainer title="编辑">
        <RecordEditor
          path={path}
          onClose={() => history.push(data.p ? `/projects/${data.p.id}` : '/')}
          afterSave={() =>
            history.push(data.p ? `/projects/${data.p.id}` : '/')
          }
        />
      </PageContainer>
    );
  else if (password)
    content = <PageContainer title="修改密码">{authForm}</PageContainer>;
  else content = <People data={data} path={path} />;
  return (
    <WorkspaceContext.Provider
      value={{ session, submit, reload, go: (path) => history.push(path) }}
    >
      <ProLayout
        title="山雀"
        logo={<img className="login-mark" src="/static/mark.svg" alt="山雀" />}
        layout="side"
        navTheme="light"
        token={{
          sider: {
            colorMenuBackground: '#142f2c',
            colorTextMenuTitle: '#ffffff',
            colorTextMenu: '#c7d8cf',
            colorTextMenuSecondary: '#b6cabe',
            colorTextMenuSelected: '#d7efc9',
            colorTextMenuItemHover: '#ffffff',
            colorTextMenuActive: '#ffffff',
            colorBgMenuItemSelected: '#284b40',
            colorBgMenuItemHover: '#214039',
            colorBgMenuItemActive: '#284b40',
            colorTextCollapsedButton: '#c7d8cf',
            colorTextCollapsedButtonHover: '#ffffff',
          },
        }}
        fixedHeader
        fixSiderbar
        siderWidth={208}
        location={{ pathname: path }}
        route={{ routes: menu }}
        menuItemRender={(item, dom) => (
          <a
            href={item.path}
            onClick={(e) => {
              e.preventDefault();
              history.push(item.path || '/');
            }}
          >
            {dom}
          </a>
        )}
        headerTitleRender={(logo, title) => (
          <a
            className="brand"
            href="/"
            onClick={(e) => {
              e.preventDefault();
              history.push('/');
            }}
          >
            {logo}
            {title}
          </a>
        )}
        menuFooterRender={(props) => (
          <div className="account-footer">
            <Dropdown
              trigger={['click']}
              placement="topLeft"
              menu={{
                items: [
                  {
                    key: 'teams',
                    type: 'group',
                    label: '切换团队',
                    children: session.teams.map((t) => ({
                      key: `team-${t.id}`,
                      icon: <TeamOutlined />,
                      label: t.name + (t.id === session.team?.id ? ' ✓' : ''),
                      onClick: () =>
                        void submit('/teams/switch', {
                          team_id: t.id,
                          next: teamNext,
                        }).catch(() => {}),
                    })),
                  },
                  { type: 'divider' },
                  ...(session.user?.admin
                    ? [
                        {
                          key: 'team-admin',
                          label: '团队管理',
                          icon: <ApartmentOutlined />,
                          onClick: () => history.push('/teams'),
                        },
                        {
                          key: 'accounts',
                          label: '用户账户',
                          icon: <UserOutlined />,
                          onClick: () => history.push('/accounts'),
                        },
                      ]
                    : []),
                  {
                    key: 'password',
                    label: '修改密码',
                    icon: <LockOutlined />,
                    onClick: () => history.push('/password'),
                  },
                  {
                    key: 'logout',
                    label: '退出登录',
                    icon: <LogoutOutlined />,
                    onClick: () => void submit('/logout', {}).catch(() => {}),
                  },
                ],
              }}
            >
              <Button type="text" className="account-button">
                <Avatar size="small" icon={<UserOutlined />} />
                {!props?.collapsed && (
                  <>
                    <span className="account-copy">
                      <strong>{session.user?.name}</strong>
                      <small>{session.team?.name || '尚未加入团队'}</small>
                    </span>
                    <DownOutlined />
                  </>
                )}
              </Button>
            </Dropdown>
          </div>
        )}
      >
        <div key={path + location.search + String(session.team?.id)}>
          {content}
        </div>
      </ProLayout>
    </WorkspaceContext.Provider>
  );
}
