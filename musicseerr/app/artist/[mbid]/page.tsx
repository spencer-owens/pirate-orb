'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Check, Download, Eye, Disc3, Loader2 } from 'lucide-react';
import CoverArt from '@/app/components/CoverArt';
import { GridSkeleton } from '@/app/components/LoadingSkeleton';

interface ReleaseGroup {
  id: string;
  title: string;
  'primary-type'?: string;
  'secondary-types'?: string[];
  'first-release-date'?: string;
}

interface LidarrAlbumInfo {
  foreignAlbumId: string;
  monitored: boolean;
  trackFileCount: number;
  trackCount: number;
  percentOfTracks: number;
}

const typeOrder = ['Album', 'EP', 'Single', 'Live', 'Compilation', 'Remix', 'Other'];

function groupByType(rgs: ReleaseGroup[]) {
  const groups: Record<string, ReleaseGroup[]> = {};
  for (const rg of rgs) {
    const secondary = rg['secondary-types'] || [];
    let type = rg['primary-type'] || 'Other';
    if (secondary.includes('Compilation')) type = 'Compilation';
    else if (secondary.includes('Live')) type = 'Live';
    else if (secondary.includes('Remix')) type = 'Remix';
    if (!groups[type]) groups[type] = [];
    groups[type].push(rg);
  }
  return typeOrder.filter(t => groups[t]).map(t => ({ type: t, items: groups[t] }));
}

function StatusBadge({ album }: { album?: LidarrAlbumInfo }) {
  if (!album) return null;
  if (album.percentOfTracks >= 100) {
    return <span className="absolute top-2 right-2 bg-emerald-500 text-black text-xs font-bold px-2 py-0.5 rounded-full flex items-center gap-1"><Check className="w-3 h-3" />Have</span>;
  }
  if (album.trackFileCount > 0) {
    return <span className="absolute top-2 right-2 bg-yellow-500 text-black text-xs font-bold px-2 py-0.5 rounded-full flex items-center gap-1"><Download className="w-3 h-3" />{album.trackFileCount}/{album.trackCount}</span>;
  }
  if (album.monitored) {
    return <span className="absolute top-2 right-2 bg-blue-500 text-white text-xs font-bold px-2 py-0.5 rounded-full flex items-center gap-1"><Eye className="w-3 h-3" />Monitored</span>;
  }
  return null;
}

export default function ArtistPage() {
  const { mbid } = useParams<{ mbid: string }>();
  const [artist, setArtist] = useState<any>(null);
  const [lidarrAlbums, setLidarrAlbums] = useState<Map<string, LidarrAlbumInfo>>(new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!mbid) return;
    setLoading(true);
    Promise.all([
      fetch(`/api/artist/${mbid}`).then(r => r.json()),
      fetch('/api/lidarr/albums').then(r => r.json()),
    ]).then(([artistData, albumData]) => {
      if (artistData.error) { setError(artistData.error); return; }
      setArtist(artistData);
      const map = new Map<string, LidarrAlbumInfo>();
      for (const a of albumData.albums || []) map.set(a.foreignAlbumId, a);
      setLidarrAlbums(map);
    }).catch(e => setError(e.message)).finally(() => setLoading(false));
  }, [mbid]);

  if (loading) return <div className="space-y-6"><div className="h-8 w-48 bg-zinc-800 rounded animate-pulse" /><GridSkeleton count={8} /></div>;
  if (error) return <div className="text-red-400 p-8 text-center">{error}</div>;
  if (!artist) return null;

  const grouped = groupByType(artist.releaseGroups || []);

  return (
    <div className="space-y-8">
      {/* Artist header */}
      <div className="flex items-center gap-6">
        <Link href="/" className="text-zinc-400 hover:text-white"><ArrowLeft className="w-5 h-5" /></Link>
        <div>
          <h1 className="text-3xl font-bold">{artist.name}</h1>
          <p className="text-zinc-500 mt-1">
            {[artist.type, artist.country, artist.disambiguation].filter(Boolean).join(' · ')}
            {artist['life-span']?.begin && ` · ${artist['life-span'].begin.slice(0, 4)}–${artist['life-span'].ended ? artist['life-span'].end?.slice(0, 4) : 'present'}`}
          </p>
          <p className="text-zinc-500 text-sm mt-1">{artist.releaseGroups?.length || 0} releases</p>
        </div>
      </div>

      {/* Discography */}
      {grouped.map(({ type, items }) => (
        <section key={type}>
          <h2 className="text-xl font-semibold mb-4 text-zinc-300">{type}s <span className="text-zinc-600 text-base font-normal">({items.length})</span></h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
            {items.map(rg => {
              const lidarrInfo = lidarrAlbums.get(rg.id);
              return (
                <Link key={rg.id} href={`/album/${rg.id}`} className="group relative">
                  <div className="relative">
                    <CoverArt mbid={rg.id} alt={rg.title} size="xl" className="!w-full !h-auto aspect-square" />
                    <StatusBadge album={lidarrInfo} />
                  </div>
                  <h3 className="font-medium mt-2 truncate group-hover:text-emerald-400 transition-colors">{rg.title}</h3>
                  <p className="text-sm text-zinc-500">{rg['first-release-date']?.slice(0, 4) || 'Unknown'}</p>
                </Link>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
