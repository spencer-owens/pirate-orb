import { NextResponse } from 'next/server';

const LIDARR_URL = process.env.LIDARR_URL || 'http://localhost:8686';
const LIDARR_API_KEY = process.env.LIDARR_API_KEY || '';

export async function GET() {
  try {
    if (!LIDARR_API_KEY) {
      return NextResponse.json({ artists: [] });
    }

    const res = await fetch(`${LIDARR_URL}/api/v1/artist?apikey=${LIDARR_API_KEY}`);
    
    if (!res.ok) {
      throw new Error('Failed to fetch artists');
    }

    const artists = await res.json();
    
    // Return minimal data (just IDs for checking)
    const minimalArtists = artists.map((a: any) => ({
      foreignArtistId: a.foreignArtistId,
      artistName: a.artistName,
    }));

    return NextResponse.json({ artists: minimalArtists });
  } catch (error) {
    console.error('Lidarr artists error:', error);
    return NextResponse.json({ artists: [] });
  }
}
