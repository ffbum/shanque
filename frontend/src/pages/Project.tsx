import { PageContainer, ProTable } from '@ant-design/pro-components';
import {
  Button,
  Card,
  Form,
  Input,
  Popconfirm,
  Select,
  Space,
  Tabs,
  Tag,
} from 'antd';
import { useState } from 'react';
import { Distance, Editor, names, options, Status } from '../components/common';
import ProjectTypeIcon from '../components/ProjectTypeIcon';
import RecordEditor from '../components/RecordEditor';
import Tasks from '../components/Tasks';
import { useWorkspace } from '../context';
import type { Milestone, PageData, Project } from '../types';

export default function ProjectPage({
  data,
  p,
}: {
  data: PageData;
  p: Project;
}) {
  const { session, submit, go } = useWorkspace();
  const [edit, setEdit] = useState<string>();
  const [add, setAdd] = useState(false);
  const [progress, setProgress] = useState(false);
  const mutable = data.manage && !p.closed_at;
  const supervisor = session.user?.role === '主管';
  return (
    <PageContainer
      title={
        <Space size={8}>
          <ProjectTypeIcon type={p.project_type} />
          {p.name}
        </Space>
      }
      onBack={() => go('/')}
      tags={<Status value={p.state} />}
      subTitle={`${p.start_date || '未设日期'} — ${p.end_date || '未设日期'}`}
      extra={
        mutable ? (
          <Space>
            <Button onClick={() => setEdit(`/projects/${p.id}/edit`)}>
              项目设置
            </Button>
            <Popconfirm
              title="确认结项？剩余普通任务可继续跟踪。"
              onConfirm={() => submit(`/projects/${p.id}/close`, {}, false)}
            >
              <Button disabled={p.pending.length > 0}>结项</Button>
            </Popconfirm>
            <Button
              type="primary"
              onClick={() => setEdit(`/projects/${p.id}/tasks/new`)}
            >
              新建任务
            </Button>
          </Space>
        ) : undefined
      }
    >
      <Card className="section-card">
        <div className="project-summary">
          <div>
            <span className="muted">项目负责人</span>
            <p>{names(p.leads)}</p>
          </div>
          <div>
            <span className="muted">关键节点</span>
            <p>
              {p.reached} / {p.milestones.length}
            </p>
          </div>
          <div>
            <span className="muted">任务完成</span>
            <p>
              {p.done} / {p.tasks.length}
            </p>
          </div>
          <div className="progress-copy">
            <span className="muted">最新进展</span>
            <p>{p.progress || '—'}</p>
            {supervisor && (
              <Button
                className="text-link"
                type="link"
                size="small"
                onClick={() => setProgress(true)}
              >
                更新进展
              </Button>
            )}
          </div>
        </div>
        {p.description?.trim() &&
          p.description.trim() !== p.progress?.trim() && (
            <p className="muted wrap-text">{p.description}</p>
          )}
      </Card>
      <Tabs
        items={[
          {
            key: 'tasks',
            label: `项目任务 ${p.tasks.length}`,
            children: (
              <Card>
                <Tasks
                  tasks={p.tasks}
                  manage={data.manage}
                  closed={!!p.closed_at}
                />
              </Card>
            ),
          },
          {
            key: 'milestones',
            label: `关键节点 ${p.milestones.length}`,
            children: (
              <ProTable<Milestone>
                rowKey="id"
                headerTitle="关键节点"
                search={false}
                pagination={false}
                options={false}
                dataSource={p.milestones}
                scroll={{ x: 900 }}
                toolBarRender={() =>
                  supervisor && !p.closed_at
                    ? [
                        <Button
                          key="new"
                          type="primary"
                          onClick={() =>
                            setEdit(`/projects/${p.id}/milestones/new`)
                          }
                        >
                          新建节点
                        </Button>,
                      ]
                    : []
                }
                columns={[
                  {
                    title: '节点名称',
                    dataIndex: 'name',
                    render: (_, m) =>
                      supervisor && !m.achieved && !p.closed_at ? (
                        <Button
                          type="link"
                          className="text-link"
                          onClick={() =>
                            setEdit(`/projects/${p.id}/milestones/${m.id}/edit`)
                          }
                        >
                          {m.name}
                        </Button>
                      ) : (
                        m.name
                      ),
                  },
                  { title: '计划日期', dataIndex: 'planned' },
                  { title: '预计日期', render: (_, m) => m.forecast || '—' },
                  {
                    title: '当前进度',
                    render: (_, m) => (
                      <Distance
                        planned={m.planned}
                        today={session.today}
                        achieved={m.achieved}
                      />
                    ),
                  },
                  {
                    title: '节点任务',
                    render: (_, m) => m.key?.name || '手动确认',
                  },
                  {
                    title: '关联任务',
                    render: (_, m) =>
                      `${m.tasks.length - m.remaining.length} / ${m.tasks.length}`,
                  },
                  {
                    title: '达成情况',
                    render: (_, m) =>
                      m.achieved ? (
                        <span>
                          {m.achieved.slice(0, 10)} · {m.actor_name}
                        </span>
                      ) : data.manage ? (
                        <Popconfirm
                          title={`确认达成“${m.name}”？`}
                          description={`将同步完成 ${m.remaining.length} 项未完成的关联任务。`}
                          onConfirm={() =>
                            submit(
                              `/projects/${p.id}/milestones/${m.id}/confirm`,
                              { force: 1 },
                              false,
                            )
                          }
                        >
                          <Button size="small">
                            {m.key || m.remaining.length
                              ? '强制完成'
                              : '确认达成'}
                          </Button>
                        </Popconfirm>
                      ) : (
                        '—'
                      ),
                  },
                ]}
              />
            ),
          },
          {
            key: 'members',
            label: `项目成员 ${p.members.length}`,
            children: (
              <Card
                title="项目成员"
                extra={
                  mutable && (
                    <Button onClick={() => setAdd(true)}>添加成员</Button>
                  )
                }
              >
                <div className="member-list">
                  {p.members.map((u) => (
                    <div key={u.id}>
                      <span>
                        {u.name} {!!u.lead && <Tag color="blue">负责人</Tag>}
                      </span>
                      {mutable && !u.lead && (
                        <Popconfirm
                          title={`移除 ${u.name}？`}
                          onConfirm={() =>
                            submit(
                              `/projects/${p.id}/members`,
                              { remove: u.id },
                              false,
                            )
                          }
                        >
                          <Button type="link" danger>
                            移除
                          </Button>
                        </Popconfirm>
                      )}
                    </div>
                  ))}
                </div>
              </Card>
            ),
          },
        ]}
      />
      {edit && <RecordEditor path={edit} onClose={() => setEdit(undefined)} />}
      {add && (
        <Editor
          title="添加项目成员"
          onClose={() => setAdd(false)}
          onSave={async (values) =>
            submit(`/projects/${p.id}/members`, values, false)
          }
        >
          <Form.Item name="members" label="成员" rules={[{ required: true }]}>
            <Select
              mode="multiple"
              options={options(
                data.staff?.filter(
                  (u) => !p.members.some((m) => m.id === u.id),
                ),
              )}
              showSearch={{ optionFilterProp: 'label' }}
            />
          </Form.Item>
        </Editor>
      )}
      {progress && (
        <Editor
          title="更新进展"
          initial={{ progress: p.progress }}
          onClose={() => setProgress(false)}
          onSave={async (values) =>
            submit(`/projects/${p.id}/progress`, values, false)
          }
        >
          <Form.Item name="progress">
            <Input.TextArea rows={5} maxLength={600} />
          </Form.Item>
        </Editor>
      )}
    </PageContainer>
  );
}
