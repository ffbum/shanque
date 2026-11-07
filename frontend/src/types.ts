export interface Person {
  id: number;
  name: string;
  login?: string;
  role?: string;
  admin?: number;
  active?: number;
  lead?: number;
}
export interface Team {
  id: number;
  name: string;
  role?: string;
  members?: number;
  projects?: number;
}
export interface Session {
  user: Person | null;
  team: Team | null;
  teams: Team[];
  csrf: string;
  today: string;
}
export type ProjectType = '科研' | '工程' | '固投' | '自研' | '预研';
export interface Task {
  project_type?: ProjectType | null;
  id: number;
  project_id: number;
  project_name?: string;
  name: string;
  due: string;
  start_date: string;
  status: string;
  note: string;
  is_key: number;
  milestone_id: number | null;
  milestone_name?: string;
  milestone_achieved?: string;
  planned?: string;
  done_at?: string;
  finisher?: string;
  revision: string;
  assignees: Person[];
  assignee_ids: number[];
  team_id?: number;
  can_update?: boolean;
  due_x?: number;
  start_x?: number;
}
export interface Milestone {
  id: number;
  name: string;
  planned: string;
  forecast?: string;
  achieved?: string;
  actor_name?: string;
  tasks: Task[];
  remaining: Task[];
  key?: Task;
  stage_start?: string;
  state?: string;
  label?: string;
  plan_x?: number;
  forecast_x?: number;
  actual_x?: number;
  stage_x?: number;
  left?: number;
  width?: number;
}
export interface Project {
  project_type?: ProjectType | null;
  id: number;
  name: string;
  description: string;
  progress: string;
  editor?: string;
  progress_at?: string;
  start_date: string;
  end_date: string;
  closed_at?: string;
  state: string;
  done: number;
  reached: number;
  leads: Person[];
  members: Person[];
  tasks: Task[];
  milestones: Milestone[];
  pending: Milestone[];
  overdue: Milestone[];
  upcoming: Milestone[];
  blocked: Task[];
  late: Task[];
  unlinked?: Task[];
  left?: number;
  width?: number;
}
export interface Chart {
  start: string;
  stop: string;
  today_x: number;
  day_width: number;
  width: number;
  counts: { total: number; done: number; risk: number; upcoming: number };
}
export interface PageData {
  projects?: Project[];
  p?: Project | null;
  items?: Task[];
  item?: Task | Milestone;
  staff?: Person[];
  available?: Person[];
  available_projects?: Project[];
  teams?: Team[];
  team?: Team;
  can_manage?: boolean;
  manage?: boolean;
  selected?: number[];
  ms?: Milestone[];
  candidates?: Task[];
  chart?: Chart;
  kind?: string;
  metrics?: [string, number][];
  filters?: [string, number][];
}
export type Values = Record<string, unknown>;
