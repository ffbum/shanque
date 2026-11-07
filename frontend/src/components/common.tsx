import { Alert, Button, Form, Modal, Tag } from 'antd';
import dayjs from 'dayjs';
import { type ReactNode, useState } from 'react';
import type { Person, Values } from '../types';

export const statuses = ['未开始', '进行中', '受阻', '已完成'];
export const names = (people: Person[] = []) =>
  people.map((p) => p.name).join('、');
export const options = (people: Person[] = []) =>
  people.map((p) => ({
    value: p.id,
    label: p.login ? `${p.name}（${p.login}）` : p.name,
  }));
export const days = (date: string, today: string) =>
  dayjs(date).startOf('day').diff(dayjs(today).startOf('day'), 'day');
export function Status({ value }: { value: string }) {
  const color: Record<string, string> = {
    已完成: 'success',
    正常推进: 'success',
    进行中: 'processing',
    受阻: 'error',
    需关注: 'warning',
  };
  return (
    <Tag
      color={color[value]}
      className={
        ['已完成', '正常推进'].includes(value)
          ? 'status-completed'
          : value === '进行中'
            ? 'status-progress'
            : undefined
      }
    >
      {value}
    </Tag>
  );
}
export function Distance({
  planned,
  today,
  achieved,
}: {
  planned: string;
  today: string;
  achieved?: string;
}) {
  const gap = days(planned, today);
  return (
    <span className={achieved ? 'muted' : gap < 0 ? 'late' : 'muted'}>
      {achieved
        ? '已达成'
        : gap < 0
          ? `逾期 ${-gap} 天`
          : gap === 0
            ? '今日到期'
            : `还有 ${gap} 天`}
    </span>
  );
}
export function dateValues(values: Values) {
  return Object.fromEntries(
    Object.entries(values).map(([key, value]) => [
      key,
      dayjs.isDayjs(value) ? value.format('YYYY-MM-DD') : value,
    ]),
  );
}
export function Editor({
  title,
  initial,
  children,
  onSave,
  onClose,
  extra,
  width = 560,
}: {
  title: string;
  initial?: Values;
  children: ReactNode;
  onSave: (v: Values) => Promise<void>;
  onClose: () => void;
  extra?: ReactNode;
  width?: number;
}) {
  const [form] = Form.useForm();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  return (
    <Modal
      title={title}
      open
      onCancel={onClose}
      width={width}
      footer={null}
      destroyOnHidden
    >
      {error && (
        <Alert type="error" showIcon title={error} className="form-error" />
      )}
      <Form
        form={form}
        layout="vertical"
        initialValues={initial}
        onKeyDown={(event) => {
          if (
            event.key === 'Enter' &&
            (event.target as HTMLElement).closest('.ant-picker')
          )
            event.preventDefault();
        }}
        onFinish={async (values) => {
          setBusy(true);
          setError('');
          try {
            await onSave(dateValues(values));
            onClose();
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        {children}
        <div className="form-actions">
          {extra}
          <Button onClick={onClose}>取消</Button>
          <Button type="primary" htmlType="submit" loading={busy}>
            保存
          </Button>
        </div>
      </Form>
    </Modal>
  );
}
