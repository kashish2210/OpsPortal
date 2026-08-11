/** Shapes returned by the OpsPortal REST API. Mirrors the DRF serializers. */

export type Role = 'ADMIN' | 'SALES' | 'WAREHOUSE' | 'ACCOUNTS';
export type CustomerType = 'RETAIL' | 'WHOLESALE' | 'DISTRIBUTOR';
export type CustomerStatus = 'LEAD' | 'ACTIVE' | 'INACTIVE';
export type ChallanStatus = 'DRAFT' | 'CONFIRMED' | 'CANCELLED';
export type MovementType = 'IN' | 'OUT';

export interface Paginated<T> {
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface Choice {
  value: string;
  label: string;
}

/** The uniform error envelope produced by `core.exceptions.api_exception_handler`. */
export interface ApiErrorBody {
  success: false;
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
  };
}

// ---------------------------------------------------------------------------
// Accounts
// ---------------------------------------------------------------------------
export interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  initials: string;
  role: Role;
  role_display: string;
  phone: string;
  department: string;
  avatar_url: string | null;
  is_active: boolean;
  is_staff: boolean;
  is_superuser: boolean;
  is_email_verified: boolean;
  last_login: string | null;
  date_joined: string;
}

export interface TokenPair {
  access: string;
  refresh: string;
  user: User;
}

// ---------------------------------------------------------------------------
// CRM
// ---------------------------------------------------------------------------
export interface CustomerListItem {
  id: number;
  code: string;
  name: string;
  business_name: string;
  mobile: string;
  email: string;
  customer_type: CustomerType;
  customer_type_display: string;
  status: CustomerStatus;
  status_display: string;
  city: string;
  follow_up_date: string | null;
  is_follow_up_due: boolean;
  created_at: string;
}

export interface FollowUp {
  id: number;
  customer: number;
  customer_name: string;
  note: string;
  channel: string;
  channel_display: string;
  next_follow_up_date: string | null;
  created_by: number | null;
  created_by_name: string | null;
  created_at: string;
}

export interface Customer extends CustomerListItem {
  gst_number: string;
  address: string;
  state: string;
  pincode: string;
  full_address: string;
  credit_limit: string;
  notes: string;
  follow_up_count: number;
  challan_count: number;
  recent_follow_ups: FollowUp[] | null;
  created_by: number | null;
  created_by_name: string | null;
  updated_at: string;
}

export interface CustomerOption {
  id: number;
  code: string;
  name: string;
  business_name: string;
  mobile: string;
  customer_type: CustomerType;
  status: CustomerStatus;
  label: string;
}

export interface CustomerPayload {
  name: string;
  business_name?: string;
  mobile: string;
  email?: string;
  gst_number?: string;
  customer_type: CustomerType;
  status: CustomerStatus;
  address?: string;
  city?: string;
  state?: string;
  pincode?: string;
  credit_limit?: string;
  follow_up_date?: string | null;
  notes?: string;
}

// ---------------------------------------------------------------------------
// Inventory
// ---------------------------------------------------------------------------
export interface ProductListItem {
  id: number;
  name: string;
  sku: string;
  category: string;
  unit: string;
  unit_display: string;
  unit_price: string;
  current_stock: number;
  min_stock_alert: number;
  location: string;
  is_active: boolean;
  is_low_stock: boolean;
  is_out_of_stock: boolean;
  stock_value: string;
  /** Absolute URL — local media, or a (pre-signed) S3 URL when USE_S3 is on. */
  image_url: string | null;
  updated_at: string;
}

export interface Product extends ProductListItem {
  description: string;
  hsn_code: string;
  tax_rate: string;
  created_by: number | null;
  created_by_name: string | null;
  created_at: string;
}

export interface ProductOption {
  id: number;
  name: string;
  sku: string;
  category: string;
  unit: string;
  unit_price: string;
  current_stock: number;
  location: string;
  label: string;
}

export interface ProductPayload {
  name: string;
  sku: string;
  category: string;
  description?: string;
  unit: string;
  unit_price: string;
  hsn_code?: string;
  tax_rate?: string;
  opening_stock?: number;
  min_stock_alert: number;
  location?: string;
  is_active?: boolean;
}

export interface StockMovement {
  id: number;
  product: number;
  product_name: string;
  product_sku: string;
  movement_type: MovementType;
  movement_type_display: string;
  quantity: number;
  signed_quantity: number;
  reason: string;
  reason_display: string;
  reference: string;
  notes: string;
  balance_after: number;
  created_by: number | null;
  created_by_name: string | null;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Sales
// ---------------------------------------------------------------------------
export interface ChallanItem {
  id?: number;
  product: number;
  product_name: string;
  product_sku: string;
  product_category: string;
  product_unit: string;
  product_location: string;
  product_stock?: number;
  unit_price: string;
  tax_rate: string;
  quantity: number;
  line_total: string;
  line_tax: string;
}

export interface ChallanListItem {
  id: number;
  challan_number: string;
  challan_date: string;
  customer: number;
  customer_name: string;
  customer_business_name: string;
  customer_mobile: string;
  status: ChallanStatus;
  status_display: string;
  total_quantity: number;
  total_amount: string;
  grand_total: string;
  item_count: number;
  created_by: number | null;
  created_by_name: string | null;
  created_at: string;
}

export interface Challan extends ChallanListItem {
  customer_gst_number: string;
  customer_address: string;
  notes: string;
  delivery_address: string;
  vehicle_number: string;
  items: ChallanItem[];
  total_tax: string;
  is_editable: boolean;
  can_confirm: boolean;
  can_cancel: boolean;
  confirmed_by: number | null;
  confirmed_by_name: string | null;
  confirmed_at: string | null;
  cancelled_by: number | null;
  cancelled_by_name: string | null;
  cancelled_at: string | null;
  cancellation_reason: string;
  updated_at: string;
}

export interface ChallanPayload {
  customer: number;
  challan_date?: string;
  notes?: string;
  delivery_address?: string;
  vehicle_number?: string;
  confirm?: boolean;
  items: Array<{ product: number; quantity: number; unit_price?: string }>;
}

/** `details.shortages` on an `insufficient_stock` error. */
export interface StockShortage {
  product_id: number;
  sku: string;
  product_name: string;
  requested: number;
  available: number;
  short_by: number;
}

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------
export interface DashboardData {
  generated_at: string;
  user: { id: number; name: string; role: Role; role_display: string };
  customers: {
    total: number;
    leads: number;
    active: number;
    inactive: number;
    follow_ups_due: number;
    added_this_month: number;
  };
  inventory: {
    total_products: number;
    active_products: number;
    low_stock: number;
    out_of_stock: number;
    total_stock_units: number;
    stock_value: string;
  };
  sales: {
    total_challans: number;
    draft: number;
    confirmed: number;
    cancelled: number;
    units_shipped: number;
    confirmed_value: string;
    this_month_value: string;
  };
  recent_challans: ChallanListItem[];
  low_stock_products: ProductListItem[];
  follow_ups_due: CustomerListItem[];
  recent_movements: StockMovement[];
  recent_follow_ups: FollowUp[];
  sales_trend: Array<{ date: string; value: string; count: number }>;
}
