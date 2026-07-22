import React from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';

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

function App() {
    return (
        // BrowserRouter를 사용해 키워드/카테고리/기사/히스토리/내정보/관리자 페이지를 URL 단위로 분리합니다.
        <BrowserRouter>
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
                    <Route path="my-info" element={<MyInfoPage />} />
                    <Route path="*" element={<Navigate to="/" replace />} />
                </Route>

                {/* 기존 단일 대시보드는 비교/백업용으로 유지합니다. */}
                <Route path="/dashboard" element={<TrendDashboard />} />

                {/* 최소 관리자 페이지입니다. 실제 API도 ROLE_ADMIN으로 보호됩니다. */}
                <Route
                    path="/admin"
                    element={
                        <AdminProtectedRoute>
                            <AdminPage />
                        </AdminProtectedRoute>
                    }
                />
            </Routes>
        </BrowserRouter>
    );
}

export default App;
