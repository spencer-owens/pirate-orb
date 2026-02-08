const MB_API = 'https://musicbrainz.org/ws/2';
const USER_AGENT = 'MusicSeerr/2.0 (https://github.com/spencer-owens/pirate-orb)';

// Simple rate limiter: 1 request per second
let lastRequest = 0;

async function rateLimitedFetch(url: string): Promise<Response> {
  const now = Date.now();
  const wait = Math.max(0, 1100 - (now - lastRequest));
  if (wait > 0) await new Promise(r => setTimeout(r, wait));
  lastRequest = Date.now();
  
  const res = await fetch(url, {
    headers: { 'User-Agent': USER_AGENT, 'Accept': 'application/json' },
  });
  
  if (res.status === 503) {
    // Rate limited, wait and retry once
    await new Promise(r => setTimeout(r, 2000));
    lastRequest = Date.now();
    return fetch(url, {
      headers: { 'User-Agent': USER_AGENT, 'Accept': 'application/json' },
    });
  }
  
  return res;
}

export async function searchArtists(query: string, limit = 10) {
  const res = await rateLimitedFetch(
    `${MB_API}/artist/?query=artist:${encodeURIComponent(query)}&fmt=json&limit=${limit}`
  );
  return res.json();
}

export async function searchReleaseGroups(query: string, limit = 10) {
  const res = await rateLimitedFetch(
    `${MB_API}/release-group/?query=releasegroup:${encodeURIComponent(query)}&fmt=json&limit=${limit}`
  );
  return res.json();
}

export async function getArtist(mbid: string) {
  const res = await rateLimitedFetch(
    `${MB_API}/artist/${mbid}?inc=release-groups&fmt=json`
  );
  if (!res.ok) throw new Error(`Artist not found: ${res.status}`);
  return res.json();
}

export async function getReleaseGroup(mbid: string) {
  const res = await rateLimitedFetch(
    `${MB_API}/release-group/${mbid}?inc=releases+artists&fmt=json`
  );
  if (!res.ok) throw new Error(`Release group not found: ${res.status}`);
  return res.json();
}

export async function getReleaseTracks(releaseMbid: string) {
  const res = await rateLimitedFetch(
    `${MB_API}/release/${releaseMbid}?inc=recordings+artist-credits&fmt=json`
  );
  if (!res.ok) throw new Error(`Release not found: ${res.status}`);
  return res.json();
}
