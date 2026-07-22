import React, { useMemo, useState } from 'react';
import { Bot, Send, Sparkles } from 'lucide-react';

function formatKeywordList(items) {
    if (!items.length) return '아직 추천할 키워드 데이터가 없습니다.';
    return items.map((item, index) => `${index + 1}. ${item.keyword}`).join('\n');
}

function buildAnswer(question, trends) {
    const normalizedQuestion = question.toLowerCase();
    const rising = trends.filter((item) => Number(item.velocityScore ?? item.velocity_score ?? item.changeValue ?? 0) > 0);
    const falling = trends.filter((item) => Number(item.velocityScore ?? item.velocity_score ?? item.changeValue ?? 0) < 0);
    const topVolatile = [...trends]
        .sort((a, b) => {
            const aVelocity = Math.abs(Number(a.velocityScore ?? a.velocity_score ?? a.changeValue ?? 0));
            const bVelocity = Math.abs(Number(b.velocityScore ?? b.velocity_score ?? b.changeValue ?? 0));
            return bVelocity - aVelocity;
        })
        .slice(0, 5);

    // 현재는 백엔드 AI API가 없으므로 프론트엔드 데이터 기반의 규칙형 답변을 제공합니다.
    // 추후 /api/v1/chat 또는 /api/v1/ai/summary 같은 API가 생기면 이 함수만 API 호출로 교체하면 됩니다.
    if (normalizedQuestion.includes('상승') || normalizedQuestion.includes('급상승')) {
        return `현재 상승 흐름이 있는 키워드는 다음과 같습니다.\n\n${formatKeywordList(rising.slice(0, 5))}`;
    }

    if (normalizedQuestion.includes('하락') || normalizedQuestion.includes('감소')) {
        return `현재 하락 흐름이 있는 키워드는 다음과 같습니다.\n\n${formatKeywordList(falling.slice(0, 5))}`;
    }

    if (normalizedQuestion.includes('변동') || normalizedQuestion.includes('불안정')) {
        return `변동성이 큰 키워드는 다음과 같습니다.\n\n${formatKeywordList(topVolatile)}`;
    }

    if (normalizedQuestion.includes('경제')) {
        return `경제 카테고리에서 확인할 만한 키워드입니다.\n\n${formatKeywordList(trends.filter((item) => item.category === '경제').slice(0, 5))}`;
    }

    if (normalizedQuestion.includes('it') || normalizedQuestion.includes('과학') || normalizedQuestion.includes('기술')) {
        return `IT/과학 카테고리에서 확인할 만한 키워드입니다.\n\n${formatKeywordList(trends.filter((item) => item.category === 'IT/과학').slice(0, 5))}`;
    }

    return `최근 키워드 흐름을 요약하면 다음 키워드를 먼저 확인하는 것이 좋습니다.\n\n${formatKeywordList(trends.slice(0, 5))}\n\n질문 예시: “급상승 키워드 알려줘”, “변동성 큰 키워드 뭐야?”, “경제 키워드만 보여줘”`;
}

export default function TrendChatbot({ trends = [] }) {
    const [input, setInput] = useState('');
    const [messages, setMessages] = useState([
        {
            role: 'bot',
            content: '안녕하세요. 최근 키워드 데이터를 기준으로 트렌드 흐름을 요약해드릴게요.',
        },
    ]);

    const quickPrompts = useMemo(
        () => ['급상승 키워드 알려줘', '변동성 큰 키워드 뭐야?', '경제 키워드만 보여줘'],
        []
    );

    const handleSubmit = (event, forcedQuestion) => {
        event?.preventDefault();
        const question = (forcedQuestion ?? input).trim();
        if (!question) return;

        const answer = buildAnswer(question, trends);

        setMessages((prev) => [
            ...prev,
            { role: 'user', content: question },
            { role: 'bot', content: answer },
        ]);
        setInput('');
    };

    return (
        <section id="chatbot" className="rounded-3xl border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-100 px-5 py-4">
                <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-blue-50 text-blue-600">
                        <Bot className="h-5 w-5" />
                    </div>
                    <div>
                        <h2 className="font-bold text-slate-950">키워드 챗봇</h2>
                        <p className="text-xs text-slate-500">현재 화면의 트렌드 데이터를 기반으로 답변합니다.</p>
                    </div>
                </div>
            </div>

            <div className="max-h-80 space-y-3 overflow-y-auto px-5 py-4">
                {messages.map((message, index) => (
                    <div
                        key={`${message.role}-${index}`}
                        className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                            message.role === 'bot'
                                ? 'bg-slate-50 text-slate-700'
                                : 'ml-8 bg-blue-600 text-white'
                        }`}
                    >
                        <pre className="whitespace-pre-wrap font-sans">{message.content}</pre>
                    </div>
                ))}
            </div>

            <div className="flex flex-wrap gap-2 px-5 pb-3">
                {quickPrompts.map((prompt) => (
                    <button
                        key={prompt}
                        type="button"
                        onClick={(event) => handleSubmit(event, prompt)}
                        className="inline-flex items-center gap-1 rounded-full border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700"
                    >
                        <Sparkles className="h-3 w-3" />
                        {prompt}
                    </button>
                ))}
            </div>

            <form onSubmit={handleSubmit} className="flex gap-2 border-t border-slate-100 p-4">
                <input
                    value={input}
                    onChange={(event) => setInput(event.target.value)}
                    className="min-w-0 flex-1 rounded-2xl border border-slate-200 px-4 py-2 text-sm outline-none transition focus:border-blue-400 focus:ring-4 focus:ring-blue-100"
                    placeholder="최근 키워드에 대해 질문해보세요"
                />
                <button
                    type="submit"
                    className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-blue-600 text-white transition hover:bg-blue-700"
                    aria-label="챗봇 질문 보내기"
                >
                    <Send className="h-4 w-4" />
                </button>
            </form>
        </section>
    );
}
