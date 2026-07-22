import { useEffect, useState } from 'react';
import { fetchKeywordArticles, fetchKeywordHistory } from '../api/trendApi';

// 키워드 상세 화면에서 필요한 관련 기사와 7일 히스토리를 함께 가져오는 훅입니다.
export function useKeywordDetail(keyword) {
    const [articles, setArticles] = useState([]);
    const [history, setHistory] = useState([]);
    const [loadingKeywordDetail, setLoadingKeywordDetail] = useState(false);
    const [keywordDetailError, setKeywordDetailError] = useState(null);

    useEffect(() => {
        if (!keyword) {
            setArticles([]);
            setHistory([]);
            return undefined;
        }

        let isMounted = true;

        async function loadKeywordDetail() {
            setLoadingKeywordDetail(true);
            setKeywordDetailError(null);

            try {
                const [articleData, historyData] = await Promise.all([
                    fetchKeywordArticles(keyword),
                    fetchKeywordHistory(keyword),
                ]);

                if (isMounted) {
                    setArticles(articleData);
                    setHistory(historyData);
                }
            } catch (error) {
                console.error('키워드 상세 데이터를 가져오는 중 오류 발생:', error);
                if (isMounted) {
                    setArticles([]);
                    setHistory([]);
                    setKeywordDetailError(error);
                }
            } finally {
                if (isMounted) {
                    setLoadingKeywordDetail(false);
                }
            }
        }

        loadKeywordDetail();

        // 라우트가 바뀌었을 때 이전 요청 결과가 새 화면에 덮어써지지 않게 막습니다.
        return () => {
            isMounted = false;
        };
    }, [keyword]);

    return {
        articles,
        history,
        loadingKeywordDetail,
        keywordDetailError,
    };
}
