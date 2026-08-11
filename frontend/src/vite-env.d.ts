/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the REST API. Empty means same-origin. */
  readonly VITE_API_BASE_URL?: string;
  /** Base URL of the Django-rendered auth pages. Empty means same-origin. */
  readonly VITE_DJANGO_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
