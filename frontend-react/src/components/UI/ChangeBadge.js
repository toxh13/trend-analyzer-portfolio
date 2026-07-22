import React from 'react';
import { Minus, Sparkles, TrendingDown, TrendingUp } from 'lucide-react';

export function ChangeBadge({ type, value }) {
    if (type === 'up') {
        return (
            <span className="td-data inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700">
                <TrendingUp className="h-3.5 w-3.5" />
                +{value}
            </span>
        );
    }

    if (type === 'down') {
        return (
            <span className="td-data inline-flex items-center gap-1 rounded-full bg-rose-50 px-2 py-1 text-xs font-semibold text-rose-700">
                <TrendingDown className="h-3.5 w-3.5" />
                {value}
            </span>
        );
    }

    if (type === 'new') {
        return (
            <span className="td-data inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-1 text-xs font-semibold text-amber-700">
                <Sparkles className="h-3.5 w-3.5" />
                NEW
            </span>
        );
    }

    return (
        <span className="td-data inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-500">
            <Minus className="h-3.5 w-3.5" />0
        </span>
    );
}
