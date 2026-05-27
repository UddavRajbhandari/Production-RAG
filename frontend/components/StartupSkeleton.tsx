'use client';

export default function StartupSkeleton() {
  return (
    <div className="flex min-h-screen flex-col bg-background-primary">
      {/* Navbar skeleton */}
      <div className="flex h-13 items-center border-b border-border bg-background-surface px-4">
        <div className="skeleton-shimmer h-5 w-32" />
        <div className="ml-auto flex items-center gap-3">
          <div className="skeleton-shimmer h-7 w-7 rounded-full" />
          <div className="skeleton-shimmer h-7 w-16 rounded-input" />
        </div>
      </div>

      {/* Main content skeleton */}
      <div className="mx-auto flex w-full max-w-[1600px] flex-1">
        {/* Sidebar skeleton */}
        <aside className="hidden w-64 shrink-0 border-r border-border bg-background-surface md:flex md:flex-col p-4 gap-4">
          <div className="skeleton-shimmer h-36 w-full rounded-card" />
          <div className="space-y-3">
            <div className="skeleton-shimmer h-4 w-24" />
            <div className="skeleton-shimmer h-3 w-full" />
            <div className="skeleton-shimmer h-3 w-3/4" />
            <div className="skeleton-shimmer h-3 w-5/6" />
            <div className="skeleton-shimmer h-3 w-2/3" />
          </div>
        </aside>

        {/* Chat area skeleton */}
        <main className="flex flex-1 flex-col items-center justify-center px-6" style={{ height: 'calc(100vh - 3.25rem)' }}>
          <div className="flex flex-col items-center gap-6">
            {/* Logo */}
            <div className="skeleton-shimmer h-14 w-14 rounded-full" />

            {/* Title */}
            <div className="space-y-3 text-center">
              <div className="skeleton-shimmer mx-auto h-6 w-48" />
              <div className="skeleton-shimmer mx-auto h-4 w-72" />
            </div>

            {/* Status indicator */}
            <div className="mt-4 flex items-center gap-3 rounded-card border border-border bg-background-surface px-5 py-3">
              <div className="h-2.5 w-2.5 animate-pulse rounded-full bg-accent-primary" />
              <div className="space-y-1.5">
                <div className="skeleton-shimmer h-3.5 w-36" />
                <div className="skeleton-shimmer h-3 w-48" />
              </div>
            </div>

            {/* Input bar skeleton */}
            <div className="mt-8 w-full max-w-xl">
              <div className="skeleton-shimmer h-11 w-full rounded-input" />
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
