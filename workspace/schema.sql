CREATE TABLE IF NOT EXISTS person (
 id INTEGER PRIMARY KEY, login TEXT NOT NULL UNIQUE COLLATE NOCASE, name TEXT NOT NULL,
 password TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('主管','总监','成员')),
 admin INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1,
 version INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS project (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
 progress TEXT NOT NULL DEFAULT '', progress_at TEXT, progress_by INTEGER REFERENCES person,
 closed_at TEXT, closed_by INTEGER REFERENCES person,
 start_date TEXT, end_date TEXT,
 project_type TEXT CHECK(project_type IN ('科研','工程','固投','自研','预研'))
);
CREATE TABLE IF NOT EXISTS membership (
 project_id INTEGER NOT NULL REFERENCES project, person_id INTEGER NOT NULL REFERENCES person,
 lead INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(project_id,person_id)
);
CREATE TABLE IF NOT EXISTS milestone (
 id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES project,
 name TEXT NOT NULL, planned TEXT NOT NULL, forecast TEXT,
 achieved TEXT, actor INTEGER REFERENCES person
);
CREATE TABLE IF NOT EXISTS task (
 id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES project,
 milestone_id INTEGER REFERENCES milestone ON DELETE SET NULL, name TEXT NOT NULL, due TEXT NOT NULL, start_date TEXT,
 is_key INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT '未开始'
 CHECK(status IN ('未开始','进行中','受阻','已完成')),
 note TEXT NOT NULL DEFAULT '', done_at TEXT, done_by INTEGER REFERENCES person,
 CHECK (is_key=0 OR milestone_id IS NOT NULL)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_key ON task(milestone_id) WHERE is_key=1;
CREATE INDEX IF NOT EXISTS tasks_project ON task(project_id);
CREATE INDEX IF NOT EXISTS milestones_project ON milestone(project_id);
CREATE TABLE IF NOT EXISTS assignment (
 task_id INTEGER NOT NULL REFERENCES task ON DELETE CASCADE, person_id INTEGER NOT NULL REFERENCES person,
 PRIMARY KEY(task_id,person_id)
);
CREATE TABLE IF NOT EXISTS team (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE
);
CREATE TABLE IF NOT EXISTS team_member (
 team_id INTEGER NOT NULL REFERENCES team, person_id INTEGER NOT NULL REFERENCES person,
 role TEXT NOT NULL CHECK(role IN ('主管','总监','成员')),
 PRIMARY KEY(team_id,person_id)
);
CREATE INDEX IF NOT EXISTS team_member_person ON team_member(person_id,team_id);
CREATE TABLE IF NOT EXISTS project_team (
 project_id INTEGER NOT NULL REFERENCES project, team_id INTEGER NOT NULL REFERENCES team,
 PRIMARY KEY(project_id,team_id)
);
CREATE INDEX IF NOT EXISTS project_team_team ON project_team(team_id,project_id);
