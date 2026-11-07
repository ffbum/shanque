import type { PageData, Session, Values } from './types';
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public project?: number,
    public team?: number,
  ) {
    super(message);
  }
}
export interface Envelope {
  data: PageData;
  context: Session;
  redirect?: string;
  messages?: string[];
}
const development = process.env.NODE_ENV === 'development';
// The dev proxy prefixes legacy endpoints; production is served by Flask itself.
function endpoint(path: string) {
  return development && !path.startsWith('/api/') ? `/api/page${path}` : path;
}
async function decode(response: Response) {
  const body = await response.json();
  if (!response.ok)
    throw new ApiError(
      response.status,
      body.message || body.messages?.join('，') || '操作失败，请重试。',
      body.project,
      body.team,
    );
  return body;
}
export async function sessionInfo(signal?: AbortSignal): Promise<Session> {
  return decode(
    await fetch('/api/session', {
      headers: { Accept: 'application/json' },
      signal,
    }),
  );
}
export async function readPage(
  path: string,
  signal?: AbortSignal,
): Promise<Envelope> {
  return decode(
    await fetch(endpoint(path), {
      headers: { Accept: 'application/json' },
      signal,
    }),
  );
}
export async function save(
  path: string,
  values: Values | FormData,
  session: Session,
): Promise<Envelope> {
  const form = values instanceof FormData ? values : new FormData();
  if (!(values instanceof FormData)) {
    for (const [key, value] of Object.entries(values)) {
      for (const item of Array.isArray(value) ? value : [value]) {
        form.append(key, item == null ? '' : String(item));
      }
    }
  }
  form.set('csrf', session.csrf);
  form.set('team_context', session.team ? String(session.team.id) : '');
  return decode(
    await fetch(endpoint(path), {
      method: 'POST',
      headers: { Accept: 'application/json' },
      body: form,
    }),
  );
}
