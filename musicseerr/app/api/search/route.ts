import { NextRequest, NextResponse } from 'next/server';
import { searchArtists, searchReleaseGroups } from '@/lib/musicbrainz';

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const query = searchParams.get('q');
  const type = searchParams.get('type') || 'artist';

  if (!query || query.length < 2) {
    return NextResponse.json({ error: 'Query too short' }, { status: 400 });
  }

  try {
    const data = type === 'artist' ? await searchArtists(query) : await searchReleaseGroups(query);
    return NextResponse.json(data);
  } catch (error: any) {
    return NextResponse.json({ error: 'Failed to search MusicBrainz' }, { status: 500 });
  }
}
