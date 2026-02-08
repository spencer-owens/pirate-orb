'use client';

import { useState, useEffect } from 'react';
import { Search, User, Disc3, Plus, Check, Loader2, X } from 'lucide-react';
import Link from 'next/link';
import CoverArt from './components/CoverArt';
import { CardSkeleton } from './components/LoadingSkeleton';

type SearchType = 'artist' | 'album';

export default function Home() {
  const [query, setQuery] = useState('');
  const [searchType, setSearchType] = useState<SearchType>('artist');
  const [results, setResults] = useState<any>({});
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState<string | null>(null);
  const [added, setAdded] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [lidarrArtists, setLidarrArtists] = useState<Set<string>>(new Set());

  useEffect(() => {
    fetch('/api/lidarr/artists')
      .then(r => r.json())
      .then(data => {
        if (data.artists) setLidarrArtists(new Set(data.artists.map((a: any) => a.foreignArtistId)));
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (query.length < 2) { setResults({}); return; }
    const timer = setTimeout(async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`/api/search?q=${encodeURIComponent(query)}&type=${searchType}`);
        const data = await res.json();
        if (data.error) setError(data.error);
        else setResults(data);
      } catch { setError('Search failed'); }
      setLoading(false);
    }, 350);
    return () => clearTimeout(timer);
  }, [query, searchType]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === '/' && !['INPUT', 'TEXTAREA'].includes((e.target as HTMLElement).tagName)) {
        e.preventDefault();
        document.getElementById('search-input')?.focus();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  const addArtist = async (artist: any) => {
    setAdding(artist.id);
    try {
      const res = await fetch('/api/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: 'artist', mbid: artist.id, name: artist.name }),
      });
      const data = await res.json();
      if (data.success || data.id) {
        setAdded(prev => new Set([...prev, artist.id]));
        setLidarrArtists(prev => new Set([...prev, artist.id]));
      } else setError(data.error || 'Failed to add');
    } catch { setError('Failed to add'); }
    setAdding(null);
  };

  const isInLibrary = (id: string) => lidarrArtists.has(id) || added.has(id);

  return (
    <div className="space-y-6">
      {/* Search controls */}
      <div className="space-y-4">
        <div className="flex gap-2">
          {(['artist', 'album'] as const).map(t => (
            <button key={t} onClick={() => setSearchType(t)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                searchType === t ? 'bg-emerald-500 text-black' : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700'
              }`}>
              {t === 'artist' ? <User className="w-4 h-4" /> : <Disc3 className="w-4 h-4" />}
              {t === 'artist' ? 'Artists' : 'Albums'}
            </button>
          ))}
        </div>
        <div className="relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500" />
          <input id="search-input" type="text" value={query} onChange={e => setQuery(e.target.value)}
            placeholder={`Search for ${searchType}s... (press / to focus)`}
            className="w-full bg-zinc-800 border border-zinc-700 rounded-xl pl-12 pr-4 py-4 text-lg placeholder:text-zinc-500 focus:outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20" />
          {loading && <Loader2 className="absolute right-4 top-1/2 -translate-y-1/2 w-5 h-5 text-emerald-400 animate-spin" />}
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 flex items-center gap-2">
          <X className="w-5 h-5 flex-shrink-0" /> {error}
        </div>
      )}

      {loading && query.length >= 2 && <CardSkeleton count={5} />}

      {/* Artist results */}
      {!loading && searchType === 'artist' && (
        <div className="space-y-2">
          {results.artists?.map((artist: any) => (
            <div key={artist.id} className="flex items-center justify-between p-4 bg-zinc-800/50 border border-zinc-700/50 rounded-xl hover:bg-zinc-800 transition-colors group">
              <Link href={`/artist/${artist.id}`} className="flex items-center gap-4 flex-1 min-w-0">
                <CoverArt mbid={artist.id} alt={artist.name} size="sm" type="artist" />
                <div className="min-w-0">
                  <h3 className="font-semibold text-lg truncate group-hover:text-emerald-400 transition-colors">{artist.name}</h3>
                  <p className="text-sm text-zinc-500 truncate">
                    {[artist.type, artist.country, artist.disambiguation].filter(Boolean).join(' · ') || 'Artist'}
                  </p>
                </div>
              </Link>
              <button onClick={() => addArtist(artist)} disabled={adding === artist.id || isInLibrary(artist.id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors flex-shrink-0 ml-3 ${
                  isInLibrary(artist.id) ? 'bg-emerald-500/20 text-emerald-400' : adding === artist.id ? 'bg-zinc-700 text-zinc-400' : 'bg-emerald-500 text-black hover:bg-emerald-400'
                }`}>
                {isInLibrary(artist.id) ? <><Check className="w-4 h-4" /> In Library</> :
                 adding === artist.id ? <><Loader2 className="w-4 h-4 animate-spin" /> Adding...</> :
                 <><Plus className="w-4 h-4" /> Add</>}
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Album results */}
      {!loading && searchType === 'album' && (
        <div className="space-y-2">
          {results['release-groups']?.map((album: any) => (
            <Link key={album.id} href={`/album/${album.id}`}
              className="flex items-center gap-4 p-4 bg-zinc-800/50 border border-zinc-700/50 rounded-xl hover:bg-zinc-800 transition-colors group block">
              <CoverArt mbid={album.id} alt={album.title} size="sm" />
              <div className="min-w-0 flex-1">
                <h3 className="font-semibold text-lg truncate group-hover:text-emerald-400 transition-colors">{album.title}</h3>
                <p className="text-sm text-zinc-500 truncate">
                  {album['artist-credit']?.[0]?.name}
                  {album['first-release-date'] && ` · ${album['first-release-date'].slice(0, 4)}`}
                  {album['primary-type'] && ` · ${album['primary-type']}`}
                </p>
              </div>
            </Link>
          ))}
        </div>
      )}

      {query.length >= 2 && !loading && searchType === 'artist' && !results.artists?.length && (
        <p className="text-center py-12 text-zinc-500">No artists found for &ldquo;{query}&rdquo;</p>
      )}
      {query.length >= 2 && !loading && searchType === 'album' && !results['release-groups']?.length && (
        <p className="text-center py-12 text-zinc-500">No albums found for &ldquo;{query}&rdquo;</p>
      )}
      {query.length < 2 && !loading && (
        <p className="text-center py-12 text-zinc-500">Start typing to search MusicBrainz...</p>
      )}
    </div>
  );
}
