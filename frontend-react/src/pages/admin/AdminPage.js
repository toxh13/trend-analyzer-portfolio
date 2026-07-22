import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';

import AdminHeader from '../../components/admin/AdminHeader';
import AdminCrawlRunsTab from '../../components/admin/AdminCrawlRunsTab';
import AdminKeywordGroupsTab from '../../components/admin/AdminKeywordGroupsTab';
import AdminKeywordTab from '../../components/admin/AdminKeywordTab';
import AdminMergeSuggestionsTab from '../../components/admin/AdminMergeSuggestionsTab';
import AdminSummaryCards from '../../components/admin/AdminSummaryCards';
import AdminTabNav from '../../components/admin/AdminTabNav';
import { getErrorMessage } from '../../components/admin/adminUtils';
import { buildApiUrl } from '../../utils/apiBaseUrl';
import { fetchCrawlRun, fetchCrawlRuns } from '../../api/crawlRunApi';

export default function AdminPage() {
    const [keywords, setKeywords] = useState([]);
    const [stats, setStats] = useState(null);
    const [form, setForm] = useState({
        keyword: '',
        category: '',
        priority: 0,
        notionEnabled: true,
        keywordType: 'TRACKING',
    });
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [analyzing, setAnalyzing] = useState(false);
    const [generatingSuggestions, setGeneratingSuggestions] = useState(false);
    const [recommendationRun, setRecommendationRun] = useState(null);
    const [notice, setNotice] = useState(null);
    const [activeTab, setActiveTab] = useState('keywords');
    const [keywordGroups, setKeywordGroups] = useState([]);
    const [mergeSuggestions, setMergeSuggestions] = useState([]);
    const [groupSearchKeyword, setGroupSearchKeyword] = useState('');
    const [suggestionGroupSearchKeyword, setSuggestionGroupSearchKeyword] = useState('');
    const [selectedSuggestionGroupId, setSelectedSuggestionGroupId] = useState(null);
    const [expandedGroupIds, setExpandedGroupIds] = useState({});
    const [groupForm, setGroupForm] = useState({
        canonicalKeyword: '',
        description: '',
        active: true,
    });
    const [aliasForms, setAliasForms] = useState({});
    const [crawlRuns, setCrawlRuns] = useState([]);
    const [crawlRunsLoading, setCrawlRunsLoading] = useState(false);
    const [crawlRunsLoaded, setCrawlRunsLoaded] = useState(false);
    const [crawlRunsError, setCrawlRunsError] = useState(null);
    const [selectedCrawlRun, setSelectedCrawlRun] = useState(null);
    const [selectedCrawlRunId, setSelectedCrawlRunId] = useState(null);
    const [crawlRunDetailLoading, setCrawlRunDetailLoading] = useState(false);
    const [crawlRunDetailError, setCrawlRunDetailError] = useState(null);

    const activeKeywordCount = useMemo(
        () => keywords.filter((item) => item.active).length,
        [keywords]
    );

    const filteredKeywordGroups = useMemo(() => {
        const searchValue = groupSearchKeyword.trim().toLowerCase();

        if (!searchValue) {
            return keywordGroups;
        }

        return keywordGroups.filter((group) => {
            const canonicalKeyword = group.canonicalKeyword?.toLowerCase() || '';
            const description = group.description?.toLowerCase() || '';
            const aliasMatched = (group.aliases || []).some((alias) =>
                alias.rawKeyword?.toLowerCase().includes(searchValue)
            );

            return canonicalKeyword.includes(searchValue)
                || description.includes(searchValue)
                || aliasMatched;
        });
    }, [keywordGroups, groupSearchKeyword]);

    const filteredSuggestionGroups = useMemo(() => {
        const searchValue = suggestionGroupSearchKeyword.trim().toLowerCase();

        return keywordGroups
            .filter((group) => group.active)
            .filter((group) => {
                if (!searchValue) {
                    return true;
                }

                const canonicalKeyword = group.canonicalKeyword?.toLowerCase() || '';
                const description = group.description?.toLowerCase() || '';
                const aliasMatched = (group.aliases || []).some((alias) =>
                    alias.rawKeyword?.toLowerCase().includes(searchValue)
                );

                return canonicalKeyword.includes(searchValue)
                    || description.includes(searchValue)
                    || aliasMatched;
            });
    }, [keywordGroups, suggestionGroupSearchKeyword]);

    const selectedSuggestionGroup = useMemo(
        () => keywordGroups.find((group) => group.id === selectedSuggestionGroupId) || null,
        [keywordGroups, selectedSuggestionGroupId]
    );

    const loadRecommendationRun = useCallback(async (targetGroupId) => {
        if (!targetGroupId) {
            setRecommendationRun(null);
            return;
        }

        const response = await axios.get(
            buildApiUrl(`/api/v1/admin/keyword-merge-suggestions/runs/latest?targetGroupId=${targetGroupId}`),
            { withCredentials: true }
        );
        setRecommendationRun(response.status === 204 ? null : response.data);
    }, []);

    const loadAdminData = useCallback(async () => {
        setLoading(true);
        setNotice(null);

        try {
            const [keywordResponse, statsResponse, groupResponse, suggestionResponse] = await Promise.all([
                axios.get(buildApiUrl('/api/v1/admin/keywords'), { withCredentials: true }),
                axios.get(buildApiUrl('/api/v1/trends/stats'), { withCredentials: true }),
                axios.get(buildApiUrl('/api/v1/admin/keyword-groups'), { withCredentials: true }),
                axios.get(buildApiUrl('/api/v1/admin/keyword-merge-suggestions?status=PENDING'), { withCredentials: true }),
            ]);

            setKeywords(keywordResponse.data || []);
            setStats(statsResponse.data || null);
            setKeywordGroups(groupResponse.data || []);
            setMergeSuggestions(suggestionResponse.data || []);
        } catch (error) {
            console.error('관리자 데이터 조회 실패:', error);
            setNotice({ type: 'error', message: getErrorMessage(error, '관리자 데이터를 불러오지 못했습니다.') });
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadAdminData();
    }, [loadAdminData]);

    useEffect(() => {
        if (activeTab !== 'suggestions') {
            return;
        }

        loadRecommendationRun(selectedSuggestionGroupId).catch((error) => {
            console.error('AI recommendation run lookup failed:', error);
        });
    }, [activeTab, selectedSuggestionGroupId, loadRecommendationRun]);

    useEffect(() => {
        if (!recommendationRun || !['PENDING', 'RUNNING'].includes(recommendationRun.status)) {
            return undefined;
        }

        const intervalId = window.setInterval(async () => {
            try {
                await loadRecommendationRun(recommendationRun.targetGroupId);
            } catch (error) {
                console.error('AI recommendation run polling failed:', error);
            }
        }, 3000);

        return () => window.clearInterval(intervalId);
    }, [recommendationRun, loadRecommendationRun]);

    const loadCrawlRuns = useCallback(async () => {
        setCrawlRunsLoading(true);
        setCrawlRunsError(null);

        try {
            setCrawlRuns(await fetchCrawlRuns(20));
            setCrawlRunsLoaded(true);
        } catch (error) {
            console.error('수집 실행 이력 조회 실패:', error);
            setCrawlRunsError(getErrorMessage(error, '수집 실행 이력을 불러오지 못했습니다.'));
            setCrawlRunsLoaded(true);
        } finally {
            setCrawlRunsLoading(false);
        }
    }, []);

    useEffect(() => {
        if (activeTab === 'crawl-runs' && !crawlRunsLoaded && !crawlRunsLoading) {
            loadCrawlRuns();
        }
    }, [activeTab, crawlRunsLoaded, crawlRunsLoading, loadCrawlRuns]);

    const handleSelectCrawlRun = useCallback(async (runId) => {
        setSelectedCrawlRunId(runId);
        setSelectedCrawlRun(null);
        setCrawlRunDetailLoading(true);
        setCrawlRunDetailError(null);

        try {
            setSelectedCrawlRun(await fetchCrawlRun(runId));
        } catch (error) {
            console.error('수집 실행 상세 조회 실패:', error);
            setCrawlRunDetailError(getErrorMessage(error, '선택한 실행의 상세 정보를 불러오지 못했습니다.'));
        } finally {
            setCrawlRunDetailLoading(false);
        }
    }, []);

    const handleChange = (event) => {
        const { name, value, type, checked } = event.target;

        setForm((prev) => ({
            ...prev,
            [name]: type === 'checkbox' ? checked : value,
        }));
    };

    const handleGroupFormChange = (name, value) => {
        setGroupForm((prev) => ({
            ...prev,
            [name]: value,
        }));
    };

    const handleToggleGroupExpand = (groupId) => {
        setExpandedGroupIds((prev) => ({
            ...prev,
            [groupId]: !prev[groupId],
        }));
    };

    const handleCreateKeyword = async (event) => {
        event.preventDefault();

        if (!form.keyword.trim()) {
            setNotice({ type: 'error', message: '키워드를 입력해주세요.' });
            return;
        }

        setSaving(true);
        setNotice(null);

        try {
            await axios.post(buildApiUrl('/api/v1/admin/keywords'), {
                keyword: form.keyword.trim(),
                category: form.category.trim() || null,
                priority: Number(form.priority) || 0,
                notionEnabled: Boolean(form.notionEnabled),
                active: true,
                keywordType: form.keywordType,
            }, {
                withCredentials: true,
            });

            setForm({
                keyword: '',
                category: '',
                priority: 0,
                notionEnabled: true,
                keywordType: 'TRACKING',
            });
            setNotice({ type: 'success', message: '키워드를 등록했습니다.' });
            await loadAdminData();
        } catch (error) {
            console.error('키워드 등록 실패:', error);
            setNotice({ type: 'error', message: getErrorMessage(error, '키워드 등록에 실패했습니다.') });
        } finally {
            setSaving(false);
        }
    };

    const handleAliasChange = (groupId, value) => {
        setAliasForms((prev) => ({
            ...prev,
            [groupId]: value,
        }));
    };

    const handleAddAlias = async (groupId) => {
        const rawKeyword = aliasForms[groupId]?.trim();

        if (!rawKeyword) {
            setNotice({ type: 'error', message: '추가할 alias를 입력해주세요.' });
            return;
        }

        setNotice(null);

        try {
            await axios.post(buildApiUrl(`/api/v1/admin/keyword-groups/${groupId}/aliases`), {
                rawKeyword,
            }, {
                withCredentials: true,
            });

            setAliasForms((prev) => ({
                ...prev,
                [groupId]: '',
            }));

            setNotice({ type: 'success', message: 'alias를 추가했습니다.' });
            await loadAdminData();
        } catch (error) {
            console.error('alias 추가 실패:', error);
            setNotice({ type: 'error', message: getErrorMessage(error, 'alias 추가에 실패했습니다.') });
        }
    };

    const handleCreateGroup = async (event) => {
        event.preventDefault();

        if (!groupForm.canonicalKeyword.trim()) {
            setNotice({ type: 'error', message: '대표 키워드를 입력해주세요.' });
            return;
        }

        setSaving(true);
        setNotice(null);

        try {
            await axios.post(buildApiUrl('/api/v1/admin/keyword-groups'), {
                canonicalKeyword: groupForm.canonicalKeyword.trim(),
                description: groupForm.description.trim() || null,
                active: Boolean(groupForm.active),
            }, {
                withCredentials: true,
            });

            setGroupForm({
                canonicalKeyword: '',
                description: '',
                active: true,
            });

            setNotice({ type: 'success', message: '대표 키워드 그룹을 생성했습니다.' });
            await loadAdminData();
        } catch (error) {
            console.error('대표 키워드 그룹 생성 실패:', error);
            setNotice({ type: 'error', message: getErrorMessage(error, '대표 키워드 그룹 생성에 실패했습니다.') });
        } finally {
            setSaving(false);
        }
    };

    const handleActivateGroup = async (groupId) => {
        const confirmed = window.confirm('이 대표 키워드 그룹을 다시 활성화할까요?');
        if (!confirmed) {
            return;
        }

        setNotice(null);

        try {
            await axios.patch(buildApiUrl(`/api/v1/admin/keyword-groups/${groupId}/activate`), null, {
                withCredentials: true,
            });

            setNotice({ type: 'success', message: '대표 키워드 그룹을 활성화했습니다.' });
            await loadAdminData();
        } catch (error) {
            console.error('대표 키워드 그룹 활성화 실패:', error);
            setNotice({ type: 'error', message: getErrorMessage(error, '대표 키워드 그룹 활성화에 실패했습니다.') });
        }
    };

    const handleDeactivateGroup = async (groupId) => {
        const confirmed = window.confirm('이 대표 키워드 그룹을 비활성화할까요? 연결된 alias도 함께 비활성화합니다.');
        if (!confirmed) {
            return;
        }

        setNotice(null);

        try {
            await axios.patch(buildApiUrl(`/api/v1/admin/keyword-groups/${groupId}/deactivate`), null, {
                withCredentials: true,
            });

            setNotice({ type: 'success', message: '대표 키워드 그룹을 비활성화했습니다.' });
            await loadAdminData();
        } catch (error) {
            console.error('대표 키워드 그룹 비활성화 실패:', error);
            setNotice({ type: 'error', message: getErrorMessage(error, '대표 키워드 그룹 비활성화에 실패했습니다.') });
        }
    };

    const handleActivateAlias = async (aliasId) => {
        const confirmed = window.confirm('이 alias를 다시 활성화할까요?');
        if (!confirmed) {
            return;
        }

        setNotice(null);

        try {
            await axios.patch(buildApiUrl(`/api/v1/admin/keyword-aliases/${aliasId}/activate`), null, {
                withCredentials: true,
            });

            setNotice({ type: 'success', message: 'alias를 활성화했습니다.' });
            await loadAdminData();
        } catch (error) {
            console.error('alias 활성화 실패:', error);
            setNotice({ type: 'error', message: getErrorMessage(error, 'alias 활성화에 실패했습니다.') });
        }
    };

    const handleDeactivateAlias = async (aliasId) => {
        const confirmed = window.confirm('이 alias를 비활성화할까요?');
        if (!confirmed) {
            return;
        }

        setNotice(null);

        try {
            await axios.patch(buildApiUrl(`/api/v1/admin/keyword-aliases/${aliasId}/deactivate`), null, {
                withCredentials: true,
            });

            setNotice({ type: 'success', message: 'alias를 비활성화했습니다.' });
            await loadAdminData();
        } catch (error) {
            console.error('alias 비활성화 실패:', error);
            setNotice({ type: 'error', message: getErrorMessage(error, 'alias 비활성화에 실패했습니다.') });
        }
    };

    const handleDetachAlias = async (aliasId, rawKeyword) => {
        const confirmed = window.confirm(
            `"${rawKeyword}" alias 연결을 완전히 해제할까요?\n해제하면 다른 대표 키워드에 다시 추가할 수 있습니다.`
        );

        if (!confirmed) {
            return;
        }

        setNotice(null);

        try {
            await axios.delete(buildApiUrl(`/api/v1/admin/keyword-aliases/${aliasId}`), {
                withCredentials: true,
            });

            setNotice({ type: 'success', message: 'alias 연결을 해제했습니다.' });
            await loadAdminData();
        } catch (error) {
            console.error('alias 해제 실패:', error);
            setNotice({ type: 'error', message: getErrorMessage(error, 'alias 해제에 실패했습니다.') });
        }
    };

    const handleApproveSuggestion = async (suggestionId) => {
        const confirmed = window.confirm('이 추천을 승인해서 alias로 등록할까요?');
        if (!confirmed) {
            return;
        }

        setNotice(null);

        try {
            await axios.patch(buildApiUrl(`/api/v1/admin/keyword-merge-suggestions/${suggestionId}/approve`), null, {
                withCredentials: true,
            });

            setNotice({ type: 'success', message: 'AI 추천을 승인했습니다.' });
            await loadAdminData();
        } catch (error) {
            console.error('AI 추천 승인 실패:', error);
            setNotice({ type: 'error', message: getErrorMessage(error, 'AI 추천 승인에 실패했습니다.') });
        }
    };

    const handleRejectSuggestion = async (suggestionId) => {
        const confirmed = window.confirm('이 추천을 거절할까요? 같은 대표 키워드 기준에서는 다시 추천되지 않습니다.');
        if (!confirmed) {
            return;
        }

        setNotice(null);

        try {
            await axios.patch(buildApiUrl(`/api/v1/admin/keyword-merge-suggestions/${suggestionId}/reject`), null, {
                withCredentials: true,
            });

            setNotice({ type: 'success', message: 'AI 추천을 거절했습니다.' });
            await loadAdminData();
        } catch (error) {
            console.error('AI 추천 거절 실패:', error);
            setNotice({ type: 'error', message: getErrorMessage(error, 'AI 추천 거절에 실패했습니다.') });
        }
    };

    const handleGenerateSuggestions = async () => {
        if (!selectedSuggestionGroup) {
            setNotice({ type: 'error', message: 'AI 추천을 생성할 대표 키워드 그룹을 선택해주세요.' });
            return;
        }

        const confirmed = window.confirm(`"${selectedSuggestionGroup.canonicalKeyword}" 대표 키워드 기준으로 AI 병합 추천을 생성할까요?`);
        if (!confirmed) {
            return;
        }

        setGeneratingSuggestions(true);
        setNotice(null);

        try {
            const response = await axios.post(buildApiUrl(`/api/v1/admin/keyword-merge-suggestions/generate?targetGroupId=${selectedSuggestionGroup.id}`), null, {
                withCredentials: true,
            });

            setRecommendationRun(response.data);

            await loadAdminData();
            setNotice({ type: 'success', message: 'AI 추천 작업을 등록했습니다. 실행 상태는 자동으로 갱신됩니다.' });
        } catch (error) {
            console.error('AI 추천 생성 실패:', error);
            setNotice({ type: 'error', message: getErrorMessage(error, 'AI 추천 생성에 실패했습니다.') });
        } finally {
            setGeneratingSuggestions(false);
        }
    };

    const handleToggleKeyword = async (id) => {
        setNotice(null);

        try {
            await axios.patch(buildApiUrl(`/api/v1/admin/keywords/${id}/toggle`), null, {
                withCredentials: true,
            });

            await loadAdminData();
        } catch (error) {
            console.error('키워드 상태 변경 실패:', error);
            setNotice({ type: 'error', message: getErrorMessage(error, '키워드 상태 변경에 실패했습니다.') });
        }
    };

    const handleAnalyzeNow = async () => {
        const confirmed = window.confirm('지금 트렌드 분석 배치를 수동 실행할까요?');
        if (!confirmed) {
            return;
        }

        setAnalyzing(true);
        setNotice(null);

        try {
            await axios.post(buildApiUrl('/api/v1/admin/trends/analyze-now'), null, {
                withCredentials: true,
            });

            setNotice({ type: 'success', message: '트렌드 분석을 실행했습니다.' });
            await loadAdminData();
        } catch (error) {
            console.error('수동 분석 실행 실패:', error);
            setNotice({ type: 'error', message: getErrorMessage(error, '수동 분석 실행에 실패했습니다.') });
        } finally {
            setAnalyzing(false);
        }
    };

    return (
        <div className="min-h-screen bg-slate-50 text-slate-900" style={{ fontFamily: "'Inter', system-ui, sans-serif" }}>
            <AdminHeader />

            <main className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
                {notice && (
                    <div className={`rounded-2xl px-4 py-3 text-sm font-semibold ${
                        notice.type === 'success'
                            ? 'bg-emerald-50 text-emerald-700'
                            : 'bg-rose-50 text-rose-700'
                    }`}>
                        {notice.message}
                    </div>
                )}

                <AdminTabNav activeTab={activeTab} onChangeTab={setActiveTab} />

                {activeTab !== 'crawl-runs' && (
                    <AdminSummaryCards
                        keywords={keywords}
                        activeKeywordCount={activeKeywordCount}
                        stats={stats}
                        analyzing={analyzing}
                        onAnalyzeNow={handleAnalyzeNow}
                    />
                )}

                {activeTab === 'keywords' && (
                    <AdminKeywordTab
                        form={form}
                        keywords={keywords}
                        loading={loading}
                        saving={saving}
                        onChange={handleChange}
                        onCreateKeyword={handleCreateKeyword}
                        onRefresh={loadAdminData}
                        onToggleKeyword={handleToggleKeyword}
                    />
                )}

                {activeTab === 'groups' && (
                    <AdminKeywordGroupsTab
                        groupForm={groupForm}
                        saving={saving}
                        filteredKeywordGroups={filteredKeywordGroups}
                        groupSearchKeyword={groupSearchKeyword}
                        expandedGroupIds={expandedGroupIds}
                        aliasForms={aliasForms}
                        onGroupFormChange={handleGroupFormChange}
                        onCreateGroup={handleCreateGroup}
                        onGroupSearchChange={setGroupSearchKeyword}
                        onRefresh={loadAdminData}
                        onToggleGroupExpand={handleToggleGroupExpand}
                        onActivateGroup={handleActivateGroup}
                        onDeactivateGroup={handleDeactivateGroup}
                        onAliasChange={handleAliasChange}
                        onAddAlias={handleAddAlias}
                        onActivateAlias={handleActivateAlias}
                        onDeactivateAlias={handleDeactivateAlias}
                        onDetachAlias={handleDetachAlias}
                    />
                )}

                {activeTab === 'suggestions' && (
                    <AdminMergeSuggestionsTab
                        generatingSuggestions={generatingSuggestions}
                        recommendationRun={recommendationRun}
                        selectedSuggestionGroup={selectedSuggestionGroup}
                        suggestionGroupSearchKeyword={suggestionGroupSearchKeyword}
                        filteredSuggestionGroups={filteredSuggestionGroups}
                        selectedSuggestionGroupId={selectedSuggestionGroupId}
                        mergeSuggestions={mergeSuggestions}
                        onGenerateSuggestions={handleGenerateSuggestions}
                        onRefresh={async () => {
                            await loadAdminData();
                            await loadRecommendationRun(selectedSuggestionGroupId);
                        }}
                        onSuggestionGroupSearchChange={setSuggestionGroupSearchKeyword}
                        onSelectSuggestionGroup={setSelectedSuggestionGroupId}
                        onApproveSuggestion={handleApproveSuggestion}
                        onRejectSuggestion={handleRejectSuggestion}
                    />
                )}

                {activeTab === 'crawl-runs' && (
                    <AdminCrawlRunsTab
                        runs={crawlRuns}
                        loading={crawlRunsLoading}
                        error={crawlRunsError}
                        selectedRun={selectedCrawlRun}
                        detailLoading={crawlRunDetailLoading}
                        detailError={crawlRunDetailError}
                        onRefresh={loadCrawlRuns}
                        onSelectRun={handleSelectCrawlRun}
                        onRetryDetail={() => selectedCrawlRunId && handleSelectCrawlRun(selectedCrawlRunId)}
                    />
                )}
            </main>
        </div>
    );
}
