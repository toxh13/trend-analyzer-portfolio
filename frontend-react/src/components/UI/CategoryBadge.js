import React from 'react';
import { createCategoryMeta } from '../../utils/trendUtils';

function hexToRgba(hex, alpha) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

export function CategoryBadge({ category }) {
    if (!category) return null;

    const meta = createCategoryMeta(category);

    return (
        <span
            className={`rounded-full px-2 py-0.5 text-xs font-semibold ${meta.text}`}
            style={{ backgroundColor: hexToRgba(meta.hex, 0.1) }}
        >
            {category}
        </span>
    );
}
