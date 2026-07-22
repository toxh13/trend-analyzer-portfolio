import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchTrends } from '../api/trendApi';

// 트렌드 목록 조회 전용 커스텀 훅입니다.
// 페이지 컴포넌트는 API 호출 세부 구현을 몰라도 loading/error/trends만 사용하면 됩니다.
export function useTrends(categoryName = 'ALL', options = {}) {
    const enabled = options.enabled ?? true;
    const autoLoad = options.autoLoad ?? true;
    const [trends, setTrends] = useState([]);
    const [loadingTrends, setLoadingTrends] = useState(enabled);
    const [trendError, setTrendError] = useState(null);
    const mountedRef = useRef(true);
    const requestIdRef = useRef(0);
    const inFlightRef = useRef(null);
    const hasSuccessfulDataRef = useRef(false);

    useEffect(() => {
        mountedRef.current = true;
        return () => {
            mountedRef.current = false;
            requestIdRef.current += 1;
        };
    }, []);

    const refreshTrends = useCallback((reset = false) => {
        if (!enabled) {
            return Promise.resolve([]);
        }

        if (inFlightRef.current) {
            return inFlightRef.current;
        }

        const requestId = ++requestIdRef.current;
        if (reset) {
            hasSuccessfulDataRef.current = false;
            setTrends([]);
        }

        if (!hasSuccessfulDataRef.current) {
            setLoadingTrends(true);
        }
        setTrendError(null);

        const request = fetchTrends(categoryName)
            .then((data) => {
                if (mountedRef.current && requestId === requestIdRef.current) {
                    setTrends(data);
                    hasSuccessfulDataRef.current = true;
                }
                return data;
            })
            .catch((error) => {
                console.error('트렌드 데이터를 가져오는 중 오류 발생:', error);
                if (mountedRef.current && requestId === requestIdRef.current) {
                    setTrendError(error);
                }
                throw error;
            })
            .finally(() => {
                if (mountedRef.current && requestId === requestIdRef.current) {
                    setLoadingTrends(false);
                }
                if (inFlightRef.current === request) {
                    inFlightRef.current = null;
                }
            });

        inFlightRef.current = request;
        return request;
    }, [categoryName, enabled]);

    useEffect(() => {
        requestIdRef.current += 1;
        inFlightRef.current = null;

        if (!enabled) {
            setTrends([]);
            setTrendError(null);
            setLoadingTrends(false);
            hasSuccessfulDataRef.current = false;
            return undefined;
        }

        if (!autoLoad) {
            setLoadingTrends(false);
            return undefined;
        }

        refreshTrends(true).catch(() => {});
        return undefined;
    }, [autoLoad, categoryName, enabled, refreshTrends]);

    return { trends, loadingTrends, trendError, refreshTrends };
}
