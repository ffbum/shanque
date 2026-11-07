import { Button, Form, Input, Space, Table, Tooltip } from 'antd';
import { useState } from 'react';
import { useWorkspace } from '../context';
import type { Task } from '../types';
import { Distance, Editor, names, Status, statuses } from './common';
import ProjectTypeIcon from './ProjectTypeIcon';
import RecordEditor from './RecordEditor';

export default function Tasks({
  tasks,
  manage = false,
  closed = false,
  todo = false,
}: {
  tasks: Task[];
  manage?: boolean;
  closed?: boolean;
  todo?: boolean;
}) {
  const { session, go } = useWorkspace();
  const [edit, setEdit] = useState<string>();
  const [change, setChange] = useState<{ task: Task; status: string }>();
  return (
    <>
      <Table<Task>
        rowKey="id"
        size="middle"
        pagination={tasks.length > 20 ? { pageSize: 20 } : false}
        dataSource={tasks}
        scroll={{ x: 1050 }}
        columns={[
          {
            title: '任务名称',
            dataIndex: 'name',
            width: 240,
            render: (_, t) => (
              <div>
                {manage && !closed ? (
                  <Button
                    type="link"
                    className="text-link"
                    onClick={() =>
                      setEdit(`/projects/${t.project_id}/tasks/${t.id}/edit`)
                    }
                  >
                    {t.name}
                  </Button>
                ) : (
                  <span>{t.name}</span>
                )}
                {!!t.is_key && <span className="key-dot" title="节点任务" />}
                {todo && (
                  <div>
                    <Button
                      type="link"
                      size="small"
                      className="text-link muted"
                      onClick={() =>
                        go(`/projects/${t.project_id}?team=${t.team_id}`)
                      }
                    >
                      <ProjectTypeIcon type={t.project_type} /> {t.project_name}
                    </Button>
                  </div>
                )}
              </div>
            ),
          },
          { title: '待办人', width: 130, render: (_, t) => names(t.assignees) },
          {
            title: '截止日期',
            width: 135,
            render: (_, t) => (
              <div>
                {t.due}
                <div>
                  <Distance
                    planned={t.due}
                    today={session.today}
                    achieved={
                      t.status === '已完成' ? t.done_at || 'done' : undefined
                    }
                  />
                </div>
              </div>
            ),
          },
          {
            title: '关联节点',
            width: 150,
            render: (_, t) => t.milestone_name || '—',
          },
          {
            title: '状态',
            width: 100,
            render: (_, t) => <Status value={t.status} />,
          },
          {
            title: '最新说明',
            width: 210,
            render: (_, t) => (
              <Tooltip
                title={
                  t.done_at
                    ? `完成于 ${t.done_at.slice(0, 10)} · ${t.finisher || ''}`
                    : undefined
                }
              >
                <span className="wrap-text">{t.note || '—'}</span>
              </Tooltip>
            ),
          },
          {
            title: '更新状态',
            width: 290,
            render: (_, t) =>
              (
                todo
                  ? t.can_update
                  : session.user?.role !== '总监' &&
                    (manage || t.assignee_ids.includes(session.user?.id || 0))
              ) ? (
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
              ) : (
                '—'
              ),
          },
        ]}
      />
      {edit && <RecordEditor path={edit} onClose={() => setEdit(undefined)} />}
      {change && (
        <TaskStatusEditor
          change={change}
          todo={todo}
          onClose={() => setChange(undefined)}
        />
      )}
    </>
  );
}

export function TaskStatusEditor({
  change,
  todo = false,
  onClose,
}: {
  change: { task: Task; status: string };
  todo?: boolean;
  onClose: () => void;
}) {
  const { submit } = useWorkspace();
  return (
    <Editor
      title={`更新为${change.status}`}
      initial={{ note: change.task.note }}
      onClose={onClose}
      onSave={async (v) =>
        submit(
          `/projects/${change.task.project_id}/tasks/${change.task.id}/status`,
          {
            ...v,
            status: change.status,
            revision: change.task.revision,
            source: todo ? 'todo' : 'project',
          },
          false,
        )
      }
    >
      <p>{change.task.name}</p>
      <Form.Item
        name="note"
        label="说明"
        rules={[
          { required: change.status === '受阻', message: '请填写受阻原因' },
        ]}
      >
        <Input.TextArea autoFocus rows={4} maxLength={600} showCount />
      </Form.Item>
    </Editor>
  );
}
