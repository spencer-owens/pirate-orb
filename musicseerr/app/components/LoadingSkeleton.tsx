export function CardSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 p-4 bg-zinc-800/50 border border-zinc-700/50 rounded-xl animate-pulse">
          <div className="w-12 h-12 bg-zinc-700 rounded-lg flex-shrink-0" />
          <div className="flex-1 space-y-2">
            <div className="h-4 bg-zinc-700 rounded w-1/3" />
            <div className="h-3 bg-zinc-700/60 rounded w-1/5" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function GridSkeleton({ count = 12 }: { count?: number }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="animate-pulse">
          <div className="aspect-square bg-zinc-800 rounded-lg mb-2" />
          <div className="h-4 bg-zinc-800 rounded w-3/4 mb-1" />
          <div className="h-3 bg-zinc-800/60 rounded w-1/2" />
        </div>
      ))}
    </div>
  );
}
