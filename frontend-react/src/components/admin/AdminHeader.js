import React from 'react';
import { ArrowLeft, ShieldCheck } from 'lucide-react';
import { Link } from 'react-router-dom';

export default function AdminHeader() {
    return (
        <header className="border-b border-slate-200 bg-white">
            <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-4 py-5 sm:px-6 lg:px-8">
                <div className="flex items-center gap-3">
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-600 text-white">
                        <ShieldCheck className="h-6 w-6" />
                    </div>
                    <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-blue-600">Admin</p>
                        <h1 className="text-xl font-bold text-slate-950 sm:text-2xl">최소 관리자 페이지</h1>
                        <p className="text-sm text-slate-500">키워드 관리와 수동 트렌드 분석만 제공합니다.</p>
                    </div>
                </div>

                <Link
                    to="/"
                    className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-600 transition hover:bg-slate-50"
                >
                    <ArrowLeft className="h-4 w-4" />
                    대시보드로
                </Link>
            </div>
        </header>
    );
}
