import { ExportOutlined, PlusOutlined } from '@ant-design/icons';
import { PageContainer, ProTable } from '@ant-design/pro-components';
import {
  Button,
  Card,
  Col,
  Form,
  Input,
  Progress,
  Row,
  Select,
  Space,
  Statistic,
  Tooltip,
} from 'antd';
import { useState } from 'react';
import {
  Distance,
  days,
  Editor,
  names,
  Status,
  statuses,
} from '../components/common';
import PageTitle from '../components/PageTitle';
import ProjectTypeFilter, {
  matchesProjectType,
  type TypeFilter,
} from '../components/ProjectTypeFilter';
import ProjectTypeIcon from '../components/ProjectTypeIcon';
import RecordEditor from '../components/RecordEditor';
import { TaskStatusEditor } from '../components/Tasks';
import { useWorkspace } from '../context';
import type { PageData, Project, Task } from '../types';

interface LedgerRow {
  key: string;
  project: Project;
  task?: Task;
  children?: LedgerRow[];
}

function adjacentMilestones(project: Project) {
  const previous = project.milestones.filter((node) => node.achieved).at(-1);
  const next = project.milestones.find((node) => !node.achieved);
  return [
    ...(previous ? [{ node: previous, label: '上一个' }] : []),
    ...(next ? [{ node: next, label: '下一个' }] : []),
  ];
}

function nodeColor(
  planned: string | undefined,
  achieved: string | undefined,
  today: string,
) {
  return achieved
    ? 'node-done'
    : planned && planned < today
      ? 'node-overdue'
      : 'node-pending';
}

