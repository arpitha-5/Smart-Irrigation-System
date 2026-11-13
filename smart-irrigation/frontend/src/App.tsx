import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/layout/Layout';
import { LandingPage } from './pages/LandingPage';
import { DashboardPage } from './pages/DashboardPage';
import { FarmersPage } from './pages/FarmersPage';
import { FieldsPage } from './pages/FieldsPage';
import { CropsPage } from './pages/CropsPage';
import { SensorsPage } from './pages/SensorsPage';
import { ReadingsPage } from './pages/ReadingsPage';
import { WeatherPage } from './pages/WeatherPage';
import { DataQualityPage } from './pages/DataQualityPage';
import { SystemStatusPage } from './pages/SystemStatusPage';
import { RecommendationsPage } from './pages/RecommendationsPage';
import { AlertsPage } from './pages/AlertsPage';
import { ReportsPage } from './pages/ReportsPage';
import { IrrigationSchedulePage } from './pages/IrrigationSchedulePage';
import { FarmIntelligencePage } from './pages/FarmIntelligencePage';
import { WaterAnalyticsPage } from './pages/WaterAnalyticsPage';
import { LoginPage } from './pages/LoginPage';
import { SignupPage } from './pages/SignupPage';
import { ProfilePage } from './pages/ProfilePage';
import { OfflinePage } from './pages/OfflinePage';
import { ProtectedRoute } from './components/common/ProtectedRoute';

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public Landing & Authentication Pages */}
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/offline" element={<OfflinePage />} />

        {/* Protected Dashboard & Operations within Sidebar Layout */}
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="/recommendations" element={<RecommendationsPage />} />
            <Route path="/schedules" element={<IrrigationSchedulePage />} />
            <Route path="/intelligence" element={<FarmIntelligencePage />} />
            <Route path="/analytics" element={<WaterAnalyticsPage />} />
            <Route path="/water-analytics" element={<WaterAnalyticsPage />} />
            <Route path="/alerts" element={<AlertsPage />} />
            <Route path="/farmers" element={<FarmersPage />} />
            <Route path="/fields" element={<FieldsPage />} />
            <Route path="/crops" element={<CropsPage />} />
            <Route path="/sensors" element={<SensorsPage />} />
            <Route path="/readings" element={<ReadingsPage />} />
            <Route path="/weather" element={<WeatherPage />} />
            <Route path="/data-quality" element={<DataQualityPage />} />
            <Route path="/status" element={<SystemStatusPage />} />
            <Route path="/reports" element={<ReportsPage />} />
          </Route>
        </Route>

        {/* Fallback route */}
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
