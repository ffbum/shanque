import { DownOutlined, RightOutlined } from '@ant-design/icons';
import { PageContainer } from '@ant-design/pro-components';
import { Button, Card, Empty, Select, Space, Tag, Tooltip } from 'antd';
import dayjs from 'dayjs';
import { useEffect, useMemo, useRef, useState } from 'react';
import { names, Status } from '../components/common';
import PageTitle from '../components/PageTitle';
import ProjectTypeFilter, {
  matchesProjectType,
  type TypeFilter,
} from '../components/ProjectTypeFilter';
import ProjectTypeIcon from '../components/ProjectTypeIcon';
import { useWorkspace } from '../context';
import type { Chart, Milestone, PageData, Project, Task } from '../types';

interface Line {
  key: string;
  kind: 'project' | 'milestone' | 'task';
  p: Project;
  m?: Milestone;
  t?: Task;
}
export default function Gantt({
  data,
  chart,
}: {
  data: PageData;
  chart: Chart;
}) {
  const { go, session } = useWorkspace();
  const projects = data.projects || [];
  const [selected, setSelected] = useState<number>();
  const [risk, setRisk] = useState(false);
  const [projectType, setProjectType] = useState<TypeFilter>();
  const [folded, setFolded] = useState<Set<string>>(new Set());
  const viewport = useRef<HTMLDivElement>(null);
  const [window, setWindow] = useState({ left: 0, width: 900 });
  const drag = useRef<{ x: number; left: number } | undefined>(undefined);
  const leftWidth = 330;
  const toggle = (key: string) =>
    setFolded((old) => {
      const next = new Set(old);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  const visibleProjects = useMemo(
    () =>
      projects.filter(
        (p) =>
          matchesProjectType(p.project_type, projectType) &&
          (!selected || p.id === selected) &&
          (!risk || p.state === '需关注'),
      ),
    [projects, projectType, selected, risk],
  );
  const rows = useMemo(() => {
    const result: Line[] = [];
    for (const p of visibleProjects) {
      const key = `p${p.id}`;
      result.push({ key, kind: 'project', p });
      if (folded.has(key)) continue;
      for (const m of p.milestones) {
        const mk = `m${m.id}`;
        result.push({ key: mk, kind: 'milestone', p, m });
        if (!folded.has(mk))
          for (const t of m.tasks)
            result.push({ key: `t${t.id}`, kind: 'task', p, m, t });
      }
      for (const t of p.unlinked || [])
        result.push({ key: `t${t.id}`, kind: 'task', p, t });
    }
    return result;
  }, [visibleProjects, folded]);
  const today = () => {
    const el = viewport.current;
    if (el)
      el.scrollLeft = Math.max(
        0,
        chart.today_x - (el.clientWidth - leftWidth) / 3,
      );
  };
  useEffect(() => {
    const el = viewport.current;
    if (!el) return;
    const resize = () =>
      setWindow({ left: el.scrollLeft, width: el.clientWidth });
    const observer = new ResizeObserver(resize);
    observer.observe(el);
    today();
    resize();
    return () => observer.disconnect();
  }, [chart.today_x]);
  const first = Math.max(0, Math.floor(window.left / chart.day_width) - 2);
  const last = Math.min(
    Math.ceil(chart.width / chart.day_width),
    Math.ceil((window.left + window.width) / chart.day_width) + 2,
  );
  const dates = Array.from({ length: Math.max(0, last - first) }, (_, i) => ({
    day: dayjs(chart.start).add(first + i, 'day'),
    x: (first + i) * chart.day_width,
  }));
  return (
    <PageContainer
      title={<PageTitle kind="gantt">项目甘特图</PageTitle>}
      extra={<Button onClick={today}>今天</Button>}
    >
      <Card
        className="gantt-card"
        title={
          <Space wrap>
            <span>节点进展</span>
            <Tag>
              {visibleProjects.reduce((sum, p) => sum + p.reached, 0)}/
              {visibleProjects.reduce((sum, p) => sum + p.milestones.length, 0)}{' '}
              已达成
            </Tag>
          </Space>
        }
        extra={
          <Space wrap>
            <ProjectTypeFilter
              value={projectType}
              onChange={(value) => {
                setProjectType(value);
                setSelected(undefined);
              }}
            />
            <Select
              aria-label="选择项目"
              allowClear
              placeholder="全部项目"
              style={{ width: 180 }}
              value={selected}
              onChange={setSelected}
              options={projects
                .filter((p) => matchesProjectType(p.project_type, projectType))
                .map((p) => ({ value: p.id, label: p.name }))}
            />
            <Button
              type={risk ? 'primary' : 'default'}
              onClick={() => setRisk(!risk)}
            >
              需关注
            </Button>
            <Button
              onClick={() =>
                setFolded(
                  folded.size
                    ? new Set()
                    : new Set(projects.map((p) => `p${p.id}`)),
                )
              }
            >
              {folded.size ? '全部展开' : '全部收起'}
            </Button>
          </Space>
        }
      >
        <div
          ref={viewport}
          className="gantt-scroll"
          onScroll={(e) =>
            setWindow({
              left: e.currentTarget.scrollLeft,
              width: e.currentTarget.clientWidth,
            })
          }
        >
          <div
            className="gantt-sheet"
            style={{ width: chart.width + leftWidth }}
          >
            <div className="gantt-header">
              <div className="gantt-label header-label">项目 / 节点 / 任务</div>
              <div
                className="gantt-axis"
                style={{ width: chart.width }}
                onPointerDown={(e) => {
                  if (e.button !== 0 || !viewport.current) return;
                  drag.current = {
                    x: e.clientX,
                    left: viewport.current.scrollLeft,
                  };
                  e.currentTarget.setPointerCapture(e.pointerId);
                }}
                onPointerMove={(e) => {
                  if (drag.current && viewport.current)
                    viewport.current.scrollLeft =
                      drag.current.left + drag.current.x - e.clientX;
                }}
                onPointerUp={() => {
                  drag.current = undefined;
                }}
                onPointerCancel={() => {
                  drag.current = undefined;
                }}
              >
                {dates.map(({ day, x }) => (
                  <div
                    key={x}
                    className={
                      'axis-date ' +
                      ([0, 6].includes(day.day()) ? 'weekend' : '')
                    }
                    style={{ left: x, width: chart.day_width }}
                  >
                    <span>
                      {day.date() === 1 || x === dates[0]?.x
                        ? day.format('YYYY/MM')
                        : ''}
                    </span>
                    <b>{day.date()}</b>
                  </div>
                ))}
              </div>
            </div>
            {rows.map((row) => {
              const { p, m, t } = row;
              const completion = p.milestones.length
                ? (p.reached / p.milestones.length) * 100
                : 0;
              const left = t?.start_x ?? m?.stage_x ?? m?.plan_x ?? p.left ?? 0;
              const width = t
                ? Math.max(6, (t.due_x || 0) - left)
                : m
                  ? Math.max(
                      6,
                      Math.max(
                        m.plan_x || 0,
                        m.forecast_x || 0,
                        m.actual_x || 0,
                      ) - left,
                    )
                  : (p.width ?? chart.day_width);
              const done = t
                ? t.status === '已完成'
                : m
                  ? !!m.achieved
                  : !!p.closed_at;
              const danger = t
                ? t.status === '受阻' ||
                  (t.status !== '已完成' && t.due < session.today)
                : m
                  ? m.planned < session.today
                  : p.state === '需关注';
              const detail = t
                ? `${t.start_date} → ${t.due} · ${names(t.assignees)}${t.note ? ` · ${t.note}` : ''}`
                : m
                  ? `计划 ${m.planned}${m.forecast ? ` · 预计 ${m.forecast}` : ''}${m.achieved ? ` · 达成 ${m.achieved.slice(0, 10)}` : ''}`
                  : `${p.start_date} → ${p.end_date} · ${names(p.leads)} · 节点完成 ${p.reached}/${p.milestones.length}（${Math.round(completion)}%）`;
              return (
                <div
                  key={row.key}
                  className={`gantt-row ${row.kind} ${done ? 'is-done' : danger ? 'is-overdue' : 'is-pending'}`}
                >
                  <div className="gantt-label">
                    <div className="gantt-title">
                      {row.kind !== 'task' && (
                        <Button
                          type="text"
                          size="small"
                          aria-label={
                            (folded.has(row.key) ? '展开' : '收起') +
                            (m?.name || p.name)
                          }
                          icon={
                            folded.has(row.key) ? (
                              <RightOutlined />
                            ) : (
                              <DownOutlined />
                            )
                          }
                          onClick={() => toggle(row.key)}
                        />
                      )}
                      {row.kind === 'project' && (
                        <ProjectTypeIcon type={p.project_type} />
                      )}
                      <Tooltip title={detail}>
                        <span className="gantt-name">
                          {t?.name || m?.name || p.name}
                        </span>
                      </Tooltip>
                      {row.kind === 'project' && (
                        <Button
                          type="link"
                          size="small"
                          onClick={() => go(`/projects/${p.id}`)}
                        >
                          详情
                        </Button>
                      )}
                    </div>
                    <div className="gantt-meta">
                      {t ? (
                        <>
                          <span title={names(t.assignees)}>
                            {names(t.assignees)}
                          </span>
                          <span>{t.due}</span>
                          <Status value={t.status} />
                        </>
                      ) : m ? (
                        <>
                          <span>{m.planned}</span>
                          <span className="gantt-node-status">
                            {done ? '已达成' : m.label || '待达成'}
                          </span>
                          <span>
                            {m.tasks.length - m.remaining.length}/
                            {m.tasks.length} 项
                          </span>
                        </>
                      ) : (
                        <>
                          <span>{names(p.leads)}</span>
                          <span>
                            节点 {p.reached}/{p.milestones.length}
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                  <div
                    className="gantt-track"
                    style={{
                      width: chart.width,
                      backgroundSize: `${chart.day_width}px 100%`,
                    }}
                  >
                    <div
                      className="today-line"
                      style={{ left: chart.today_x }}
                    />
                    <Tooltip title={detail}>
                      <div
                        className={
                          'gantt-bar ' +
                          (done ? 'done' : danger ? 'danger' : '')
                        }
                        style={{ left, width }}
                      >
                        {row.kind === 'project' && (
                          <>
                            <div
                              className="project-progress-fill"
                              style={{ width: `${completion}%` }}
                            />
                            <span>
                              {p.milestones.length
                                ? `${Math.round(completion)}% · 节点 ${p.reached}/${p.milestones.length}`
                                : '未设节点'}
                            </span>
                          </>
                        )}
                      </div>
                    </Tooltip>
                    {m && !t && (
                      <>
                        <Tooltip title={`节点计划日 ${m.planned}`}>
                          <span
                            className="gantt-diamond"
                            style={{ left: m.plan_x }}
                          />
                        </Tooltip>
                        {m.forecast_x != null && (
                          <Tooltip title={`预计 ${m.forecast}`}>
                            <span
                              className="forecast-mark"
                              style={{ left: m.forecast_x }}
                            />
                          </Tooltip>
                        )}
                        {m.actual_x != null && (
                          <Tooltip
                            title={`实际达成 ${m.achieved?.slice(0, 10)}`}
                          >
                            <span
                              className="actual-mark"
                              style={{ left: m.actual_x }}
                            >
                              ✓
                            </span>
                          </Tooltip>
                        )}
                      </>
                    )}
                    {t && (
                      <Tooltip title={`截止 ${t.due}`}>
                        <span
                          className="task-end"
                          style={{ left: t.due_x || 0 }}
                        />
                      </Tooltip>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
          {!rows.length && <Empty description="暂无项目" />}
        </div>
        <div className="gantt-legend">
          <span>
            <i className="legend-project" /> 项目周期
          </span>
          <span>
            <i className="legend-project-done" /> 已达成节点占比
          </span>
          <span>
            <i className="legend-node" /> 节点阶段
          </span>
          <span>
            <i className="legend-line" /> 任务周期
          </span>
          <span>
            <i className="legend-diamond" /> 节点计划日
          </span>
          <span>
            <i className="legend-forecast" /> 预计日期
          </span>
          <span className="success">✓ 已达成</span>
          <span className="late">│ 今天</span>
        </div>
      </Card>
    </PageContainer>
  );
}
