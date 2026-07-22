import React from 'react';
import { Menu, RefreshCw } from 'lucide-react';
import AuthMenu from './AuthMenu';

export default function DashboardHeader({ updatedAt, isRefreshing = false, onRefresh, onToggleMenu }) {
    return (
        <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur">
            <div className="flex items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
                <div className="flex min-w-0 items-center gap-3">
                    {onToggleMenu && (
                        <button
                            type="button"
                            onClick={onToggleMenu}
                            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 lg:hidden"
                            aria-label="사이드바 열기"
                        >
                            <Menu className="h-5 w-5" />
                        </button>
                    )}

                    <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-blue-600 overflow-hidden">
                        <img src="/logo.png" alt="logo" className="h-8 w-8 object-cover" />
                    </div>

                    <div className="min-w-0">
                        <h1 className="td-display truncate text-lg font-bold tracking-tight text-slate-950 sm:text-2xl">
                            트렌드 분석 아키텍처
                        </h1>
                        <p className="mt-0.5 hidden text-sm text-slate-500 sm:block">
                            키워드 순위뿐만 아니라 변동성, 상승/하락 흐름, 관련 기사 탐색을 기준으로 정보를 분석합니다.
                        </p>
                    </div>
                </div>

                <div className="flex shrink-0 items-center gap-3">
                    {onRefresh && (
                        <button
                            type="button"
                            onClick={onRefresh}
                            disabled={isRefreshing}
                            className="flex h-10 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-600 transition hover:border-blue-200 hover:text-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
                            aria-label="데이터 새로고침"
                        >
                            <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
                            <span className="hidden sm:inline">{isRefreshing ? '조회 중' : '새로고침'}</span>
                        </button>
                    )}
                    <div className="td-data hidden items-center gap-2 rounded-full border border-emerald-100 bg-emerald-50 px-3 py-2 text-xs font-medium text-emerald-700 md:flex">
                        <span className="relative flex h-2 w-2">
                            <span className="absolute h-2 w-2 animate-ping rounded-full bg-emerald-400 opacity-60" />
                            <span className="relative h-2 w-2 rounded-full bg-emerald-500" />
                        </span>
                        마지막 전체 조회 · {updatedAt || '--:--'}
                    </div>
                    <AuthMenu />
                </div>
            </div>
        </header>
    );
}
