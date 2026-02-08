import { NextResponse } from 'next/server';
import { lidarrFetch } from '@/lib/lidarr';

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const data = await lidarrFetch('/api/v1/queue?includeArtist=true&includeAlbum=true');
    const records = (data.records || []).map((r: any) => ({
      id: r.id,
      title: r.title,
      status: r.status,
      trackedDownloadStatus: r.trackedDownloadStatus,
      trackedDownloadState: r.trackedDownloadState,
      size: r.size,
      sizeleft: r.sizeleft,
      timeleft: r.timeleft,
      artistName: r.artist?.artistName,
      albumTitle: r.album?.title,
    }));
    return NextResponse.json({ queue: records, totalRecords: data.totalRecords || 0 });
  } catch (e: any) {
    return NextResponse.json({ queue: [], totalRecords: 0, error: e.message });
  }
}
