import React, { useEffect, useState } from 'react';
import { fetchCategories } from '../api/trendApi';
import { CATEGORIES } from '../utils/trendUtils';

export default function CategoryFilter({ selectedCategory, setSelectedCategory, trends = [], includeAll = true }) {
    const [categories, setCategories] = useState(CATEGORIES);

    useEffect(() => {
        let mounted = true;
        fetchCategories()
            .then((rows) => {
                if (mounted) setCategories(rows);
            })
            .catch(() => {
                if (mounted) setCategories(CATEGORIES);
            });

        return () => {
            mounted = false;
        };
    }, []);

    return (
        <section className="mt-5 rounded-3xl border border-slate-200 bg-white p-3 shadow-sm">
            <div className="flex gap-2 overflow-x-auto">
                {categories
                    .filter((cat) => includeAll || cat.id !== 'ALL')
                    .map((cat) => {
                    const active = selectedCategory === cat.id;
                    const savedCount = Number(cat.trendCount);
                    const count = Number.isFinite(savedCount) && savedCount > 0
                        ? savedCount
                        : cat.id === 'ALL'
                            ? trends.length
                            : trends.filter((trend) => trend.category === cat.id).length;

                    return (
                        <button
                            key={cat.id}
                            type="button"
                            onClick={() => setSelectedCategory(cat.id, cat)}
                            className={`flex items-center gap-2 whitespace-nowrap rounded-2xl border px-4 py-2 text-sm font-semibold transition focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-blue-100 ${
                                active
                                    ? 'border-blue-600 bg-blue-600 text-white shadow-sm'
                                    : 'border-slate-200 bg-white text-slate-600 hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700'
                            }`}
                        >
                            {cat.hex && (
                                <span
                                    className={`h-2 w-2 rounded-full ${active ? 'bg-white' : ''}`}
                                    style={active ? undefined : { backgroundColor: cat.hex }}
                                />
                            )}
                            {cat.label}
                            <span className={`td-data text-xs ${active ? 'text-blue-100' : 'text-slate-400'}`}>{count}</span>
                        </button>
                    );
                })}
            </div>
        </section>
    );
}
