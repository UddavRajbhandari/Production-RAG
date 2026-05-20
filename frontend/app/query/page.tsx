import { Suspense } from 'react';
import QueryPageClient from './QueryPageClient';

export default function QueryPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-background-primary" />}>
      <QueryPageClient />
    </Suspense>
  );
}
