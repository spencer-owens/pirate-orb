'use client';

import { useState, useEffect, useCallback } from 'react';
import { Search, Music, Disc3, User, Plus, Check, Loader2, X } from 'lucide-react';

interface Artist {
  id: string;
  name: string;
  type?: string;
  country?: string;
  disambiguation?: string;
  score?: number;
}

interface Album {
  id: string;
  title: string;
  'primary-type'?: string;
  'first-release-date'?: string;
  'artist-credit'?: { name: string }[];
}

interface SearchResult {
  artists?: Artist[];
  'release-groups'?: Album[];
}

type SearchType = 'artist' | 'album';

export default function Home() {
  const [query, setQuery] = useState('');
  const [searchType, setSearchType] = useState<SearchType>('artist');
  const [results, setResults] = useState<SearchResult>({});
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState<string | null>(null);
  const [added, setAdded] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [lidarrArtists, setLidarrArtists] = useState<Set<string>>(new Set());

  // Fetch existing Lidarr artists on mount
  useEffect(() => {
    fetch('/api/lidarr/artists')
      .then(res => res.json())
      .then(data => {
        if (data.artists) {
          setLidarrArtists(new Set(data.artists.map((a: any) => a.foreignArtistId)));
        }
      })
      .catch(console.error);
  }, []);

  // Debounced search
  useEffect(() => {
    if (query.length < 2) {
      setResults({});
      return;
    }

    const timer = setTimeout(async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`/api/search?q=${encodeURIComponent(query)}&type=${searchType}`);
        const data = await res.json();
        if (data.error) {
          setError(data.error);
        } else {
          setResults(data);
        }
      } catch (e) {
        setError('Search failed');
      }
      setLoading(false);
    }, 300);

    return () => clearTimeout(timer);
  }, [query, searchType]);

  const addToLidarr = async (item: Artist | Album, type: 'artist' | 'album') => {
    setAdding(item.id);
    setError(null);
    
    try {
      const res = await fetch('/api/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type,
          mbid: item.id,
          name: type === 'artist' ? (item as Artist).name : (item as Album).title,
        }),
      });
      
      const data = await res.json();
      
      if (data.success) {
        setAdded(prev => new Set([...prev, item.id]));
        if (type === 'artist') {
          setLidarrArtists(prev => new Set([...prev, item.id]));
        }
      } else {
        setError(data.error || 'Failed to add');
      }
    } catch (e) {
      setError('Failed to add to Lidarr');
    }
    
    setAdding(null);
  };

  const isInLibrary = (id: string) => lidarrArtists.has(id) || added.has(id);

  return (
    <main className="min-h-screen bg-gradient-to-b from-zinc-900 to-zinc-950">
      {/* Header */}
      <header className="border-b border-zinc-800 bg-zinc-900/50 backdrop-blur sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-4 py-4">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 text-emerald-400">
              <Music className="w-8 h-8" />
              <h1 className="text-2xl font-bold">MusicSeerr</h1>
            </div>
            <span className="text-zinc-500 text-sm">Request music for your library</span>
          </div>
        </div>
      </header>

      <div className="max-w-4xl mx-auto px-4 py-8">
        {/* Search Box */}
        <div className="space-y-4">
          {/* Search Type Toggle */}
          <div className="flex gap-2">
            <button
              onClick={() => setSearchType('artist')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                searchType === 'artist'
                  ? 'bg-emerald-500 text-black'
                  : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700'
              }`}
            >
              <User className="w-4 h-4" />
              Artists
            </button>
            <button
              onClick={() => setSearchType('album')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                searchType === 'album'
                  ? 'bg-emerald-500 text-black'
                  : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700'
              }`}
            >
              <Disc3 className="w-4 h-4" />
              Albums
            </button>
          </div>

          {/* Search Input */}
          <div className="relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={`Search for ${searchType === 'artist' ? 'artists' : 'albums'}...`}
              className="w-full bg-zinc-800 border border-zinc-700 rounded-xl pl-12 pr-4 py-4 text-lg
                         placeholder:text-zinc-500 focus:outline-none focus:border-emerald-500
                         focus:ring-2 focus:ring-emerald-500/20"
            />
            {loading && (
              <Loader2 className="absolute right-4 top-1/2 -translate-y-1/2 w-5 h-5 text-emerald-400 animate-spin" />
            )}
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mt-4 p-4 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 flex items-center gap-2">
            <X className="w-5 h-5" />
            {error}
          </div>
        )}

        {/* Results */}
        <div className="mt-8 space-y-3">
          {searchType === 'artist' && results.artists?.map((artist) => (
            <div
              key={artist.id}
              className="flex items-center justify-between p-4 bg-zinc-800/50 border border-zinc-700/50 rounded-xl hover:bg-zinc-800 transition-colors"
            >
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 bg-zinc-700 rounded-full flex items-center justify-center">
                  <User className="w-6 h-6 text-zinc-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-lg">{artist.name}</h3>
                  <p className="text-sm text-zinc-500">
                    {[artist.type, artist.country, artist.disambiguation].filter(Boolean).join(' • ') || 'Artist'}
                  </p>
                </div>
              </div>
              
              <button
                onClick={() => addToLidarr(artist, 'artist')}
                disabled={adding === artist.id || isInLibrary(artist.id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
                  isInLibrary(artist.id)
                    ? 'bg-emerald-500/20 text-emerald-400 cursor-default'
                    : adding === artist.id
                    ? 'bg-zinc-700 text-zinc-400 cursor-wait'
                    : 'bg-emerald-500 text-black hover:bg-emerald-400'
                }`}
              >
                {isInLibrary(artist.id) ? (
                  <>
                    <Check className="w-4 h-4" />
                    In Library
                  </>
                ) : adding === artist.id ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Adding...
                  </>
                ) : (
                  <>
                    <Plus className="w-4 h-4" />
                    Add
                  </>
                )}
              </button>
            </div>
          ))}

          {searchType === 'album' && results['release-groups']?.map((album) => (
            <div
              key={album.id}
              className="flex items-center justify-between p-4 bg-zinc-800/50 border border-zinc-700/50 rounded-xl hover:bg-zinc-800 transition-colors"
            >
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 bg-zinc-700 rounded-lg flex items-center justify-center">
                  <Disc3 className="w-6 h-6 text-zinc-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-lg">{album.title}</h3>
                  <p className="text-sm text-zinc-500">
                    {album['artist-credit']?.[0]?.name}
                    {album['first-release-date'] && ` • ${album['first-release-date'].slice(0, 4)}`}
                    {album['primary-type'] && ` • ${album['primary-type']}`}
                  </p>
                </div>
              </div>
              
              <button
                onClick={() => addToLidarr(album, 'album')}
                disabled={adding === album.id || added.has(album.id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
                  added.has(album.id)
                    ? 'bg-emerald-500/20 text-emerald-400 cursor-default'
                    : adding === album.id
                    ? 'bg-zinc-700 text-zinc-400 cursor-wait'
                    : 'bg-emerald-500 text-black hover:bg-emerald-400'
                }`}
              >
                {added.has(album.id) ? (
                  <>
                    <Check className="w-4 h-4" />
                    Requested
                  </>
                ) : adding === album.id ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Adding...
                  </>
                ) : (
                  <>
                    <Plus className="w-4 h-4" />
                    Request
                  </>
                )}
              </button>
            </div>
          ))}

          {/* Empty States */}
          {query.length >= 2 && !loading && searchType === 'artist' && !results.artists?.length && (
            <div className="text-center py-12 text-zinc-500">
              No artists found for "{query}"
            </div>
          )}
          {query.length >= 2 && !loading && searchType === 'album' && !results['release-groups']?.length && (
            <div className="text-center py-12 text-zinc-500">
              No albums found for "{query}"
            </div>
          )}
          {query.length < 2 && (
            <div className="text-center py-12 text-zinc-500">
              Start typing to search MusicBrainz...
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
