import React, { useEffect, useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { Link } from 'react-router-dom';

import { fetchSiteMeta } from '../api/staticTrendApi';
import { isStaticMode } from '../config/dataMode';
import { describeFreshness, formatSeoulLocal } from '../utils/freshness';

// static 모드에서 수집이 늦어지거나(stale) 멈췄을 때(down) 대시보드 상단에 띄우는 안내입니다.
// API 모드에서는 아무것도 그리지 않습니다.
export default function StaticFreshnessBanner() {
    const [meta, setMeta] = useState(null);

    useEffect(() => {
        if (!isStaticMode()) return undefined;

        let mounted = true;
        fetchSiteMeta()
            .then((result) => {
                if (mounted) setMeta(result);
            })
            .catch((error) => console.error('배포 메타데이터 조회 실패:', error));

        return () => {
            mounted = false;
        };
    }, []);

    if (!meta || (meta.freshness !== 'stale' && meta.freshness !== 'down')) {
        return null;
    }

    const isDown = meta.freshness === 'down';
    return (
        <div
            role="status"
            className={`mb-5 flex items-start gap-3 rounded-2xl border px-4 py-3 text-sm ${
                isDown ? 'border-rose-200 bg-rose-50 text-rose-800' : 'border-amber-200 bg-amber-50 text-amber-900'
            }`}
        >
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
                <p className="font-semibold">
                    {isDown ? '데이터 수집이 중단된 상태입니다.' : '데이터 수집이 지연되고 있습니다.'}
                    <span className="ml-2 font-normal">기준 시각 {formatSeoulLocal(meta.asOf)} (서울)</span>
                </p>
                <p className="mt-1">
                    {describeFreshness(meta)}{' '}
                    <Link to="/status" className="font-semibold underline">운영 현황 보기</Link>
                </p>
            </div>
        </div>
    );
}
