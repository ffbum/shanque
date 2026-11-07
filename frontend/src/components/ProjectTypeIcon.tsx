import {
  BankOutlined,
  BulbOutlined,
  CodeOutlined,
  ExperimentOutlined,
  FolderOutlined,
  ToolOutlined,
} from '@ant-design/icons';
import { Tooltip } from 'antd';
import type { ProjectType } from '../types';

export const projectTypes: ProjectType[] = [
  '科研',
  '工程',
  '固投',
  '自研',
  '预研',
];
const icons = {
  科研: ExperimentOutlined,
  工程: ToolOutlined,
  固投: BankOutlined,
  自研: CodeOutlined,
  预研: BulbOutlined,
};
const colors = {
  科研: '#722ed1',
  工程: '#1677ff',
  固投: '#ad6800',
  自研: '#08979c',
  预研: '#d46b08',
};

export default function ProjectTypeIcon({
  type,
}: {
  type?: ProjectType | null;
}) {
  const Icon = type ? icons[type] : FolderOutlined;
  const label = type || '未设置项目类型';
  return (
    <Tooltip title={label}>
      <span
        className="project-type-icon"
        role="img"
        aria-label={label}
        style={{ color: type ? colors[type] : '#8c8c8c' }}
      >
        <Icon aria-hidden />
      </span>
    </Tooltip>
  );
}
