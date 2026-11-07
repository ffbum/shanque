import { createContext, useContext } from 'react';
import type { Session, Values } from './types';

export interface Workspace {
  session: Session;
  submit: (
    path: string,
    values: Values | FormData,
    navigate?: boolean,
  ) => Promise<void>;
  reload: () => void;
  go: (path: string) => void;
}
export const WorkspaceContext = createContext<Workspace | null>(null);
export function useWorkspace() {
  const value = useContext(WorkspaceContext);
  if (!value) throw new Error('Workspace is not available');
  return value;
}
