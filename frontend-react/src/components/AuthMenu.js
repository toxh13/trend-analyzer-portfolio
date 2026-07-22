import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { LogIn, LogOut, User, Link as LinkIcon, ShieldCheck } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { clearCsrfToken, refreshCsrfToken } from '../api/csrf';
import { buildApiUrl } from '../utils/apiBaseUrl';

export default function AuthMenu() {
    const navigate = useNavigate();
    const [auth, setAuth] = useState({ authenticated: false });
    const [loading, setLoading] = useState(true);
    const [open, setOpen] = useState(false);
    const [logoutPending, setLogoutPending] = useState(false);
    const [logoutError, setLogoutError] = useState(null);

    useEffect(() => {
        fetchMe();
    }, []);

    const fetchMe = async () => {
        setLoading(true);
        try {
            const response = await axios.get(buildApiUrl('/api/v1/auth/me'), {
                withCredentials: true,
            });
            setAuth(response.data);
        } catch (error) {
            console.error('로그인 상태 조회 실패:', error);
            setAuth({ authenticated: false });
        } finally {
            setLoading(false);
        }
    };

    const handleGoogleLogin = () => {
        // OAuth2 시작점입니다. 백엔드 Spring Security가 Google 로그인 화면으로 redirect합니다.
        window.location.href = buildApiUrl('/oauth2/authorization/google');
    };

    const handleLogout = async () => {
        setLogoutPending(true);
        setLogoutError(null);

        try {
            const csrfToken = await refreshCsrfToken();
            const headers = csrfToken?.token
                ? { [csrfToken.headerName]: csrfToken.token }
                : {};

            await axios.post(buildApiUrl('/api/v1/auth/logout'), null, {
                withCredentials: true,
                headers,
            });
            clearCsrfToken();
            setAuth({ authenticated: false });
            setOpen(false);
            navigate('/', { replace: true });
        } catch (error) {
            console.error('로그아웃 실패:', error);
            setLogoutError('로그아웃에 실패했습니다. 다시 시도해 주세요.');
        } finally {
            setLogoutPending(false);
        }
    };

    const goToMyInfo = () => {
        // 내정보 페이지에서 Discord 연동과 구독 키워드 목록을 관리합니다.
        navigate('/my-info');
        setOpen(false);
    };

    const goToAdmin = () => {
        // ROLE_ADMIN 사용자에게만 최소 관리자 페이지 진입 버튼을 노출합니다.
        navigate('/admin');
        setOpen(false);
    };

    if (loading) {
        return (
            <div className="h-10 w-24 animate-pulse rounded-2xl bg-slate-100" />
        );
    }

    if (!auth.authenticated) {
        return (
            <button
                type="button"
                onClick={handleGoogleLogin}
                className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700"
            >
                <LogIn className="h-4 w-4" />
                로그인
            </button>
        );
    }

    const isAdmin = auth.role === 'ROLE_ADMIN';

    return (
        <div className="relative">
            <button
                type="button"
                onClick={() => setOpen((prev) => !prev)}
                className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700"
            >
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-blue-50 text-blue-700">
                    <User className="h-4 w-4" />
                </span>
                <span className="hidden max-w-32 truncate sm:inline">
                    {auth.username || auth.email || '내정보'}
                </span>
            </button>

            {open && (
                <div className="absolute right-0 z-30 mt-2 w-72 rounded-3xl border border-slate-200 bg-white p-4 shadow-xl shadow-slate-200/70">
                    <div className="flex items-start gap-3">
                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-blue-50 text-blue-700">
                            <User className="h-5 w-5" />
                        </div>
                        <div className="min-w-0">
                            <p className="truncate text-sm font-bold text-slate-950">{auth.username || '사용자'}</p>
                            <p className="truncate text-xs text-slate-500">{auth.email}</p>
                            <p className="mt-1 text-xs font-medium text-blue-600">{auth.provider}</p>
                        </div>
                    </div>

                    {isAdmin && (
                        <button
                            type="button"
                            onClick={goToAdmin}
                            className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-blue-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-blue-700"
                        >
                            <ShieldCheck className="h-4 w-4" />
                            관리자 페이지
                        </button>
                    )}

                    <div className="mt-4 rounded-2xl bg-slate-50 p-3">
                        <div className="flex items-center gap-2 text-xs font-semibold text-slate-500">
                            <LinkIcon className="h-3.5 w-3.5" />
                            Discord 연동 상태
                        </div>
                        <p className="mt-1 text-sm font-semibold text-slate-800">
                            {auth.discordLinked ? 'Discord 계정 연동됨' : 'Discord 계정 미연동'}
                        </p>
                        <p className="mt-1 text-xs leading-relaxed text-slate-500">
                            웹에서 Discord 구독목록을 확인하거나 변경하려면 Discord 계정 연동이 필요합니다.
                        </p>
                    </div>

                    <div className="mt-3 grid grid-cols-2 gap-2">
                        <button
                            type="button"
                            className="rounded-2xl border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-600 transition hover:bg-slate-50"
                            onClick={goToMyInfo}
                        >
                            내정보
                        </button>
                        <button
                            type="button"
                            onClick={handleLogout}
                            disabled={logoutPending}
                            className="inline-flex items-center justify-center gap-2 rounded-2xl bg-slate-900 px-3 py-2 text-sm font-semibold text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                            <LogOut className="h-4 w-4" />
                            {logoutPending ? '로그아웃 중...' : '로그아웃'}
                        </button>
                    </div>

                    {logoutError && (
                        <p role="alert" className="mt-3 text-sm font-semibold text-rose-600">
                            {logoutError}
                        </p>
                    )}
                </div>
            )}
        </div>
    );
}
