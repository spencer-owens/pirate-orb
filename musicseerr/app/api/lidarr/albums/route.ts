import { NextResponse } from 'next/server';
import { lidarrFetch, LidarrAlbum } from '@/lib/lidarr';

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const albums: LidarrAlbum[] = await lidarrFetch('/api/v1/album');
    const mapped = albums.map(a => ({
      id: a.id,
      title: a.title,
      foreignAlbumId: a.foreignAlbumId,
      artistId: a.artistId,
      monitored: a.monitored,
      albumType: a.albumType,
      releaseDate: a.releaseDate,
      trackFileCount: a.statistics?.trackFileCount || 0,
      trackCount: a.statistics?.trackCount || 0,
      percentOfTracks: a.statistics?.percentOfTracks || 0,
    }));
    return NextResponse.json({ albums: mapped });
  } catch (e: any) {
    return NextResponse.json({ albums: [], error: e.message });
  }
}