export default function Overview({ data }: { data: PageData }) {
  const { session, go, submit } = useWorkspace();
  const [filter, setFilter] = useState('全部项目');
  const [query, setQuery] = useState('');
  const [projectType, setProjectType] = useState<TypeFilter>();
  const [create, setCreate] = useState(false);
  const [progress, setProgress] = useState<Project>();
  const [editTask, setEditTask] = useState<string>();
  const [change, setChange] = useState<{ task: Task; status: string }>();
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const canManage = (p: Project) =>
    session.user?.role === '主管' ||
    p.leads.some((u) => u.id === session.user?.id);
  const scopedProjects = (data.projects || []).filter(
    (p) =>
      matchesProjectType(p.project_type, projectType) && p.name.includes(query),
  );
  const projects = scopedProjects.filter(
    (p) => filter === '全部项目' || p.state === filter,
  );
  const metrics: [string, number][] = [
    ['进行中项目', projects.filter((p) => !p.closed_at).length],
    ['已逾期节点', projects.reduce((sum, p) => sum + p.overdue.length, 0)],
    [
      '7 天内到期节点',
      projects.reduce(
        (sum, p) =>
          sum +
          p.upcoming.filter((m) => days(m.planned, session.today) <= 7).length,
        0,
      ),
    ],
  ];
  return (
    <PageContainer
      title={<PageTitle kind="overview">项目总览</PageTitle>}
      extra={
        session.user?.role === '主管' ? (
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setCreate(true)}
          >
            新建项目
          </Button>
        ) : undefined
      }
    >
      <Row gutter={[16, 16]} className="metrics">
        {metrics.map(([label, value]) => (
          <Col key={label} xs={24} sm={8}>
            <Card>
              <Statistic title={label} value={value} />
            </Card>
          </Col>
        ))}
      </Row>
      <ProTable<LedgerRow>
        className="overview-ledger"
        headerTitle="项目台账"
        rowKey="key"
        rowClassName={(row) =>
          row.task ? 'ledger-task-row' : 'ledger-project-row'
        }
        dataSource={projects.map((project) => ({
          key: `project-${project.id}`,
          project,
          children: project.tasks.length
            ? project.tasks.map((task) => ({
                key: `task-${task.id}`,
                project,
                task,
              }))
            : undefined,
        }))}
        search={false}
        pagination={false}
        options={{ reload: false, density: true, setting: true }}
        scroll={{ x: 1150 }}
        toolBarRender={() => [
          <Input.Search
            key="query"
            aria-label="搜索项目"
            placeholder="搜索项目"
            allowClear
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{ width: 190 }}
          />,
          <ProjectTypeFilter
            key="projectType"
            value={projectType}
            onChange={setProjectType}
          />,
          <Select
            key="filter"
            value={filter}
            onChange={setFilter}
            style={{ width: 145 }}
            options={['全部项目', '正常推进', '需关注', '已结项'].map(
              (label) => ({
                value: label,
                label: `${label} ${scopedProjects.filter((p) => label === '全部项目' || p.state === label).length}`,
              }),
            )}
          />,
        ]}
        expandable={{
          expandedRowKeys: projects
            .map((p) => `project-${p.id}`)
            .filter((key) => !collapsed.has(key)),
          onExpand: (expanded, row) =>
            setCollapsed((previous) => {
              const next = new Set(previous);
              if (expanded) next.delete(row.key);
              else next.add(row.key);
              return next;
            }),
          indentSize: 24,
          expandRowByClick: true,
        }}
        columns={[
          {
            title: '项目 / 任务',
            dataIndex: 'name',
            width: 240,
            render: (_, { project: p, task: t }) =>
              t ? (
                <div className="ledger-task-name">
                  {canManage(p) && !p.closed_at ? (
                    <Button
                      type="link"
                      className="text-link"
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditTask(`/projects/${p.id}/tasks/${t.id}/edit`);
                      }}
                    >
                      {t.name}
                    </Button>
                  ) : (
                    <span>{t.name}</span>
                  )}
                  {!!t.is_key && <span className="key-dot" title="节点任务" />}
                  <div className="muted">{names(t.assignees)}</div>
                </div>
              ) : (
                <div className="project-cell">
                  <div className="project-name-line">
                    <ProjectTypeIcon type={p.project_type} />
                    <strong>{p.name}</strong>
                    <Tooltip title="项目详情">
                      <Button
                        type="text"
                        size="small"
                        aria-label="项目详情"
                        icon={<ExportOutlined />}
                        onClick={(e) => {
                          e.stopPropagation();
                          go(`/projects/${p.id}`);
                        }}
                      />
                    </Tooltip>
                  </div>
                  <div className="muted">{names(p.leads)}</div>
                </div>
              ),
          },
          {
            title: '当前状态',
            className: 'ledger-status-cell',
            width: 130,
            render: (_, { project: p, task: t }) =>
              t ? (
                <Status value={t.status} />
              ) : (
                <div className="ledger-progress">
                  <div className="ledger-progress-heading">
                    <Status value={p.state} />
                  </div>
                  <Progress
                    percent={
                      p.milestones.length
                        ? Math.round((p.reached / p.milestones.length) * 100)
                        : 0
                    }
                    size="small"
                    showInfo={false}
                  />
                  <span className="muted">
                    节点 {p.reached}/{p.milestones.length}
                  </span>
                </div>
              ),
          },
          {
            title: '任务完成',
            key: 'taskCompletion',
            width: 150,
            render: (_, { project: p, task: t }) =>
              t ? (
                <div className="ledger-task-dates">
                  <div className="task-date-due">
                    <span>截止</span>
                    <time>{t.due}</time>
                  </div>
                  <div
                    className={
                      t.status === '已完成'
                        ? 'task-date-done'
                        : t.due < session.today
                          ? 'task-date-overdue'
                          : 'task-date-due'
                    }
                  >
                    {t.status === '已完成' ? (
                      <>
                        <span>完成</span>
                        <time>{t.done_at?.slice(0, 10) || '—'}</time>
                      </>
                    ) : (
                      <>
                        <span>{t.due < session.today ? '逾期' : '剩余'}</span>
                        <span>{Math.abs(days(t.due, session.today))} 天</span>
                      </>
                    )}
                  </div>
                </div>
              ) : (
                <div className="ledger-progress task-completion">
                  <span className="ledger-progress-heading">
                    {p.done} / {p.tasks.length}
                  </span>
                  <Progress
                    percent={
                      p.tasks.length
                        ? Math.round((p.done / p.tasks.length) * 100)
                        : 0
                    }
                    size="small"
                    showInfo={false}
                  />
                  <span aria-hidden="true" />
                </div>
              ),
          },
          {
            title: '关键节点',
            width: 240,
            render: (_, { project: p, task: t }) =>
              t ? (
                t.milestone_name ? (
                  <div
                    className={`milestone-line ledger-node ${nodeColor(t.planned, t.milestone_achieved, session.today)}`}
                  >
                    <div className="milestone-name">
                      <span>{t.milestone_name}</span>
                      <span className="muted">{t.planned}</span>
                    </div>
                    {t.planned && (
                      <Distance
                        planned={t.planned}
                        today={session.today}
                        achieved={t.milestone_achieved}
                      />
                    )}
                  </div>
                ) : (
                  <span className="muted">仅归属项目</span>
                )
              ) : (
                <div className="milestone-stack">
                  {p.milestones.length ? (
                    adjacentMilestones(p).map(({ node: m, label }) => (
                      <div
                        className={`milestone-line ledger-node ${nodeColor(m.planned, m.achieved, session.today)}`}
                        key={m.id}
                      >
                        <span
                          className={
                            'milestone-dot ' +
                            (m.achieved
                              ? 'done'
                              : m.planned < session.today
                                ? 'danger'
                                : '')
                          }
                        />
                        <div className="milestone-name">
                          <Tooltip
                            title={
                              m.forecast ? `预计 ${m.forecast}` : undefined
                            }
                          >
                            {m.name}
                          </Tooltip>
                          <span className="muted">
                            {label} · {m.planned}
                          </span>
                        </div>
                        <Distance
                          planned={m.planned}
                          today={session.today}
                          achieved={m.achieved}
                        />
                      </div>
                    ))
                  ) : (
                    <span className="muted">暂无节点</span>
                  )}
                </div>
              ),
          },
          {
            title: '最新进展',
            className: 'ledger-updates-cell',
            width: 330,
            render: (_, { project: p, task: t }) =>
              t ? (
                <div onClick={(e) => e.stopPropagation()}>
                  {t.note && <p className="wrap-text">{t.note}</p>}
                  {t.done_at && (
                    <div className="muted">
                      {t.finisher} · {t.done_at.slice(0, 10)}
                    </div>
                  )}
                  {session.user?.role !== '总监' &&
                    (canManage(p) ||
                      t.assignee_ids.includes(session.user?.id || 0)) && (
                      <Space size={0} wrap>
                        {statuses.map((status) => (
                          <Button
                            key={status}
                            type="link"
                            size="small"
                            disabled={
                              !!t.is_key &&
                              t.status === '已完成' &&
                              status !== '已完成'
                            }
                            onClick={() => setChange({ task: t, status })}
                          >
                            {status}
                          </Button>
                        ))}
                      </Space>
                    )}
                </div>
              ) : (
                <div onClick={(e) => e.stopPropagation()}>
                  <p className="wrap-text">{p.progress || '—'}</p>
                  {p.progress_at && (
                    <div className="muted">
                      {p.editor} · {p.progress_at.slice(0, 10)}
                    </div>
                  )}
                  {session.user?.role === '主管' && (
                    <Button
                      type="link"
                      size="small"
                      className="text-link"
                      onClick={() => setProgress(p)}
                    >
                      更新进展
                    </Button>
                  )}
                </div>
              ),
          },
        ]}
      />
      {editTask && (
        <RecordEditor path={editTask} onClose={() => setEditTask(undefined)} />
      )}
      {change && (
        <TaskStatusEditor
          change={change}
          onClose={() => setChange(undefined)}
        />
      )}
      {create && (
        <RecordEditor path="/projects/new" onClose={() => setCreate(false)} />
      )}
      {progress && (
        <Editor
          title="更新进展"
          initial={{ progress: progress.progress }}
          onClose={() => setProgress(undefined)}
          onSave={async (values) =>
            submit(`/projects/${progress.id}/progress`, values, false)
          }
        >
          <Form.Item name="progress" label={progress.name}>
            <Input.TextArea rows={5} maxLength={600} showCount autoFocus />
          </Form.Item>
        </Editor>
      )}
    </PageContainer>
  );
}
