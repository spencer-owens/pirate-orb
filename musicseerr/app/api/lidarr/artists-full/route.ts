import { NextResponse } from 'next/server';
import { lidarrFetch } from '@/lib/lidarr';

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const artists = await lidarrFetch('/api/v1/artist');
    const mapped = artists.map((a: any) => ({
      id: a.id,
      foreignArtistId: a.foreignArtistId,
      artistName: a.artistName,
      monitored: a.monitored,
      albumCount: a.statistics?.albumCount || 0,
      trackFileCount: a.statistics?.trackFileCount || 0,
      trackCount: a.statistics?.trackCount || 0,
    }));
    return NextResponse.json({ artists: mapped });
  } catch (e: any) {
    return NextResponse.json({ artists: [], error: e.message });
  }
}
