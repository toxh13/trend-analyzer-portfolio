import React from 'react';
import { NavLink } from 'react-router-dom';
import { Activity, BarChart3, FileText, Home, Layers, Menu, Search, Tags, User } from 'lucide-react';
import { isStaticMode } from '../config/dataMode';

const MENU_ITEMS = [
    { id: 'popular-keywords', label: '인기 키워드', icon: Home, to: '/' },
    { id: 'category-analysis', label: '카테고리 분석', icon: Tags, to: '/categories' },
    { id: 'keyword-analysis', label: '키워드 분석', icon: Search, to: '/keywords' },
    { id: 'keyword-compare', label: '키워드 비교', icon: BarChart3, to: '/history' },
    { id: 'articles', label: '관련 기사', icon: FileText, to: '/articles' },
    { id: 'my-info', label: '내정보', icon: User, to: '/my-info' },
];

// static 모드에는 로그인 서버가 없으므로 내정보를 빼고 읽기 전용 운영 현황을 넣습니다.
const STATIC_MENU_ITEMS = [
    ...MENU_ITEMS.filter((item) => item.id !== 'my-info'),
    { id: 'operations-status', label: '운영 현황', icon: Activity, to: '/status' },
];

export default function SidebarNav({ isOpen, onToggle, stats }) {
    const closeMobileMenu = () => {
        if (typeof window !== 'undefined' && window.innerWidth < 1024 && isOpen) {
            onToggle?.();
        }
    };

    const trackedKeywordCount = stats?.trackedKeywords ?? stats?.tracked ?? 0;
    const windowHours = stats?.windowHours ?? 24;
    const menuItems = isStaticMode() ? STATIC_MENU_ITEMS : MENU_ITEMS;

    return (
        <>
            {isOpen && (
                <button
                    type="button"
                    className="fixed inset-0 z-30 bg-slate-900/30 lg:hidden"
                    aria-label="메뉴 닫기 배경"
                    onClick={onToggle}
                />
            )}

            <aside
                className={`fixed left-0 top-0 z-40 flex h-screen flex-col overflow-hidden border-r border-slate-200 bg-white shadow-xl shadow-slate-200/60 transition-all duration-300 lg:sticky lg:z-10 lg:shadow-none ${
                    isOpen ? 'w-72 translate-x-0' : '-translate-x-full lg:w-20 lg:translate-x-0'
                }`}
            >
                <div
                    className={`flex h-16 items-center border-b border-slate-100 px-4 ${
                        isOpen ? 'justify-between' : 'justify-center'
                    }`}
                >
                    {isOpen && (
                        <div className="flex min-w-0 items-center gap-3 overflow-hidden">
                            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-blue-600 text-white">
                                <Layers className="h-5 w-5" />
                            </div>
                            <div className="min-w-0">
                                <p className="truncate text-sm font-bold text-slate-900">Trend Analyzer</p>
                                <p className="truncate text-xs text-slate-500">실시간 키워드 분석</p>
                            </div>
                        </div>
                    )}

                    <button
                        type="button"
                        onClick={onToggle}
                        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl text-slate-500 transition hover:bg-slate-100 hover:text-slate-900"
                        aria-label="사이드바 열기 또는 닫기"
                    >
                        <Menu className="h-5 w-5" />
                    </button>
                </div>

                <nav className="flex-1 space-y-1 px-3 py-4">
                    {menuItems.map((item) => {
                        const Icon = item.icon;

                        return (
                            <NavLink
                                key={item.id}
                                to={item.to}
                                end={item.to === '/'}
                                onClick={closeMobileMenu}
                                className={({ isActive }) => `flex items-center rounded-2xl px-3 py-3 text-sm font-medium transition ${
                                    isOpen ? 'gap-3 justify-start' : 'justify-center'
                                } ${
                                    isActive
                                        ? 'bg-blue-50 text-blue-700'
                                        : 'text-slate-600 hover:bg-blue-50 hover:text-blue-700'
                                }`}
                                title={!isOpen ? item.label : undefined}
                            >
                                <Icon className="h-5 w-5 shrink-0" />
                                {isOpen && <span>{item.label}</span>}
                            </NavLink>
                        );
                    })}
                </nav>

                <div className="border-t border-slate-100 p-4">
                    {isOpen ? (
                        <div className="rounded-2xl bg-slate-50 p-4">
                            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">오늘의 분석 상태</p>
                            <p className="mt-2 text-2xl font-bold text-slate-900">{trackedKeywordCount.toLocaleString()}개</p>
                            <p className="text-xs text-slate-500">최근 {windowHours}시간 추적 키워드</p>
                        </div>
                    ) : (
                        <div className="mx-auto h-10 w-10 rounded-2xl bg-slate-50" />
                    )}
                </div>
            </aside>
        </>
    );
}
