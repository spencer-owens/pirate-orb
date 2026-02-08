import { NextRequest, NextResponse } from 'next/server';

const MB_API = 'https://musicbrainz.org/ws/2';
const USER_AGENT = 'MusicSeerr/1.0 (https://github.com/spencer-owens/pirate-orb)';

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const query = searchParams.get('q');
  const type = searchParams.get('type') || 'artist';

  if (!query || query.length < 2) {
    return NextResponse.json({ error: 'Query too short' }, { status: 400 });
  }

  try {
    let url: string;
    
    if (type === 'artist') {
      url = `${MB_API}/artist/?query=artist:${encodeURIComponent(query)}&fmt=json&limit=10`;
    } else {
      // Album (release-group) search
      url = `${MB_API}/release-group/?query=releasegroup:${encodeURIComponent(query)}&fmt=json&limit=10`;
    }

    const response = await fetch(url, {
      headers: {
        'User-Agent': USER_AGENT,
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`MusicBrainz API error: ${response.status}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Search error:', error);
    return NextResponse.json(
      { error: 'Failed to search MusicBrainz' },
      { status: 500 }
    );
  }
}
