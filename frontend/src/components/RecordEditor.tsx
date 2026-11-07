import {
  Alert,
  Button,
  DatePicker,
  Form,
  Input,
  Popconfirm,
  Select,
  Spin,
  Tag,
} from 'antd';
import dayjs from 'dayjs';
import { useEffect, useState } from 'react';
import { readPage } from '../api';
import { useWorkspace } from '../context';
import type { PageData, Task } from '../types';
import { Editor, options } from './common';
import ProjectTypeIcon, { projectTypes } from './ProjectTypeIcon';

function TaskFields({ data }: { data: PageData }) {
  const form = Form.useFormInstance();
  const mid = Form.useWatch('milestone_id', form);
  const node = data.ms?.find((m) => m.id === mid);
  return (
    <>
      <Form.Item name="name" label="任务名称" rules={[{ required: true }]}>
        <Input maxLength={120} autoFocus />
      </Form.Item>
      <Form.Item
        name="assignees"
        label="待办人"
        rules={[{ required: true, type: 'array', min: 1 }]}
      >
        <Select
          mode="multiple"
          options={options(data.staff)}
          showSearch={{ optionFilterProp: 'label' }}
        />
      </Form.Item>
      <Form.Item name="milestone_id" label="关联节点">
        <Select
          allowClear
          options={data.ms?.map((m) => ({
            value: m.id,
            label: `${m.name} · ${m.planned}`,
          }))}
          onChange={(id) => {
            const selected = data.ms?.find((m) => m.id === id);
            if (selected) form.setFieldValue('due', dayjs(selected.planned));
          }}
        />
      </Form.Item>
      <Form.Item
        name="start_date"
        label="开始日期"
        rules={[{ required: true }]}
      >
        <DatePicker allowClear={false} />
      </Form.Item>
      <Form.Item name="due" label="截止日期" rules={[{ required: true }]}>
        <DatePicker allowClear={false} />
      </Form.Item>
      {node && <Tag color="blue">节点计划日 {node.planned}</Tag>}
    </>
  );
}

export default function RecordEditor({
  path,
  onClose,
  afterSave,
}: {
  path: string;
  onClose: () => void;
  afterSave?: () => void;
}) {
  const { session, submit } = useWorkspace();
  const [data, setData] = useState<PageData>();
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    readPage(path, controller.signal)
      .then((r) => setData(r.data))
      .catch((e) => {
        if (e.name !== 'AbortError') setError(e.message);
      });
    return () => controller.abort();
  }, [path]);
  if (error)
    return (
      <Editor title="无法打开" onClose={onClose} onSave={async () => onClose()}>
        <Alert type="error" title={error} />
      </Editor>
    );
  if (!data)
    return (
      <div className="loading-overlay">
        <Spin size="large" />
      </div>
    );
  const task = path.includes('/tasks/');
  const project = data.kind === 'project';
  const record = project ? data.p : data.item;
  const initial = task
    ? {
        ...data.item,
        assignees: data.selected,
        start_date: dayjs((data.item as Task)?.start_date || session.today),
        due: dayjs(
          (data.item as Task)?.due || data.ms?.[0]?.planned || session.today,
        ),
        milestone_id: data.item
          ? (data.item as Task).milestone_id
          : data.ms?.[0]?.id,
      }
    : project
      ? {
          ...data.p,
          leads: data.selected,
          start_date: dayjs(data.p?.start_date || session.today),
          end_date: dayjs(data.p?.end_date || session.today),
        }
      : {
          ...data.item,
          planned: dayjs(
            (data.item as { planned?: string })?.planned || session.today,
          ),
          forecast: (data.item as { forecast?: string })?.forecast
            ? dayjs((data.item as { forecast: string }).forecast)
            : undefined,
          key: data.candidates?.find((t) => t.is_key)?.id,
        };
  const finish = async (values: Record<string, unknown>) => {
    await submit(
      path,
      { ...values, revision: (data.item as Task)?.revision },
      false,
    );
    afterSave?.();
  };
  return (
    <Editor
      title={
        (record ? '编辑' : '新建') + (task ? '任务' : project ? '项目' : '节点')
      }
      initial={initial}
      onClose={onClose}
      onSave={finish}
      extra={
        !project &&
        data.item && (
          <Popconfirm
            title={task ? '删除此任务？' : '删除此节点？关联任务会保留。'}
            onConfirm={async () => {
              await finish({ delete: 1 });
              onClose();
            }}
          >
            <Button danger>删除</Button>
          </Popconfirm>
        )
      }
    >
      {task ? (
        <TaskFields data={data} />
      ) : (
        <>
          <Form.Item
            name="name"
            label={project ? '项目名称' : '节点名称'}
            rules={[{ required: true }]}
          >
            <Input maxLength={80} autoFocus />
          </Form.Item>
          {project ? (
            <>
              <Form.Item
                name="project_type"
                label="项目类型"
                rules={[{ required: true, message: '请选择项目类型' }]}
              >
                <Select
                  placeholder="选择项目类型"
                  options={projectTypes.map((type) => ({
                    value: type,
                    label: (
                      <span className="project-type-option">
                        <ProjectTypeIcon type={type} />
                        {type}
                      </span>
                    ),
                  }))}
                />
              </Form.Item>
              <Form.Item name="description" label="项目说明">
                <Input.TextArea rows={3} maxLength={2000} />
              </Form.Item>
              <div className="date-pair">
                <Form.Item
                  name="start_date"
                  label="开始日期"
                  rules={[{ required: true }]}
                >
                  <DatePicker />
                </Form.Item>
                <Form.Item
                  name="end_date"
                  label="结束日期"
                  rules={[{ required: true }]}
                >
                  <DatePicker />
                </Form.Item>
              </div>
              {session.user?.role === '主管' && (
                <Form.Item
                  name="leads"
                  label="项目负责人"
                  rules={[{ required: true, type: 'array', min: 1 }]}
                >
                  <Select
                    mode="multiple"
                    options={options(data.staff)}
                    showSearch={{ optionFilterProp: 'label' }}
                  />
                </Form.Item>
              )}
            </>
          ) : (
            <>
              <div className="date-pair">
                <Form.Item
                  name="planned"
                  label="计划日期"
                  rules={[{ required: true }]}
                >
                  <DatePicker />
                </Form.Item>
                <Form.Item name="forecast" label="预计日期">
                  <DatePicker />
                </Form.Item>
              </div>
              <Form.Item name="key" label="节点任务">
                <Select
                  allowClear
                  options={data.candidates?.map((t) => ({
                    value: t.id,
                    label: t.name,
                  }))}
                />
              </Form.Item>
            </>
          )}
        </>
      )}
    </Editor>
  );
}
