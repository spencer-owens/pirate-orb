const LIDARR_URL = process.env.LIDARR_URL || 'http://localhost:8686';
const LIDARR_API_KEY = process.env.LIDARR_API_KEY || '';

export async function lidarrFetch(path: string, options?: RequestInit) {
  const separator = path.includes('?') ? '&' : '?';
  const url = `${LIDARR_URL}${path}${separator}apikey=${LIDARR_API_KEY}`;
  const res = await fetch(url, { ...options, next: { revalidate: 0 } });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Lidarr ${res.status}: ${text}`);
  }
  return res.json();
}

export async function getLidarrConfig() {
  const [roots, profiles, metaProfiles] = await Promise.all([
    lidarrFetch('/api/v1/rootfolder'),
    lidarrFetch('/api/v1/qualityprofile'),
    lidarrFetch('/api/v1/metadataprofile'),
  ]);
  return {
    rootPath: roots[0]?.path || '/music',
    qualityProfileId: profiles[0]?.id || 1,
    metadataProfileId: metaProfiles[0]?.id || 1,
  };
}

export interface LidarrArtist {
  id: number;
  artistName: string;
  foreignArtistId: string;
  monitored: boolean;
  statistics?: { albumCount: number; trackFileCount: number; trackCount: number; percentOfTracks: number };
}

export interface LidarrAlbum {
  id: number;
  title: string;
  foreignAlbumId: string;
  artistId: number;
  monitored: boolean;
  albumType: string;
  releaseDate?: string;
  statistics?: { trackFileCount: number; trackCount: number; percentOfTracks: number };
  artist?: { artistName: string; foreignArtistId: string };
}

export interface LidarrQueueItem {
  id: number;
  title: string;
  status: string;
  trackedDownloadStatus?: string;
  trackedDownloadState?: string;
  size: number;
  sizeleft: number;
  timeleft?: string;
  estimatedCompletionTime?: string;
  artist?: { artistName: string };
  album?: { title: string };
}
