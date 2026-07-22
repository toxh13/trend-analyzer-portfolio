import React from 'react';

export function RankBadge({ rank }) {
    const color = rank === 1
        ? 'bg-amber-50 text-amber-600'
        : rank === 2
            ? 'bg-slate-100 text-slate-600'
            : rank === 3
                ? 'bg-orange-50 text-orange-600'
                : 'bg-slate-50 text-slate-500';

    return (
        <div className={`td-data flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl text-sm font-bold ${color}`}>
            {rank}
        </div>
    );
}
