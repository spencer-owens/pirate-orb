'use client';

import { useEffect, useState } from 'react';
import { RefreshCw, Download, Clock, AlertCircle, CheckCircle } from 'lucide-react';

function formatBytes(bytes: number) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

function ProgressBar({ size, sizeleft }: { size: number; sizeleft: number }) {
  const pct = size > 0 ? ((size - sizeleft) / size) * 100 : 0;
  return (
    <div className="w-full bg-zinc-700 rounded-full h-2">
      <div className="bg-emerald-500 h-2 rounded-full transition-all" style={{ width: `${pct}%` }} />
    </div>
  );
}

export default function RequestsPage() {
  const [queue, setQueue] = useState<any[]>([]);
  const [missing, setMissing] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = async () => {
    try {
      const [queueData, albumsData] = await Promise.all([
        fetch('/api/lidarr/queue').then(r => r.json()),
        fetch('/api/lidarr/albums').then(r => r.json()),
      ]);
      setQueue(queueData.queue || []);
      // Missing = monitored but no tracks
      const miss = (albumsData.albums || []).filter((a: any) => a.monitored && a.trackFileCount === 0 && a.trackCount > 0);
      setMissing(miss);
    } catch {}
  };

  useEffect(() => {
    setLoading(true);
    fetchData().finally(() => setLoading(false));
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  const refresh = async () => {
    setRefreshing(true);
    await fetchData();
    setRefreshing(false);
  };

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Requests & Queue</h1>
        <button onClick={refresh} disabled={refreshing}
          className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm bg-zinc-800 text-zinc-400 hover:bg-zinc-700 disabled:opacity-50">
          <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} /> Refresh
        </button>
      </div>

      {/* Active Downloads */}
      <section>
        <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
          <Download className="w-5 h-5 text-emerald-400" /> Active Downloads
          <span className="text-zinc-500 text-sm font-normal">({queue.length})</span>
        </h2>
        {loading ? (
          <div className="space-y-2">{Array.from({length: 3}).map((_, i) => <div key={i} className="h-16 bg-zinc-800 rounded-lg animate-pulse" />)}</div>
        ) : queue.length === 0 ? (
          <p className="text-zinc-500 py-6 text-center bg-zinc-800/30 rounded-lg">No active downloads</p>
        ) : (
          <div className="space-y-2">
            {queue.map(item => (
              <div key={item.id} className="p-4 bg-zinc-800/50 border border-zinc-700/50 rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <span className="font-medium">{item.albumTitle || item.title}</span>
                    {item.artistName && <span className="text-zinc-500 ml-2">— {item.artistName}</span>}
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    {item.trackedDownloadState === 'importPending' ? (
                      <span className="text-yellow-400 flex items-center gap-1"><CheckCircle className="w-4 h-4" /> Import Pending</span>
                    ) : item.status === 'downloading' ? (
                      <span className="text-emerald-400 flex items-center gap-1"><Download className="w-4 h-4" /> Downloading</span>
                    ) : (
                      <span className="text-zinc-400">{item.status}</span>
                    )}
                  </div>
                </div>
                <ProgressBar size={item.size} sizeleft={item.sizeleft} />
                <div className="flex justify-between mt-1 text-xs text-zinc-500">
                  <span>{formatBytes(item.size - item.sizeleft)} / {formatBytes(item.size)}</span>
                  {item.timeleft && <span>{item.timeleft} remaining</span>}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Missing / Wanted */}
      <section>
        <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
          <Clock className="w-5 h-5 text-yellow-400" /> Wanted — Missing
          <span className="text-zinc-500 text-sm font-normal">({missing.length})</span>
        </h2>
        {loading ? (
          <div className="space-y-2">{Array.from({length: 3}).map((_, i) => <div key={i} className="h-12 bg-zinc-800 rounded-lg animate-pulse" />)}</div>
        ) : missing.length === 0 ? (
          <p className="text-zinc-500 py-6 text-center bg-zinc-800/30 rounded-lg">All monitored albums have been downloaded</p>
        ) : (
          <div className="space-y-2">
            {missing.map(album => (
              <div key={album.id} className="flex items-center gap-4 p-3 bg-zinc-800/30 border border-zinc-700/30 rounded-lg">
                <AlertCircle className="w-5 h-5 text-yellow-400 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <span className="font-medium truncate block">{album.title}</span>
                  <span className="text-sm text-zinc-500">{album.releaseDate?.slice(0, 4) || 'Unknown'} · {album.albumType}</span>
                </div>
                <span className="text-xs text-zinc-600">{album.trackCount} tracks</span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
