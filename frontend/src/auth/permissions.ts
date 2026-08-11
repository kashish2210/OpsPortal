/**
 * Client-side mirror of `core.permissions.RolePermission`.
 *
 * This drives what the UI *offers*; the server enforces the same matrix, so a
 * crafted request still gets a 403. Keep the two in sync when roles change.
 */

import type { Role } from '../api/types';

export const ALL_ROLES: Role[] = ['ADMIN', 'SALES', 'WAREHOUSE', 'ACCOUNTS'];

export type Capability =
  | 'customers.read'
  | 'customers.write'
  | 'products.read'
  | 'products.write'
  | 'stock.read'
  | 'stock.write'
  | 'challans.read'
  | 'challans.write'
  | 'users.manage';

const MATRIX: Record<Capability, Role[]> = {
  'customers.read': ALL_ROLES,
  'customers.write': ['ADMIN', 'SALES'],
  'products.read': ALL_ROLES,
  'products.write': ['ADMIN', 'WAREHOUSE'],
  'stock.read': ALL_ROLES,
  'stock.write': ['ADMIN', 'WAREHOUSE'],
  'challans.read': ALL_ROLES,
  'challans.write': ['ADMIN', 'SALES'],
  'users.manage': ['ADMIN'],
};

export function can(role: Role | undefined, capability: Capability): boolean {
  if (!role) return false;
  if (role === 'ADMIN') return true;
  return MATRIX[capability].includes(role);
}

export const ROLE_BADGE: Record<Role, string> = {
  ADMIN: 'badge-accent',
  SALES: 'badge-info',
  WAREHOUSE: 'badge-ok',
  ACCOUNTS: 'badge-warn',
};
