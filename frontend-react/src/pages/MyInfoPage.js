import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Link as LinkIcon, LogIn, RefreshCw, Tags, Unlink, User, X } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';

import { buildApiUrl } from '../utils/apiBaseUrl';

export default function MyInfoPage() {
    const [searchParams] = useSearchParams();
    const [auth, setAuth] = useState({ authenticated: false });
    const [subscriptions, setSubscriptions] = useState([]);
    const [subscriptionKeyword, setSubscriptionKeyword] = useState('');
    const [loading, setLoading] = useState(true);
    const [actionLoading, setActionLoading] = useState(false);
    const [notice, setNotice] = useState(null);

    const discordLinkResult = searchParams.get('discordLink');
    const discordLinkMessage = searchParams.get('message');

    const discordNotice = useMemo(() => {
        if (!discordLinkResult) {
            return null;
        }

        return {
            type: discordLinkResult === 'success' ? 'success' : 'error',
            message: discordLinkMessage || (discordLinkResult === 'success'
                ? 'Discord 계정 연동이 완료되었습니다.'
                : 'Discord 계정 연동에 실패했습니다.'),
        };
    }, [discordLinkResult, discordLinkMessage]);

    const loadMyInfo = useCallback(async () => {
        setLoading(true);

        try {
            // 현재 로그인 사용자 정보를 조회합니다. 세션 쿠키 기반이므로 withCredentials가 필요합니다.
            const meResponse = await axios.get(buildApiUrl('/api/v1/auth/me'), {
                withCredentials: true,
            });

            const currentAuth = meResponse.data;
            setAuth(currentAuth);

            if (currentAuth.authenticated) {
                try {
                    // 로그인 사용자만 구독 키워드를 조회합니다.
                    // 이 API가 rate limit 또는 Discord 연동 문제로 실패해도 로그인 상태 자체는 유지합니다.
                    const subscriptionResponse = await axios.get(buildApiUrl('/api/v1/me/subscriptions'), {
                        withCredentials: true,
                    });

                    setSubscriptions(subscriptionResponse.data);
                } catch (subscriptionError) {
                    console.error('구독 키워드 조회 실패:', subscriptionError);
                    setSubscriptions([]);
                    setNotice({ type: 'error', message: '구독 키워드를 불러오지 못했습니다. 로그인 상태는 유지됩니다.' });
                }
            } else {
                setSubscriptions([]);
            }
        } catch (error) {
            console.error('내정보 조회 실패:', error);
            setAuth({ authenticated: false });
            setSubscriptions([]);
            setNotice({ type: 'error', message: '내정보를 불러오지 못했습니다.' });
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadMyInfo();
    }, [loadMyInfo]);

    useEffect(() => {
        if (discordNotice) {
            setNotice(discordNotice);
        }
    }, [discordNotice]);

    const handleGoogleLogin = () => {
        // 기존 Google OAuth 시작점을 그대로 사용합니다.
        window.location.href = buildApiUrl('/oauth2/authorization/google');
    };

    const handleDiscordLink = () => {
        // 백엔드가 Discord OAuth 인증 URL을 생성한 뒤 Discord로 redirect합니다.
        window.location.href = buildApiUrl('/api/v1/me/discord/link');
    };

    const handleDiscordUnlink = async () => {
        const confirmed = window.confirm('Discord 계정 연동을 해제할까요? 구독 키워드는 삭제되지 않습니다.');
        if (!confirmed) {
            return;
        }

        setActionLoading(true);

        try {
            const response = await axios.delete(buildApiUrl('/api/v1/me/discord/link'), {
                withCredentials: true,
            });

            setNotice({ type: 'success', message: response.data.message || 'Discord 연동을 해제했습니다.' });
            await loadMyInfo();
        } catch (error) {
            console.error('Discord 연동 해제 실패:', error);
            setNotice({ type: 'error', message: 'Discord 연동 해제에 실패했습니다.' });
        } finally {
            setActionLoading(false);
        }
    };

    const getErrorMessage = (error, fallback) => error?.response?.data?.message || fallback;

    const handleCreateSubscription = async (event) => {
        event.preventDefault();
        const keyword = subscriptionKeyword.trim();
        if (!keyword) {
            setNotice({ type: 'error', message: '구독할 키워드를 입력해 주세요.' });
            return;
        }

        setActionLoading(true);
        try {
            const response = await axios.post(buildApiUrl('/api/v1/me/subscriptions'), { keyword }, {
                withCredentials: true,
            });
            setSubscriptions((current) => [response.data, ...current]);
            setSubscriptionKeyword('');
            setNotice({ type: 'success', message: `#${response.data.keyword} 키워드를 구독했습니다. Discord Bot에도 즉시 반영됩니다.` });
        } catch (error) {
            console.error('웹 구독 생성 실패:', error);
            setNotice({ type: 'error', message: getErrorMessage(error, '키워드 구독에 실패했습니다.') });
        } finally {
            setActionLoading(false);
        }
    };

    const handleDeleteSubscription = async (subscription) => {
        setActionLoading(true);
        try {
            await axios.delete(buildApiUrl(`/api/v1/me/subscriptions/${subscription.id}`), {
                withCredentials: true,
            });
            setSubscriptions((current) => current.filter((item) => item.id !== subscription.id));
            setNotice({ type: 'success', message: `#${subscription.keyword} 키워드 구독을 취소했습니다. Discord Bot에도 즉시 반영됩니다.` });
        } catch (error) {
            console.error('웹 구독 취소 실패:', error);
            setNotice({ type: 'error', message: getErrorMessage(error, '키워드 구독 취소에 실패했습니다.') });
        } finally {
            setActionLoading(false);
        }
    };

    if (loading) {
        return (
            <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="h-6 w-40 animate-pulse rounded bg-slate-100" />
                <div className="mt-4 h-20 animate-pulse rounded-2xl bg-slate-50" />
            </section>
        );
    }

    if (!auth.authenticated) {
        return (
            <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="flex items-center gap-3">
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-50 text-blue-700">
                        <User className="h-6 w-6" />
                    </div>
                    <div>
                        <h2 className="text-xl font-bold text-slate-950">내정보</h2>
                        <p className="text-sm text-slate-500">Discord 연동과 구독 키워드를 확인하려면 로그인이 필요합니다.</p>
                    </div>
                </div>

                <button
                    type="button"
                    onClick={handleGoogleLogin}
                    className="mt-6 inline-flex items-center gap-2 rounded-2xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-700"
                >
                    <LogIn className="h-4 w-4" />
                    Google로 로그인
                </button>
            </section>
        );
    }

    return (
        <div className="space-y-6">
            <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                    <div className="flex items-center gap-3">
                        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-50 text-blue-700">
                            <User className="h-6 w-6" />
                        </div>
                        <div>
                            <h2 className="text-xl font-bold text-slate-950">내정보</h2>
                            <p className="text-sm text-slate-500">OAuth 로그인 계정과 Discord Bot 구독 정보를 연결합니다.</p>
                        </div>
                    </div>

                    <button
                        type="button"
                        onClick={loadMyInfo}
                        className="inline-flex items-center justify-center gap-2 rounded-2xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600 transition hover:bg-slate-50"
                    >
                        <RefreshCw className="h-4 w-4" />
                        새로고침
                    </button>
                </div>

                {notice && (
                    <div className={`mt-5 rounded-2xl px-4 py-3 text-sm font-medium ${
                        notice.type === 'success'
                            ? 'bg-emerald-50 text-emerald-700'
                            : 'bg-rose-50 text-rose-700'
                    }`}>
                        {notice.message}
                    </div>
                )}

                <div className="mt-6 grid gap-4 md:grid-cols-3">
                    <InfoCard label="이름" value={auth.username || '사용자'} />
                    <InfoCard label="이메일" value={auth.email || '-'} />
                    <InfoCard label="로그인 방식" value={auth.provider || '-'} />
                </div>
            </section>

            <section className="grid gap-6 lg:grid-cols-2">
                <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                    <div className="flex items-center gap-2">
                        <LinkIcon className="h-5 w-5 text-blue-600" />
                        <h3 className="text-lg font-bold text-slate-950">Discord 연동</h3>
                    </div>

                    <p className="mt-3 text-sm leading-relaxed text-slate-500">
                        Discord 계정을 연동하면 Discord Bot에서 구독한 키워드를 웹 대시보드에서도 확인할 수 있습니다.
                    </p>

                    <div className="mt-4 rounded-2xl bg-slate-50 p-4">
                        <p className="text-sm font-semibold text-slate-800">
                            {auth.discordLinked ? 'Discord 계정 연동됨' : 'Discord 계정 미연동'}
                        </p>
                        <p className="mt-1 text-xs text-slate-500">
                            Discord User ID: {auth.discordUserId || '-'}
                        </p>
                    </div>

                    <div className="mt-4 flex flex-wrap gap-2">
                        {auth.discordLinked ? (
                            <button
                                type="button"
                                disabled={actionLoading}
                                onClick={handleDiscordUnlink}
                                className="inline-flex items-center gap-2 rounded-2xl border border-rose-200 px-4 py-2 text-sm font-semibold text-rose-600 transition hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                                <Unlink className="h-4 w-4" />
                                연동 해제
                            </button>
                        ) : (
                            <button
                                type="button"
                                onClick={handleDiscordLink}
                                className="rounded-2xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-700"
                            >
                                Discord 연동하기
                            </button>
                        )}
                    </div>
                </div>

                <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                    <div className="flex items-center gap-2">
                        <Tags className="h-5 w-5 text-blue-600" />
                        <h3 className="text-lg font-bold text-slate-950">구독한 키워드</h3>
                    </div>

                    <p className="mt-3 text-sm leading-relaxed text-slate-500">
                        Discord 계정을 연동하면 웹과 Bot이 같은 구독 목록을 사용합니다. 웹에서 변경하면 Discord의 <span className="font-semibold text-slate-700">/list</span>에도 즉시 반영됩니다.
                    </p>

                    {auth.discordLinked ? (
                        <form onSubmit={handleCreateSubscription} className="mt-4 flex gap-2">
                            <input
                                value={subscriptionKeyword}
                                onChange={(event) => setSubscriptionKeyword(event.target.value)}
                                maxLength={100}
                                placeholder="예: LLM, 클라우드"
                                disabled={actionLoading}
                                className="min-w-0 flex-1 rounded-2xl border border-slate-200 px-3 py-2 text-sm outline-none transition focus:border-blue-400 focus:ring-4 focus:ring-blue-50 disabled:bg-slate-50"
                            />
                            <button
                                type="submit"
                                disabled={actionLoading}
                                className="rounded-2xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                                구독
                            </button>
                        </form>
                    ) : (
                        <p className="mt-4 rounded-2xl bg-amber-50 px-4 py-3 text-sm text-amber-700">
                            웹에서 구독을 관리하려면 먼저 Discord 계정을 연동해 주세요.
                        </p>
                    )}

                    <div className="mt-4 flex flex-wrap gap-2">
                        {subscriptions.length > 0 ? (
                            subscriptions.map((item) => (
                                <div
                                    key={item.id}
                                    className="inline-flex items-center gap-1 rounded-full bg-blue-50 py-1 pl-3 pr-1 text-sm font-semibold text-blue-700"
                                    title={item.createdAt ? `구독일: ${item.createdAt}` : undefined}
                                >
                                    #{item.keyword}
                                    {auth.discordLinked && (
                                        <button
                                            type="button"
                                            onClick={() => handleDeleteSubscription(item)}
                                            disabled={actionLoading}
                                            aria-label={`${item.keyword} 구독 취소`}
                                            className="rounded-full p-1 text-blue-600 transition hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-50"
                                        >
                                            <X className="h-3.5 w-3.5" />
                                        </button>
                                    )}
                                </div>
                            ))
                        ) : (
                            <p className="rounded-2xl bg-slate-50 px-4 py-3 text-sm text-slate-400">
                                아직 구독한 키워드가 없습니다.
                            </p>
                        )}
                    </div>
                </div>
            </section>
        </div>
    );
}

function InfoCard({ label, value }) {
    return (
        <div className="rounded-2xl bg-slate-50 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</p>
            <p className="mt-2 truncate text-sm font-bold text-slate-900">{value}</p>
        </div>
    );
}
