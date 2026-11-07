import {
  ApartmentOutlined,
  CalendarOutlined,
  CheckSquareOutlined,
  HomeOutlined,
  TeamOutlined,
  UserOutlined,
} from '@ant-design/icons';
import type { ReactNode } from 'react';

const icons = {
  overview: HomeOutlined,
  gantt: CalendarOutlined,
  todo: CheckSquareOutlined,
  members: TeamOutlined,
  teams: ApartmentOutlined,
  accounts: UserOutlined,
};
export default function PageTitle({
  kind,
  children,
}: {
  kind: keyof typeof icons;
  children: ReactNode;
}) {
  const Icon = icons[kind];
  return (
    <span className="page-title-with-icon">
      <Icon aria-hidden="true" />
      {children}
    </span>
  );
}
