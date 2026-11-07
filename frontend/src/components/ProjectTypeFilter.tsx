import { Select } from 'antd';
import type { ProjectType } from '../types';
import ProjectTypeIcon, { projectTypes } from './ProjectTypeIcon';

export type TypeFilter = ProjectType | undefined;
export function matchesProjectType(
  type: ProjectType | null | undefined,
  filter: TypeFilter,
) {
  return !filter || type === filter;
}

export default function ProjectTypeFilter({
  value,
  onChange,
}: {
  value: TypeFilter;
  onChange: (value: TypeFilter) => void;
}) {
  return (
    <Select<TypeFilter>
      aria-label="筛选项目类型"
      allowClear
      placeholder="全部项目类型"
      style={{ width: 160 }}
      value={value}
      onChange={onChange}
      options={[
        ...projectTypes.map((type) => ({
          value: type,
          label: (
            <span className="project-type-option">
              <ProjectTypeIcon type={type} />
              {type}
            </span>
          ),
        })),
      ]}
    />
  );
}
