import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import { ApiError, SESSION_EXPIRED_EVENT, tokenStore } from '../api/client';
import { auth as authApi } from '../api/endpoints';
import type { User } from '../api/types';
import { can, type Capability } from './permissions';

interface AuthState {
  user: User | null;
  status: 'loading' | 'authenticated' | 'anonymous';
  login: (username: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  setUser: (user: User) => void;
  can: (capability: Capability) => boolean;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUserState] = useState<User | null>(null);
  const [status, setStatus] = useState<AuthState['status']>('loading');

  const loadUser = useCallback(async () => {
    if (!tokenStore.access) {
      setUserState(null);
      setStatus('anonymous');
      return;
    }
    try {
      const me = await authApi.me();
      setUserState(me);
      setStatus('authenticated');
    } catch (error) {
      // A 401 here means both tokens are dead; anything else (network, 500)
      // should not silently sign the user out.
      if (error instanceof ApiError && error.isAuthError) tokenStore.clear();
      setUserState(null);
      setStatus('anonymous');
    }
  }, []);

  useEffect(() => {
    void loadUser();
  }, [loadUser]);

  // The API client fires this when a refresh attempt fails for good.
  useEffect(() => {
    const onExpired = () => {
      setUserState(null);
      setStatus('anonymous');
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, onExpired);
  }, []);

  // Keep tabs in sync: signing out in one tab signs out the others.
  useEffect(() => {
    const onStorage = (event: StorageEvent) => {
      if (event.key === 'opsportal.access') void loadUser();
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, [loadUser]);

  const login = useCallback(async (username: string, password: string) => {
    const { user: loggedIn } = await authApi.login(username, password);
    setUserState(loggedIn);
    setStatus('authenticated');
    return loggedIn;
  }, []);

  const logout = useCallback(async () => {
    await authApi.logout();
    setUserState(null);
    setStatus('anonymous');
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      user,
      status,
      login,
      logout,
      refreshUser: loadUser,
      setUser: setUserState,
      can: (capability: Capability) => can(user?.role, capability),
    }),
    [user, status, login, logout, loadUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>.');
  return context;
}
