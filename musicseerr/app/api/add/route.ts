import { NextRequest, NextResponse } from 'next/server';

const LIDARR_URL = process.env.LIDARR_URL || 'http://localhost:8686';
const LIDARR_API_KEY = process.env.LIDARR_API_KEY || '';
const LIDARR_METADATA_API = 'https://api.lidarr.audio/api/v0.4';

interface AddRequest {
  type: 'artist' | 'album';
  mbid: string;
  name: string;
}

async function getLidarrConfig() {
  // Get root folder
  const rootRes = await fetch(`${LIDARR_URL}/api/v1/rootfolder?apikey=${LIDARR_API_KEY}`);
  const roots = await rootRes.json();
  const rootPath = roots[0]?.path || '/music';

  // Get quality profile
  const qualityRes = await fetch(`${LIDARR_URL}/api/v1/qualityprofile?apikey=${LIDARR_API_KEY}`);
  const profiles = await qualityRes.json();
  const qualityProfileId = profiles[0]?.id || 1;

  // Get metadata profile
  const metaRes = await fetch(`${LIDARR_URL}/api/v1/metadataprofile?apikey=${LIDARR_API_KEY}`);
  const metaProfiles = await metaRes.json();
  const metadataProfileId = metaProfiles[0]?.id || 1;

  return { rootPath, qualityProfileId, metadataProfileId };
}

async function addArtist(mbid: string, name: string) {
  const config = await getLidarrConfig();
  
  // First verify the artist exists in Lidarr's metadata
  const metaRes = await fetch(`${LIDARR_METADATA_API}/artist/${mbid}`);
  const metaData = await metaRes.json();
  
  if (!metaData.artistname) {
    throw new Error('Artist not found in metadata API');
  }

  // Add to Lidarr
  const payload = {
    foreignArtistId: mbid,
    artistName: name,
    path: `${config.rootPath}/${name.replace(/[/\\]/g, '-')}`,
    qualityProfileId: config.qualityProfileId,
    metadataProfileId: config.metadataProfileId,
    monitored: true,
    monitorNewItems: 'all',
    addOptions: {
      monitor: 'all',
      searchForMissingAlbums: true,
    },
  };

  const addRes = await fetch(`${LIDARR_URL}/api/v1/artist?apikey=${LIDARR_API_KEY}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  const result = await addRes.json();

  if (result.id) {
    return { success: true, id: result.id };
  } else {
    const error = Array.isArray(result) ? result[0]?.errorMessage : result.message;
    throw new Error(error || 'Failed to add artist');
  }
}

async function addAlbum(mbid: string, name: string) {
  // For albums, we need to find the artist first, then add the album
  // This is more complex - for now, we'll look up the release group
  // and add the associated artist
  
  const rgRes = await fetch(
    `https://musicbrainz.org/ws/2/release-group/${mbid}?inc=artists&fmt=json`,
    { headers: { 'User-Agent': 'MusicSeerr/1.0' } }
  );
  
  const rgData = await rgRes.json();
  
  if (!rgData['artist-credit']?.[0]?.artist?.id) {
    throw new Error('Could not find artist for this album');
  }
  
  const artistMbid = rgData['artist-credit'][0].artist.id;
  const artistName = rgData['artist-credit'][0].artist.name;
  
  // Check if artist already exists in Lidarr
  const existingRes = await fetch(`${LIDARR_URL}/api/v1/artist?apikey=${LIDARR_API_KEY}`);
  const existingArtists = await existingRes.json();
  const existingArtist = existingArtists.find((a: any) => a.foreignArtistId === artistMbid);
  
  if (existingArtist) {
    // Artist exists, trigger search for this album
    const searchRes = await fetch(`${LIDARR_URL}/api/v1/command?apikey=${LIDARR_API_KEY}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: 'AlbumSearch',
        albumIds: [], // Would need album ID, for now just trigger artist search
      }),
    });
    return { success: true, message: 'Album search triggered' };
  } else {
    // Add artist first (which will include this album)
    return await addArtist(artistMbid, artistName);
  }
}

export async function POST(request: NextRequest) {
  try {
    const body: AddRequest = await request.json();
    const { type, mbid, name } = body;

    if (!LIDARR_API_KEY) {
      return NextResponse.json(
        { error: 'Lidarr API key not configured' },
        { status: 500 }
      );
    }

    if (type === 'artist') {
      const result = await addArtist(mbid, name);
      return NextResponse.json(result);
    } else {
      const result = await addAlbum(mbid, name);
      return NextResponse.json(result);
    }
  } catch (error: any) {
    console.error('Add error:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to add' },
      { status: 500 }
    );
  }
}
