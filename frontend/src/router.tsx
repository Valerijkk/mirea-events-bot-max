import { Routes, Route, Navigate } from 'react-router-dom'
import { ProtectedRoute } from './components/ProtectedRoute'
import { AdminRoute } from './components/AdminRoute'
import { Layout } from './components/Layout'
import { LoginPage } from './pages/LoginPage'
import { EventsPage } from './pages/EventsPage'
import { EventDetailPage } from './pages/EventDetailPage'
import { SlotsPage } from './pages/SlotsPage'
import { ScannerPage } from './pages/ScannerPage'
import { BroadcastsPage } from './pages/BroadcastsPage'
import { OrganizersPage } from './pages/OrganizersPage'
import { AuditPage } from './pages/AuditPage'
import { StatsPage } from './pages/StatsPage'

export function AppRouter() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route path="/" element={<Navigate to="/events" replace />} />
          <Route path="/events" element={<EventsPage />} />
          <Route path="/events/:id" element={<EventDetailPage />} />
          <Route path="/events/:id/slots" element={<SlotsPage />} />
          <Route path="/events/:id/scanner" element={<ScannerPage />} />
          <Route path="/events/:id/broadcasts" element={<BroadcastsPage />} />
          <Route element={<AdminRoute />}>
            <Route path="/organizers" element={<OrganizersPage />} />
            <Route path="/audit" element={<AuditPage />} />
            <Route path="/stats" element={<StatsPage />} />
          </Route>
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
