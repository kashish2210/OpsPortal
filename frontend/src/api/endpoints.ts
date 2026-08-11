/** Typed helpers for every endpoint the SPA uses. */

import { api, downloadFile, request, tokenStore } from './client';
import type {
  Challan,
  ChallanListItem,
  ChallanPayload,
  Choice,
  Customer,
  CustomerListItem,
  CustomerOption,
  CustomerPayload,
  DashboardData,
  FollowUp,
  Paginated,
  Product,
  ProductListItem,
  ProductOption,
  ProductPayload,
  StockMovement,
  TokenPair,
  User,
} from './types';

export type ListParams = Record<string, string | number | boolean | undefined | null>;

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------
export const auth = {
  login: async (username: string, password: string) => {
    const tokens = await api.post<TokenPair>('/api/auth/login/', { username, password });
    tokenStore.set(tokens);
    return tokens;
  },

  logout: async () => {
    const refresh = tokenStore.refresh;
    try {
      if (refresh) await api.post('/api/auth/logout/', { refresh });
    } catch {
      // A already-expired token is fine - we are logging out either way.
    } finally {
      tokenStore.clear();
    }
  },

  me: () => api.get<User>('/api/auth/me/'),
  updateMe: (payload: Partial<Pick<User, 'first_name' | 'last_name' | 'phone' | 'department'>>) =>
    api.patch<User>('/api/auth/me/', payload),
  changePassword: (old_password: string, new_password: string) =>
    api.post<{ success: boolean; message: string }>('/api/auth/change-password/', {
      old_password,
      new_password,
    }),
};

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------
export const dashboard = {
  summary: (signal?: AbortSignal) => api.get<DashboardData>('/api/dashboard/', undefined, signal),
};

// ---------------------------------------------------------------------------
// Customers
// ---------------------------------------------------------------------------
export const customers = {
  list: (params?: ListParams, signal?: AbortSignal) =>
    api.get<Paginated<CustomerListItem>>('/api/customers/', params, signal),
  get: (id: number, signal?: AbortSignal) => api.get<Customer>(`/api/customers/${id}/`, undefined, signal),
  create: (payload: CustomerPayload) => api.post<Customer>('/api/customers/', payload),
  update: (id: number, payload: Partial<CustomerPayload>) =>
    api.patch<Customer>(`/api/customers/${id}/`, payload),
  archive: (id: number) => api.delete<void>(`/api/customers/${id}/`),
  options: (q?: string, signal?: AbortSignal) =>
    api.get<CustomerOption[]>('/api/customers/options/', { q }, signal),
  choices: (signal?: AbortSignal) =>
    api.get<Record<string, Choice[]>>('/api/customers/choices/', undefined, signal),
  followUps: (id: number, params?: ListParams, signal?: AbortSignal) =>
    api.get<Paginated<FollowUp>>(`/api/customers/${id}/follow-ups/`, params, signal),
  addFollowUp: (
    id: number,
    payload: { note: string; channel: string; next_follow_up_date?: string | null },
  ) => api.post<FollowUp>(`/api/customers/${id}/follow-ups/`, payload),
};

