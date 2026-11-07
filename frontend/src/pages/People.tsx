import { PageContainer, ProTable } from '@ant-design/pro-components';
import {
  Button,
  Card,
  Form,
  Input,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Upload,
} from 'antd';
import { useState } from 'react';
import { Editor, options } from '../components/common';
import PageTitle from '../components/PageTitle';
import ProjectTypeIcon from '../components/ProjectTypeIcon';
import { useWorkspace } from '../context';
import type { PageData, Person, Team } from '../types';

function roleTag(role: string) {
  return (
    <Tag
      className={`team-role-tag team-role-${role === '主管' ? 'manager' : role === '总监' ? 'director' : 'member'}`}
    >
      {`团队${role}`}
    </Tag>
  );
}

export default function People({
  data,
  path,
}: {
  data: PageData;
  path: string;
}) {
  const { session, submit, go } = useWorkspace();
  const [edit, setEdit] = useState<Person | Team | 'new'>();
  const [passwordUser, setPasswordUser] = useState<Person>();
  const [savingRole, setSavingRole] = useState<number>();
  const [adding, setAdding] = useState(false);
  const [linking, setLinking] = useState(false);
  const accounts = path === '/accounts';
  const teamList = path === '/teams';
  const teamAdmin = path.startsWith('/teams/');
  const team = data.team;
  const source = teamAdmin ? 'team-admin' : '';
  const memberPath = `/teams/${team?.id}/members`;
  return (
    <PageContainer
      title={
        <PageTitle
          kind={
            accounts ? 'accounts' : teamList || teamAdmin ? 'teams' : 'members'
          }
        >
          {accounts
            ? '用户账户'
            : teamList
              ? '团队管理'
              : teamAdmin
                ? team?.name
                : '团队人员'}
        </PageTitle>
      }
      onBack={teamAdmin ? () => go('/teams') : undefined}
      extra={
        accounts || teamList ? (
          <Space>
            {accounts && (
              <>
                <Button href="/accounts/template.xlsx">下载导入模板</Button>
                <Upload
                  accept=".xlsx"
                  showUploadList={false}
                  beforeUpload={(file) => {
                    const form = new FormData();
                    form.set('file', file);
                    void submit('/accounts/import', form, false).catch(
                      () => {},
                    );
                    return false;
                  }}
                >
                  <Button>导入账户</Button>
                </Upload>
              </>
            )}
            <Button type="primary" onClick={() => setEdit('new')}>
              {accounts ? '新建账户' : '新建团队'}
            </Button>
          </Space>
        ) : data.can_manage ? (
          <Space>
            {teamAdmin && (
              <Button onClick={() => setEdit(team)}>重命名团队</Button>
            )}
            <Button type="primary" onClick={() => setAdding(true)}>
              添加人员
            </Button>
          </Space>
        ) : undefined
      }
    >
      {teamList ? (
        <ProTable<Team>
          rowKey="id"
          headerTitle="团队"
          dataSource={data.teams}
          search={false}
          pagination={false}
          options={false}
          columns={[
            {
              title: '团队名称',
              dataIndex: 'name',
              render: (_, t) => (
                <Button
                  type="link"
                  className="text-link"
                  onClick={() => go(`/teams/${t.id}`)}
                >
                  {t.name}
                </Button>
              ),
            },
            { title: '人员', dataIndex: 'members' },
            { title: '项目', dataIndex: 'projects' },
          ]}
        />
      ) : (
        <ProTable<Person>
          rowKey="id"
          headerTitle={accounts ? '全部账户' : team?.name}
          dataSource={data.staff}
          search={false}
          pagination={{ pageSize: 20, hideOnSinglePage: true }}
          options={false}
          scroll={{ x: 650 }}
          columns={[
            {
              title: '姓名',
              dataIndex: 'name',
              render: (_, u) => (
                <Space>
                  {u.name}
                  {accounts && !!u.admin && <Tag>管理员</Tag>}
                </Space>
              ),
            },
            { title: '登录账号', dataIndex: 'login' },
            {
              title: accounts ? '账户状态' : '团队角色',
              render: (_, u) =>
                accounts ? (
                  <Tag
                    color={u.active ? 'success' : 'default'}
                    className={u.active ? 'status-completed' : undefined}
                  >
                    {u.active ? '启用' : '停用'}
                  </Tag>
                ) : session.user?.admin ? (
                  <Select
                    aria-label={`${u.name}的团队角色`}
                    value={u.role}
                    variant="borderless"
                    style={{ width: 140 }}
                    loading={savingRole === u.id}
                    disabled={savingRole !== undefined}
                    options={['成员', '主管', '总监'].map((value) => ({
                      value,
                      label: roleTag(value),
                    }))}
                    onChange={async (role) => {
                      setSavingRole(u.id);
                      try {
                        await submit(
                          memberPath,
                          { person_id: u.id, role, source },
                          false,
                        );
                      } catch {
                      } finally {
                        setSavingRole(undefined);
                      }
                    }}
                  />
                ) : (
                  roleTag(u.role || '成员')
                ),
            },
            {
              title: '操作',
              render: (_, u) =>
                accounts ? (
                  <Space>
                    <Button type="link" onClick={() => setEdit(u)}>
                      编辑账户
                    </Button>
                    <Button type="link" onClick={() => setPasswordUser(u)}>
                      修改密码
                    </Button>
                    <Popconfirm
                      title={`${u.admin ? '取消' : '授予'} ${u.name} 的系统管理员权限？`}
                      onConfirm={() =>
                        submit('/accounts/admin', {
                          id: u.id,
                          admin: u.admin ? 0 : 1,
                        })
                      }
                    >
                      <Button type="link" disabled={!u.active && !u.admin}>
                        {u.admin ? '取消管理员' : '设为管理员'}
                      </Button>
                    </Popconfirm>
                  </Space>
                ) : (
                  <Space>
                    {data.can_manage &&
                      (session.user?.admin || u.role === '成员') && (
                        <Popconfirm
                          title={`从团队移除 ${u.name}？`}
                          onConfirm={() =>
                            submit(
                              memberPath,
                              { person_id: u.id, remove: 1, source },
                              false,
                            )
                          }
                        >
                          <Button type="link" danger>
                            移除
                          </Button>
                        </Popconfirm>
                      )}
                  </Space>
                ),
            },
          ]}
        />
      )}
      {teamAdmin && (
        <Card
          title="团队项目"
          className="section-card"
          extra={<Button onClick={() => setLinking(true)}>关联项目</Button>}
        >
          <Table
            rowKey="id"
            pagination={false}
            dataSource={data.projects}
            columns={[
              {
                title: '项目名称',
                dataIndex: 'name',
                render: (_, p) => (
                  <Space size={8}>
                    <ProjectTypeIcon type={p.project_type} />
                    {p.name}
                  </Space>
                ),
              },
              {
                title: '操作',
                render: (_, p) => (
                  <Popconfirm
                    title="解除此项目与团队的关联？"
                    onConfirm={() =>
                      submit(
                        `/teams/${team?.id}/projects`,
                        { project_id: p.id, remove: 1 },
                        false,
                      )
                    }
                  >
                    <Button type="link" danger>
                      解除关联
                    </Button>
                  </Popconfirm>
                ),
              },
            ]}
          />
        </Card>
      )}
      {passwordUser && accounts && (
        <Editor
          title={`修改密码 · ${passwordUser.name}`}
          onClose={() => setPasswordUser(undefined)}
          onSave={(values) =>
            submit(
              '/accounts/password',
              { id: passwordUser.id, password: values.password },
              false,
            )
          }
        >
          <Form.Item
            name="password"
            label="新密码"
            rules={[{ required: true }, { min: 8, max: 128 }]}
          >
            <Input.Password autoComplete="new-password" />
          </Form.Item>
          <Form.Item
            name="confirm"
            label="确认新密码"
            dependencies={['password']}
            rules={[
              { required: true },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  return !value || getFieldValue('password') === value
                    ? Promise.resolve()
                    : Promise.reject(new Error('两次输入的密码不一致'));
                },
              }),
            ]}
          >
            <Input.Password autoComplete="new-password" />
          </Form.Item>
        </Editor>
      )}
      {edit && accounts && (
        <Editor
          title={edit === 'new' ? '新建账户' : '编辑账户'}
          initial={edit === 'new' ? { active: 1 } : { ...edit }}
          onClose={() => setEdit(undefined)}
          onSave={async (values) =>
            submit(
              '/accounts/save',
              { ...values, id: edit === 'new' ? '' : edit.id },
              false,
            )
          }
        >
          {edit === 'new' && (
            <Form.Item
              name="login"
              label="登录账号"
              rules={[{ required: true }]}
            >
              <Input maxLength={80} />
            </Form.Item>
          )}
          <Form.Item name="name" label="姓名" rules={[{ required: true }]}>
            <Input maxLength={80} />
          </Form.Item>
          <Form.Item
            name="password"
            label={edit === 'new' ? '初始密码' : '新密码（留空保留原密码）'}
            rules={[{ required: edit === 'new' }, { min: 8, max: 128 }]}
          >
            <Input.Password autoComplete="new-password" />
          </Form.Item>
          {edit !== 'new' && (
            <Form.Item name="active" label="账户状态">
              <Select
                options={[
                  { value: 1, label: '启用' },
                  { value: 0, label: '停用' },
                ]}
              />
            </Form.Item>
          )}
        </Editor>
      )}
      {edit &&
        (teamList ||
          (teamAdmin && 'name' in Object(edit) && !(edit as Person).login)) &&
        !accounts && (
          <Editor
            title={edit === 'new' ? '新建团队' : '重命名团队'}
            initial={edit === 'new' ? {} : { ...edit }}
            onClose={() => setEdit(undefined)}
            onSave={async (values) =>
              submit(
                '/teams/save',
                { ...values, id: edit === 'new' ? '' : edit.id },
                edit === 'new',
              )
            }
          >
            <Form.Item
              name="name"
              label="团队名称"
              rules={[{ required: true }]}
            >
              <Input maxLength={80} />
            </Form.Item>
            {edit === 'new' && (
              <Form.Item
                name="supervisor"
                label="团队主管"
                rules={[{ required: true }]}
              >
                <Select
                  showSearch={{ optionFilterProp: 'label' }}
                  options={options(data.staff)}
                />
              </Form.Item>
            )}
          </Editor>
        )}
      {adding && (
        <Editor
          title="添加团队人员"
          initial={{ role: '成员' }}
          onClose={() => setAdding(false)}
          onSave={async (values) =>
            submit(memberPath, { ...values, source }, false)
          }
        >
          <Form.Item
            name="person_id"
            label="用户账户"
            rules={[{ required: true }]}
          >
            <Select
              showSearch={{ optionFilterProp: 'label' }}
              options={options(data.available)}
            />
          </Form.Item>
          {!!session.user?.admin && (
            <Form.Item name="role" label="团队角色">
              <Select
                options={['成员', '主管', '总监'].map((value) => ({
                  value,
                  label: roleTag(value),
                }))}
              />
            </Form.Item>
          )}
        </Editor>
      )}
      {linking && (
        <Editor
          title="关联项目"
          onClose={() => setLinking(false)}
          onSave={async (values) =>
            submit(`/teams/${team?.id}/projects`, values, false)
          }
        >
          <Form.Item
            name="project_id"
            label="项目"
            rules={[{ required: true }]}
          >
            <Select
              showSearch={{ optionFilterProp: 'label' }}
              options={data.available_projects?.map((p) => ({
                value: p.id,
                label: p.name,
              }))}
            />
          </Form.Item>
        </Editor>
      )}
    </PageContainer>
  );
}
