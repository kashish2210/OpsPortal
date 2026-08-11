import { Navigate, Route, Routes } from 'react-router-dom';

import { RequireAuth, RequireCapability } from './auth/guards';
import { Layout } from './components/Layout';
import { ChallanBuilderPage } from './pages/challans/ChallanBuilderPage';
import { ChallanDetailPage } from './pages/challans/ChallanDetailPage';
import { ChallanListPage } from './pages/challans/ChallanListPage';
import { CustomerDetailPage } from './pages/customers/CustomerDetailPage';
import { CustomerFormPage } from './pages/customers/CustomerFormPage';
import { CustomerListPage } from './pages/customers/CustomerListPage';
import { DashboardPage } from './pages/DashboardPage';
import { HandoffPage } from './pages/HandoffPage';
import { LoginPage } from './pages/LoginPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { ProductDetailPage } from './pages/products/ProductDetailPage';
import { ProductFormPage } from './pages/products/ProductFormPage';
import { ProductListPage } from './pages/products/ProductListPage';
import { ProfilePage } from './pages/ProfilePage';
import { StockMovementsPage } from './pages/StockMovementsPage';
import { UsersPage } from './pages/UsersPage';

export function App() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/auth/handoff" element={<HandoffPage />} />

      {/* Everything below needs a session */}
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<DashboardPage />} />

        <Route path="customers">
          <Route index element={<CustomerListPage />} />
          <Route
            path="new"
            element={
              <RequireCapability capability="customers.write">
                <CustomerFormPage />
              </RequireCapability>
            }
          />
          <Route path=":id" element={<CustomerDetailPage />} />
          <Route
            path=":id/edit"
            element={
              <RequireCapability capability="customers.write">
                <CustomerFormPage />
              </RequireCapability>
            }
          />
        </Route>

        <Route path="products">
          <Route index element={<ProductListPage />} />
          <Route
            path="new"
            element={
              <RequireCapability capability="products.write">
                <ProductFormPage />
              </RequireCapability>
            }
          />
          <Route path=":id" element={<ProductDetailPage />} />
          <Route
            path=":id/edit"
            element={
              <RequireCapability capability="products.write">
                <ProductFormPage />
              </RequireCapability>
            }
          />
        </Route>

        <Route path="stock" element={<StockMovementsPage />} />

        <Route path="challans">
          <Route index element={<ChallanListPage />} />
          <Route
            path="new"
            element={
              <RequireCapability capability="challans.write">
                <ChallanBuilderPage />
              </RequireCapability>
            }
          />
          <Route path=":id" element={<ChallanDetailPage />} />
          <Route
            path=":id/edit"
            element={
              <RequireCapability capability="challans.write">
                <ChallanBuilderPage />
              </RequireCapability>
            }
          />
        </Route>

        <Route
          path="users"
          element={
            <RequireCapability capability="users.manage">
              <UsersPage />
            </RequireCapability>
          }
        />

        <Route path="profile" element={<ProfilePage />} />
      </Route>

      <Route path="/index.html" element={<Navigate to="/" replace />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
