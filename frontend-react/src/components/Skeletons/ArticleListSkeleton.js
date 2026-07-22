function ArticleListSkeleton() {
    return (
        <div className="space-y-3 px-4 py-4">
            {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="space-y-2">
                    <div className="h-3 w-full animate-pulse rounded bg-slate-800" />
                    <div className="h-3 w-2/3 animate-pulse rounded bg-slate-800" />
                </div>
            ))}
        </div>
    );
}
export default ArticleListSkeleton;