'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Search, Library, Clock, Music } from 'lucide-react';

const links = [
  { href: '/', label: 'Search', icon: Search },
  { href: '/library', label: 'Library', icon: Library },
  { href: '/requests', label: 'Requests', icon: Clock },
];

export default function Nav() {
  const pathname = usePathname();

  return (
    <header className="border-b border-zinc-800 bg-zinc-900/80 backdrop-blur sticky top-0 z-50">
      <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2 text-emerald-400 hover:text-emerald-300 transition-colors">
          <Music className="w-7 h-7" />
          <span className="text-xl font-bold hidden sm:inline">MusicSeerr</span>
        </Link>
        <nav className="flex gap-1">
          {links.map(({ href, label, icon: Icon }) => {
            const active = href === '/' ? pathname === '/' : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  active ? 'bg-emerald-500/20 text-emerald-400' : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800'
                }`}
              >
                <Icon className="w-4 h-4" />
                <span className="hidden sm:inline">{label}</span>
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
