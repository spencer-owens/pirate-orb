import { NextRequest, NextResponse } from 'next/server';
import { lidarrFetch, getLidarrConfig, LidarrAlbum, LidarrArtist } from '@/lib/lidarr';

export async function POST(request: NextRequest) {
  try {
    const { albumMbid, artistMbid, artistName } = await request.json();
    if (!albumMbid || !artistMbid || !artistName) {
      return NextResponse.json({ error: 'Missing albumMbid, artistMbid, or artistName' }, { status: 400 });
    }

    // Check if artist exists in Lidarr
    const artists: LidarrArtist[] = await lidarrFetch('/api/v1/artist');
    let artist = artists.find(a => a.foreignArtistId === artistMbid);

    if (!artist) {
      // Add artist with all albums unmonitored
      const config = await getLidarrConfig();
      const payload = {
        foreignArtistId: artistMbid,
        artistName,
        path: `${config.rootPath}/${artistName.replace(/[/\\]/g, '-')}`,
        qualityProfileId: config.qualityProfileId,
        metadataProfileId: config.metadataProfileId,
        monitored: true,
        monitorNewItems: 'all',
        addOptions: { monitor: 'none', searchForMissingAlbums: false },
      };
      artist = await lidarrFetch('/api/v1/artist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      // Wait for Lidarr to populate albums
      await new Promise(r => setTimeout(r, 2000));
    }

    // Find the album in Lidarr by foreignAlbumId
    const albums: LidarrAlbum[] = await lidarrFetch(`/api/v1/album?artistId=${(artist as any).id}`);
    const album = albums.find(a => a.foreignAlbumId === albumMbid);

    if (!album) {
      return NextResponse.json({
        success: true,
        message: 'Artist added. Album may not be in Lidarr metadata profile — try a broader profile.',
        artistAdded: true,
      });
    }

    // Monitor the album
    if (!album.monitored) {
      await lidarrFetch(`/api/v1/album/${album.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...album, monitored: true }),
      });
    }

    // Trigger search for this album
    await lidarrFetch('/api/v1/command', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'AlbumSearch', albumIds: [album.id] }),
    });

    return NextResponse.json({ success: true, albumId: album.id, message: 'Album requested and search triggered' });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
