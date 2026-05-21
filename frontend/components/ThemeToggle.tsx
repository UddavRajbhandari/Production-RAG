'use client';

import { useTheme } from '@/providers/ThemeProvider';
import { Sun, Moon } from 'lucide-react';

export default function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();

  return (
    <button
      onClick={toggleTheme}
      className="relative flex h-7 w-13 items-center rounded-full border border-border bg-background-muted transition-colors duration-200 hover:border-accent-primary/50"
      aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
      role="switch"
      aria-checked={theme === 'light'}
    >
      <span
        className={`flex h-5 w-5 items-center justify-center rounded-full transition-all duration-200 ${
          theme === 'light'
            ? 'translate-x-7 bg-accent-primary text-background-primary'
            : 'translate-x-1 bg-text-muted text-text-primary'
        }`}
      >
        {theme === 'light' ? (
          <Sun size={11} />
        ) : (
          <Moon size={11} />
        )}
      </span>
    </button>
  );
}
