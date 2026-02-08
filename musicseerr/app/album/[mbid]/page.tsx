'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Plus, Check, Loader2, Download, Eye, Clock } from 'lucide-react';
import CoverArt from '@/app/components/CoverArt';

function formatDuration(ms?: number) {
  if (!ms) return '';
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

export default function AlbumPage() {
  const { mbid } = useParams<{ mbid: string }>();
  const [album, setAlbum] = useState<any>(null);
  const [lidarrStatus, setLidarrStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [requesting, setRequesting] = useState(false);
  const [requestResult, setRequestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!mbid) return;
    setLoading(true);
    Promise.all([
      fetch(`/api/album/${mbid}`).then(r => r.json()),
      fetch('/api/lidarr/albums').then(r => r.json()),
    ]).then(([albumData, lidarrData]) => {
      if (albumData.error) { setError(albumData.error); return; }
      setAlbum(albumData);
      const match = (lidarrData.albums || []).find((a: any) => a.foreignAlbumId === mbid);
      if (match) setLidarrStatus(match);
    }).catch(e => setError(e.message)).finally(() => setLoading(false));
  }, [mbid]);

  const requestAlbum = async () => {
    if (!album) return;
    setRequesting(true);
    setRequestResult(null);
    try {
      const artistMbid = album.artistCredit?.[0]?.artist?.id;
      const artistName = album.artistCredit?.[0]?.artist?.name || album.artistCredit?.[0]?.name;
      const res = await fetch('/api/lidarr/add-album', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ albumMbid: mbid, artistMbid, artistName }),
      });
      const data = await res.json();
      setRequestResult({ success: !!data.success, message: data.message || data.error || 'Done' });
      if (data.success) setLidarrStatus({ monitored: true, trackFileCount: 0, trackCount: 0 });
    } catch { setRequestResult({ success: false, message: 'Request failed' }); }
    setRequesting(false);
  };

  if (loading) return (
    <div className="animate-pulse space-y-6">
      <div className="flex gap-6"><div className="w-48 h-48 bg-zinc-800 rounded-lg" /><div className="space-y-3 flex-1"><div className="h-8 bg-zinc-800 rounded w-1/3" /><div className="h-4 bg-zinc-800 rounded w-1/4" /></div></div>
      <div className="space-y-2">{Array.from({length:8}).map((_,i) => <div key={i} className="h-10 bg-zinc-800 rounded" />)}</div>
    </div>
  );
  if (error) return <div className="text-red-400 p-8 text-center">{error}</div>;
  if (!album) return null;

  const artist = album.artistCredit?.[0];
  const hasIt = lidarrStatus?.percentOfTracks >= 100;
  const partial = lidarrStatus && lidarrStatus.trackFileCount > 0 && !hasIt;
  const monitored = lidarrStatus?.monitored && !hasIt && !partial;

  return (
    <div className="space-y-8">
      <Link href={artist?.artist?.id ? `/artist/${artist.artist.id}` : '/'} className="text-zinc-400 hover:text-white inline-flex items-center gap-2">
        <ArrowLeft className="w-4 h-4" /> {artist?.artist?.name || 'Back'}
      </Link>

      {/* Album header */}
      <div className="flex flex-col sm:flex-row gap-6">
        <CoverArt mbid={album.id} alt={album.title} size="xl" />
        <div className="flex-1">
          <h1 className="text-3xl font-bold">{album.title}</h1>
          {artist && (
            <Link href={`/artist/${artist.artist?.id}`} className="text-emerald-400 hover:text-emerald-300 text-lg">
              {artist.artist?.name || artist.name}
            </Link>
          )}
          <div className="flex flex-wrap gap-3 mt-3 text-sm text-zinc-500">
            {album.firstReleaseDate && <span>{album.firstReleaseDate.slice(0, 4)}</span>}
            {album.primaryType && <span className="bg-zinc-800 px-2 py-0.5 rounded">{album.primaryType}</span>}
            {album.secondaryTypes?.map((t: string) => (
              <span key={t} className="bg-zinc-800 px-2 py-0.5 rounded">{t}</span>
            ))}
            {album.tracks?.length > 0 && <span>{album.tracks.length} tracks</span>}
          </div>

          {/* Status / Request */}
          <div className="mt-6">
            {hasIt ? (
              <div className="inline-flex items-center gap-2 bg-emerald-500/20 text-emerald-400 px-4 py-2 rounded-lg font-medium">
                <Check className="w-5 h-5" /> In your library
              </div>
            ) : partial ? (
              <div className="flex items-center gap-3">
                <span className="inline-flex items-center gap-2 bg-yellow-500/20 text-yellow-400 px-3 py-2 rounded-lg text-sm">
                  <Download className="w-4 h-4" /> {lidarrStatus.trackFileCount}/{lidarrStatus.trackCount} tracks
                </span>
                <button onClick={requestAlbum} disabled={requesting}
                  className="bg-emerald-500 text-black px-4 py-2 rounded-lg font-medium hover:bg-emerald-400 disabled:opacity-50 flex items-center gap-2">
                  {requesting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />} Search Missing
                </button>
              </div>
            ) : monitored ? (
              <div className="inline-flex items-center gap-2 bg-blue-500/20 text-blue-400 px-4 py-2 rounded-lg font-medium">
                <Eye className="w-5 h-5" /> Monitored — waiting for download
              </div>
            ) : (
              <button onClick={requestAlbum} disabled={requesting}
                className="bg-emerald-500 text-black px-6 py-3 rounded-lg font-semibold hover:bg-emerald-400 disabled:opacity-50 flex items-center gap-2 text-lg">
                {requesting ? <><Loader2 className="w-5 h-5 animate-spin" /> Requesting...</> : <><Plus className="w-5 h-5" /> Request Album</>}
              </button>
            )}
            {requestResult && (
              <p className={`mt-3 text-sm ${requestResult.success ? 'text-emerald-400' : 'text-red-400'}`}>
                {requestResult.message}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Track listing */}
      {album.tracks?.length > 0 && (
        <section>
          <h2 className="text-xl font-semibold mb-4">Tracklist</h2>
          <div className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl overflow-hidden">
            {album.tracks.map((t: any, i: number) => (
              <div key={i} className={`flex items-center px-4 py-3 ${i > 0 ? 'border-t border-zinc-700/30' : ''} hover:bg-zinc-800/80`}>
                <span className="w-8 text-zinc-500 text-sm text-right mr-4">{t.position}</span>
                <span className="flex-1 truncate">{t.title}</span>
                <span className="text-zinc-500 text-sm ml-4">{formatDuration(t.length)}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Releases */}
      {album.releases?.length > 0 && (
        <section>
          <h2 className="text-xl font-semibold mb-4">Releases</h2>
          <div className="space-y-2">
            {album.releases.map((r: any) => (
              <div key={r.id} className="flex items-center gap-4 p-3 bg-zinc-800/30 rounded-lg text-sm">
                <span className="text-zinc-400">{r.country || '??'}</span>
                <span className="flex-1">{r.title}</span>
                <span className="text-zinc-500">{r.date || 'Unknown'}</span>
                <span className="text-zinc-600">{r.status}</span>
                {r.trackCount && <span className="text-zinc-600">{r.trackCount} tracks</span>}
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
