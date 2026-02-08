import { NextRequest, NextResponse } from 'next/server';
import { getArtist } from '@/lib/musicbrainz';

export async function GET(_req: NextRequest, { params }: { params: { mbid: string } }) {
  try {
    const data = await getArtist(params.mbid);
    // Sort release groups by date
    const releaseGroups = (data['release-groups'] || []).sort((a: any, b: any) => {
      const da = a['first-release-date'] || '9999';
      const db = b['first-release-date'] || '9999';
      return da.localeCompare(db);
    });
    return NextResponse.json({
      id: data.id,
      name: data.name,
      type: data.type,
      country: data.country,
      disambiguation: data.disambiguation,
      'life-span': data['life-span'],
      releaseGroups,
    });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
