'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, MessageSquare, Settings, FileText } from 'lucide-react';

const navItems = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/documents', label: 'Documents', icon: FileText },
  { href: '/query', label: 'Query', icon: MessageSquare },
  { href: '/settings', label: 'Settings', icon: Settings },
];

export default function Navbar() {
  const pathname = usePathname();

  return (
    <header className="fixed top-0 left-0 right-0 z-50 border-b border-border bg-background-surface/95 backdrop-blur-sm">
      <div className="mx-auto flex h-13 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2.5 transition-opacity hover:opacity-80">
          <svg width="28" height="28" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect width="32" height="32" rx="6" fill="#111118" />
            <circle cx="16" cy="16" r="9" fill="none" stroke="#6ee7b7" strokeWidth="1.5" />
            <circle cx="16" cy="16" r="4" fill="none" stroke="#6ee7b7" strokeWidth="1.5" />
            <circle cx="16" cy="16" r="1.5" fill="#6ee7b7" />
          </svg>
          <span className="font-display text-base font-semibold tracking-wide text-text-primary">
            Production<span className="text-accent-primary">RAG</span>
          </span>
        </Link>

        <nav className="flex items-center gap-1">
          {navItems.map(({ href, label, icon: Icon }) => {
            const isActive = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-1.5 rounded-input px-3 py-2 text-xs font-medium transition-all duration-150 ${
                  isActive
                    ? 'bg-accent-primary-muted text-accent-primary'
                    : 'text-text-secondary hover:bg-background-muted hover:text-text-primary'
                }`}
              >
                <Icon size={14} strokeWidth={1.5} />
                <span className="hidden sm:inline">{label}</span>
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
