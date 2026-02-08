'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Search, Disc3 } from 'lucide-react';
import CoverArt from '@/app/components/CoverArt';
import { GridSkeleton } from '@/app/components/LoadingSkeleton';

interface LibraryArtist {
  foreignArtistId: string;
  artistName: string;
  albumCount?: number;
  trackFileCount?: number;
}

export default function LibraryPage() {
  const [artists, setArtists] = useState<LibraryArtist[]>([]);
  const [albums, setAlbums] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');
  const [view, setView] = useState<'artists' | 'albums'>('artists');

  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetch('/api/lidarr/artists').then(r => r.json()),
      fetch('/api/lidarr/albums').then(r => r.json()),
    ]).then(([artistData, albumData]) => {
      setArtists(artistData.artists || []);
      setAlbums(albumData.albums || []);
    }).finally(() => setLoading(false));
  }, []);

  const filteredArtists = artists.filter(a => a.artistName.toLowerCase().includes(filter.toLowerCase()))
    .sort((a, b) => a.artistName.localeCompare(b.artistName));

  const albumsWithTracks = albums.filter(a => a.trackFileCount > 0);
  const filteredAlbums = albumsWithTracks.filter(a => a.title.toLowerCase().includes(filter.toLowerCase()))
    .sort((a, b) => (b.releaseDate || '').localeCompare(a.releaseDate || ''));

  // Build artist name lookup
  const artistMap = new Map(artists.map(a => [a.foreignArtistId, a.artistName]));
  // Build artist id → foreignArtistId from albums (albums have artistId)
  // We need to fetch artist list with IDs for this
  const [artistIdMap, setArtistIdMap] = useState<Map<number, string>>(new Map());
  useEffect(() => {
    fetch('/api/lidarr/artists-full').then(r => r.json()).then(data => {
      if (data.artists) {
        const m = new Map<number, string>();
        for (const a of data.artists) m.set(a.id, a.artistName);
        setArtistIdMap(m);
      }
    }).catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-bold">Library</h1>
        <div className="flex gap-2">
          {(['artists', 'albums'] as const).map(v => (
            <button key={v} onClick={() => setView(v)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                view === v ? 'bg-emerald-500/20 text-emerald-400' : 'text-zinc-400 hover:bg-zinc-800'
              }`}>{v === 'artists' ? `Artists (${artists.length})` : `Albums (${albumsWithTracks.length})`}</button>
          ))}
        </div>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
        <input type="text" value={filter} onChange={e => setFilter(e.target.value)} placeholder="Filter..."
          className="w-full bg-zinc-800 border border-zinc-700 rounded-lg pl-10 pr-4 py-2 text-sm placeholder:text-zinc-500 focus:outline-none focus:border-emerald-500" />
      </div>

      {loading ? <GridSkeleton count={12} /> : view === 'artists' ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {filteredArtists.map(a => (
            <Link key={a.foreignArtistId} href={`/artist/${a.foreignArtistId}`} className="group">
              <CoverArt mbid={a.foreignArtistId} alt={a.artistName} size="xl" type="artist" className="!w-full !h-auto aspect-square" />
              <h3 className="font-medium mt-2 truncate group-hover:text-emerald-400 transition-colors">{a.artistName}</h3>
            </Link>
          ))}
          {filteredArtists.length === 0 && <p className="col-span-full text-center text-zinc-500 py-8">No artists found</p>}
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {filteredAlbums.map(a => (
            <Link key={a.id} href={`/album/${a.foreignAlbumId}`} className="group">
              <div className="relative">
                <CoverArt mbid={a.foreignAlbumId} alt={a.title} size="xl" className="!w-full !h-auto aspect-square" />
                {a.percentOfTracks >= 100 && (
                  <span className="absolute top-2 right-2 bg-emerald-500 text-black text-xs font-bold px-1.5 py-0.5 rounded-full">✓</span>
                )}
              </div>
              <h3 className="font-medium mt-2 truncate group-hover:text-emerald-400 transition-colors">{a.title}</h3>
              <p className="text-sm text-zinc-500">{artistIdMap.get(a.artistId) || ''} · {a.releaseDate?.slice(0, 4) || ''}</p>
            </Link>
          ))}
          {filteredAlbums.length === 0 && <p className="col-span-full text-center text-zinc-500 py-8">No albums found</p>}
        </div>
      )}
    </div>
  );
}