// ---------------------------------------------------------------------------
// Products & stock
// ---------------------------------------------------------------------------
export const products = {
  list: (params?: ListParams, signal?: AbortSignal) =>
    api.get<Paginated<ProductListItem>>('/api/products/', params, signal),
  get: (id: number, signal?: AbortSignal) => api.get<Product>(`/api/products/${id}/`, undefined, signal),
  create: (payload: ProductPayload) => api.post<Product>('/api/products/', payload),
  update: (id: number, payload: Partial<ProductPayload>) =>
    api.patch<Product>(`/api/products/${id}/`, payload),
  archive: (id: number) => api.delete<void>(`/api/products/${id}/`),
  options: (q?: string, inStock = false, signal?: AbortSignal) =>
    api.get<ProductOption[]>('/api/products/options/', { q, in_stock: inStock || undefined }, signal),
  choices: (signal?: AbortSignal) =>
    api.get<Record<string, Choice[]>>('/api/products/choices/', undefined, signal),
  categories: (signal?: AbortSignal) =>
    api.get<Array<{ category: string; count: number }>>('/api/products/categories/', undefined, signal),
  locations: (signal?: AbortSignal) =>
    api.get<Array<{ location: string; count: number }>>('/api/products/locations/', undefined, signal),
  movements: (id: number, params?: ListParams, signal?: AbortSignal) =>
    api.get<Paginated<StockMovement>>(`/api/products/${id}/movements/`, params, signal),
  adjustStock: (id: number, new_quantity: number, notes?: string) =>
    api.post<Product>(`/api/products/${id}/adjust-stock/`, { new_quantity, notes }),

  /** Multipart upload of a product photo (local media, or S3 when enabled). */
  uploadImage: (id: number, file: File) => {
    const form = new FormData();
    form.append('image', file);
    return api.upload<Product>(`/api/products/${id}/image/`, form);
  },
  deleteImage: (id: number) => api.delete<Product>(`/api/products/${id}/image/`),
};

export const stock = {
  list: (params?: ListParams, signal?: AbortSignal) =>
    api.get<Paginated<StockMovement>>('/api/stock-movements/', params, signal),
  create: (payload: {
    product: number;
    movement_type: 'IN' | 'OUT';
    quantity: number;
    reason: string;
    reference?: string;
    notes?: string;
  }) => api.post<StockMovement>('/api/stock-movements/', payload),
};

// ---------------------------------------------------------------------------
// Challans
// ---------------------------------------------------------------------------
export const challans = {
  list: (params?: ListParams, signal?: AbortSignal) =>
    api.get<Paginated<ChallanListItem>>('/api/challans/', params, signal),
  get: (id: number, signal?: AbortSignal) => api.get<Challan>(`/api/challans/${id}/`, undefined, signal),
  create: (payload: ChallanPayload) => api.post<Challan>('/api/challans/', payload),
  update: (id: number, payload: Partial<ChallanPayload>) =>
    api.patch<Challan>(`/api/challans/${id}/`, payload),
  remove: (id: number) => api.delete<void>(`/api/challans/${id}/`),
  confirm: (id: number) => api.post<Challan>(`/api/challans/${id}/confirm/`),
  cancel: (id: number, reason?: string) => api.post<Challan>(`/api/challans/${id}/cancel/`, { reason }),
  stockMovements: (id: number, signal?: AbortSignal) =>
    api.get<StockMovement[]>(`/api/challans/${id}/stock-movements/`, undefined, signal),
  choices: (signal?: AbortSignal) =>
    api.get<Record<string, Choice[]>>('/api/challans/choices/', undefined, signal),

  /** Download (or preview) the challan as a PDF. */
  downloadPdf: (id: number, challanNumber: string, inline = false) =>
    downloadFile(`/api/challans/${id}/pdf/`, `${challanNumber}.pdf`, { inline }),
};

// ---------------------------------------------------------------------------
// Users (admin only)
// ---------------------------------------------------------------------------
export const users = {
  list: (params?: ListParams, signal?: AbortSignal) =>
    api.get<Paginated<User>>('/api/users/', params, signal),
  create: (payload: {
    username: string;
    email: string;
    first_name?: string;
    last_name?: string;
    role: string;
    phone?: string;
    department?: string;
    password: string;
  }) => api.post<User>('/api/users/', payload),
  update: (id: number, payload: Record<string, unknown>) => api.patch<User>(`/api/users/${id}/`, payload),
  activate: (id: number) => api.post<User>(`/api/users/${id}/activate/`),
  deactivate: (id: number) => api.post<User>(`/api/users/${id}/deactivate/`),
  roles: (signal?: AbortSignal) => api.get<Choice[]>('/api/users/roles/', undefined, signal),
};

export const health = () => request<{ status: string; database: string }>('/api/health/');
