function TrendListSkeleton() {
    return (
        <div className="space-y-2">
            {Array.from({ length: 7 }).map((_, i) => (
                <div key={i} className="flex items-center gap-4 rounded-xl border border-slate-800 bg-slate-900 px-4 py-4">
                    <div className="h-5 w-6 animate-pulse rounded bg-slate-800" />
                    <div className="flex-1 space-y-2">
                        <div className="h-3 w-32 animate-pulse rounded bg-slate-800" />
                        <div className="h-1.5 w-24 animate-pulse rounded bg-slate-800" />
                    </div>
                    <div className="h-3 w-10 animate-pulse rounded bg-slate-800" />
                </div>
            ))}
        </div>
    );
}
export default TrendListSkeleton;