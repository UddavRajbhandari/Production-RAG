import type { Metadata } from 'next';
import './globals.css';
import { ThemeProvider } from '@/providers/ThemeProvider';

const SITE_NAME = 'Production RAG';
const DESCRIPTION = 'Production-grade Retrieval-Augmented Generation pipeline with hybrid search, multi-agent reasoning, LLM guardrails, and RAGAS evaluation. Upload documents and query your data with AI.';

export const metadata: Metadata = {
  title: {
    default: SITE_NAME,
    template: `%s | ${SITE_NAME}`,
  },
  description: DESCRIPTION,
  keywords: ['Production RAG', 'RAG pipeline', 'retrieval augmented generation', 'document Q&A', 'AI search', 'hybrid search', 'LLM', 'vector database', 'document retrieval'],
  authors: [{ name: 'Production RAG' }],
  openGraph: {
    title: SITE_NAME,
    description: DESCRIPTION,
    siteName: SITE_NAME,
    type: 'website',
    locale: 'en_US',
  },
  twitter: {
    card: 'summary_large_image',
    title: SITE_NAME,
    description: DESCRIPTION,
  },
  icons: {
    icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="6" fill="%230a0a0f"/><circle cx="16" cy="16" r="8" fill="none" stroke="%236ee7b7" stroke-width="2"/><circle cx="16" cy="16" r="3" fill="%236ee7b7"/></svg>',
  },
  metadataBase: process.env.NEXT_PUBLIC_API_URL ? new URL(process.env.NEXT_PUBLIC_API_URL.replace('/api/v1', '')) : undefined,
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
