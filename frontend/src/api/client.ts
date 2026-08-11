/**
 * Thin fetch wrapper around the OpsPortal API.
 *
 * Responsibilities:
 *  - attach the JWT access token,
 *  - transparently refresh it once on a 401 and replay the request
 *    (concurrent 401s share a single refresh, they do not stampede),
 *  - unwrap the API's error envelope into a typed `ApiError`.
 */

import type { ApiErrorBody, TokenPair } from './types';

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');

const ACCESS_KEY = 'opsportal.access';
const REFRESH_KEY = 'opsportal.refresh';

export const tokenStore = {
  get access() {
    return localStorage.getItem(ACCESS_KEY);
  },
  get refresh() {
    return localStorage.getItem(REFRESH_KEY);
  },
  set(tokens: { access: string; refresh?: string }) {
    localStorage.setItem(ACCESS_KEY, tokens.access);
    if (tokens.refresh) localStorage.setItem(REFRESH_KEY, tokens.refresh);
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }

  /** Field-level messages, flattened for form display. */
  fieldErrors(): Record<string, string> {
    const out: Record<string, string> = {};
    for (const [key, value] of Object.entries(this.details)) {
      if (Array.isArray(value)) out[key] = value.map(String).join(' ');
      else if (typeof value === 'string') out[key] = value;
    }
    return out;
  }

  get isAuthError() {
    return this.status === 401;
  }

  get isPermissionError() {
    return this.status === 403;
  }
}

/** Broadcast when the session cannot be recovered, so the app can log out. */
export const SESSION_EXPIRED_EVENT = 'opsportal:session-expired';

function notifySessionExpired() {
  window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT));
}

let refreshInFlight: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const refresh = tokenStore.refresh;
  if (!refresh) return null;

  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const response = await fetch(`${API_BASE}/api/auth/refresh/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh }),
        });
        if (!response.ok) return null;
        const data = (await response.json()) as { access: string; refresh?: string };
        tokenStore.set(data);
        return data.access;
      } catch {
        return null;
      } finally {
        // Release the lock on the next tick so callers awaiting it all resolve.
        setTimeout(() => {
          refreshInFlight = null;
        }, 0);
      }
    })();
  }
  return refreshInFlight;
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
  params?: Record<string, string | number | boolean | undefined | null>;
  /** Send the session cookie instead of a bearer token (used by the handoff). */
  withCredentials?: boolean;
  signal?: AbortSignal;
}

function buildUrl(path: string, params?: RequestOptions['params']) {
  const url = `${API_BASE}${path}`;
  if (!params) return url;
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue;
    search.append(key, String(value));
  }
  const query = search.toString();
  return query ? `${url}?${query}` : url;
}

function readCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(^|;\\s*)${name}=([^;]*)`));
  return match ? decodeURIComponent(match[2]) : null;
}

async function parseError(response: Response): Promise<ApiError> {
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    return new ApiError(response.status, 'network_error', response.statusText || 'Request failed.');
  }

  const envelope = body as Partial<ApiErrorBody>;
  if (envelope?.error) {
    return new ApiError(
      response.status,
      envelope.error.code ?? 'error',
      envelope.error.message ?? 'Request failed.',
      envelope.error.details ?? {},
    );
  }
  // Fall back to a raw DRF payload (e.g. from the token refresh endpoint).
  const detail =
    typeof body === 'object' && body !== null && 'detail' in body
      ? String((body as { detail: unknown }).detail)
      : 'Request failed.';
  return new ApiError(response.status, 'error', detail);
}

async function performRequest(path: string, options: RequestOptions, retrying = false): Promise<Response> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  const isFormData = options.body instanceof FormData;
  if (options.body !== undefined && !isFormData) headers['Content-Type'] = 'application/json';

  if (options.withCredentials) {
    const csrf = readCookie('csrftoken');
    if (csrf) headers['X-CSRFToken'] = csrf;
  } else {
    const access = tokenStore.access;
    if (access) headers.Authorization = `Bearer ${access}`;
  }

  const response = await fetch(buildUrl(path, options.params), {
    method: options.method ?? 'GET',
    headers,
    credentials: options.withCredentials ? 'include' : 'same-origin',
    signal: options.signal,
    body:
      options.body === undefined ? undefined : isFormData ? (options.body as FormData) : JSON.stringify(options.body),
  });

  // One transparent refresh-and-replay, only for bearer-token requests.
  if (response.status === 401 && !retrying && !options.withCredentials && tokenStore.refresh) {
    const access = await refreshAccessToken();
    if (access) return performRequest(path, options, true);
    tokenStore.clear();
    notifySessionExpired();
  }

  return response;
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await performRequest(path, options);

  if (!response.ok) throw await parseError(response);
  if (response.status === 204 || response.status === 205) return undefined as T;

  const contentType = response.headers.get('content-type') ?? '';
  if (!contentType.includes('application/json')) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string, params?: RequestOptions['params'], signal?: AbortSignal) =>
    request<T>(path, { method: 'GET', params, signal }),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: 'POST', body }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: 'PATCH', body }),
  put: <T>(path: string, body?: unknown) => request<T>(path, { method: 'PUT', body }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
  upload: <T>(path: string, form: FormData) => request<T>(path, { method: 'POST', body: form }),
};

/**
 * Fetch a binary endpoint (the challan PDF) and hand it to the browser.
 *
 * A plain `<a href>` cannot be used because the endpoint needs the bearer
 * token, so the bytes are fetched, wrapped in an object URL and either
 * downloaded or opened in a new tab.
 */
export async function downloadFile(
  path: string,
  filename: string,
  { inline = false }: { inline?: boolean } = {},
): Promise<void> {
  const response = await performRequest(path, {
    method: 'GET',
    params: inline ? { disposition: 'inline' } : undefined,
  });

  if (!response.ok) throw await parseError(response);

  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);

  try {
    if (inline) {
      window.open(objectUrl, '_blank', 'noopener');
    } else {
      const anchor = document.createElement('a');
      anchor.href = objectUrl;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
    }
  } finally {
    // Give the browser a moment to start reading before revoking.
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
  }
}

/**
 * Exchange the Django session cookie for a JWT pair.
 * Used by /auth/handoff after signing in through the server-rendered pages.
 */
export async function exchangeSessionForTokens(): Promise<TokenPair> {
  const tokens = await request<TokenPair>('/api/auth/session-token/', {
    method: 'POST',
    withCredentials: true,
  });
  tokenStore.set(tokens);
  return tokens;
}

/** Absolute URL of a Django-rendered page (login, signup, password reset...). */
export function djangoUrl(path: string): string {
  const base = (import.meta.env.VITE_DJANGO_BASE_URL ?? '').replace(/\/$/, '');
  return `${base}${path}`;
}
