import React from 'react';
import { BrowserRouter, HashRouter, Navigate, Route, Routes } from 'react-router-dom';

import './App.css';
import AdminProtectedRoute from './components/admin/AdminProtectedRoute';
import MainLayout from './layouts/MainLayout';
import ArticlesPage from './pages/ArticlesPage';
import AdminPage from './pages/admin/AdminPage';
import CategoryPage from './pages/CategoryPage';
import HomePage from './pages/HomePage';
import KeywordDetailPage from './pages/KeywordDetailPage';
import MyInfoPage from './pages/MyInfoPage';
import TrendDashboard from './components/TrendDashboard';
import TrendHistoryPage from './pages/TrendHistoryPage';
import OperationsStatusPage from './pages/OperationsStatusPage';
import { isStaticMode } from './config/dataMode';

function App() {
    // static 모드(v2)는 GitHub Pages 하위 경로에 배포됩니다. Pages는 서버 rewrite가 없어
    // /history 같은 경로를 새로고침하면 404가 나므로, 경로를 # 뒤에 두는 HashRouter를 씁니다.
    const staticMode = isStaticMode();
    const Router = staticMode ? HashRouter : BrowserRouter;

    return (
        // 키워드/카테고리/기사/히스토리/내정보/관리자 페이지를 URL 단위로 분리합니다.
        <Router>
            <Routes>
                <Route path="/" element={<MainLayout />}>
                    <Route index element={<HomePage />} />
                    <Route path="keywords" element={<KeywordDetailPage />} />
                    <Route path="keywords/:keyword" element={<KeywordDetailPage />} />
                    <Route path="categories" element={<CategoryPage />} />
                    <Route path="categories/:categorySlug" element={<CategoryPage />} />
                    <Route path="articles" element={<ArticlesPage />} />
                    <Route path="history" element={<TrendHistoryPage />} />
                    <Route path="history/:keyword" element={<TrendHistoryPage />} />
                    {/* static 모드에는 로그인·구독 서버가 없으므로 내정보 대신 읽기 전용 운영 현황을 둡니다. */}
                    {staticMode
                        ? <Route path="status" element={<OperationsStatusPage />} />
                        : <Route path="my-info" element={<MyInfoPage />} />}
                    <Route path="*" element={<Navigate to="/" replace />} />
                </Route>

                {/* 기존 단일 대시보드는 비교/백업용으로 유지합니다. */}
                <Route path="/dashboard" element={<TrendDashboard />} />

                {/* 최소 관리자 페이지입니다. 실제 API도 ROLE_ADMIN으로 보호됩니다. */}
                {!staticMode && (
                    <Route
                        path="/admin"
                        element={
                            <AdminProtectedRoute>
                                <AdminPage />
                            </AdminProtectedRoute>
                        }
                    />
                )}
            </Routes>
        </Router>
    );
}

export default App;
