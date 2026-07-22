import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Navigate } from 'react-router-dom';

import { buildApiUrl } from '../../utils/apiBaseUrl';

/**
 * 관리자 페이지 접근 전 현재 로그인 사용자가 ROLE_ADMIN인지 확인합니다.
 * 백엔드는 /api/v1/admin/**를 다시 보호하므로, 이 컴포넌트는 UX용 1차 가드입니다.
 */
export default function AdminProtectedRoute({ children }) {
    const [checking, setChecking] = useState(true);
    const [allowed, setAllowed] = useState(false);
    const [authenticated, setAuthenticated] = useState(false);

    useEffect(() => {
        async function checkAdminRole() {
            try {
                const response = await axios.get(buildApiUrl('/api/v1/auth/me'), {
                    withCredentials: true,
                });

                const user = response.data;
                setAuthenticated(Boolean(user?.authenticated));
                setAllowed(user?.authenticated && user?.role === 'ROLE_ADMIN');
            } catch (error) {
                console.error('관리자 권한 확인 실패:', error);
                setAuthenticated(false);
                setAllowed(false);
            } finally {
                setChecking(false);
            }
        }

        checkAdminRole();
    }, []);

    if (checking) {
        return (
            <div className="flex min-h-screen items-center justify-center bg-slate-50 px-6 text-sm font-semibold text-slate-500">
                관리자 권한 확인 중...
            </div>
        );
    }

    if (!authenticated) {
        // 로그인하지 않은 사용자는 내정보 페이지의 로그인 버튼을 통해 OAuth 로그인을 진행합니다.
        return <Navigate to="/my-info" replace />;
    }

    if (!allowed) {
        // 일반 사용자는 관리자 화면 대신 기본 대시보드로 돌려보냅니다.
        return <Navigate to="/" replace />;
    }

    return children;
}
