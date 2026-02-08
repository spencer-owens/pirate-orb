import { NextRequest, NextResponse } from 'next/server';
import { getReleaseGroup, getReleaseTracks } from '@/lib/musicbrainz';

export async function GET(_req: NextRequest, { params }: { params: { mbid: string } }) {
  try {
    const rg = await getReleaseGroup(params.mbid);

    // Pick the first official release to get tracks
    const releases = (rg.releases || []).sort((a: any, b: any) => {
      const da = a.date || '9999';
      const db = b.date || '9999';
      return da.localeCompare(db);
    });

    let tracks: any[] = [];
    if (releases.length > 0) {
      try {
        const release = await getReleaseTracks(releases[0].id);
        tracks = (release.media || []).flatMap((m: any) =>
          (m.tracks || []).map((t: any) => ({
            position: t.position,
            title: t.title,
            length: t.length,
            disc: m.position,
          }))
        );
      } catch {
        // tracks may not be available
      }
    }

    return NextResponse.json({
      id: rg.id,
      title: rg.title,
      primaryType: rg['primary-type'],
      secondaryTypes: rg['secondary-types'] || [],
      firstReleaseDate: rg['first-release-date'],
      artistCredit: rg['artist-credit'],
      releases: releases.slice(0, 10).map((r: any) => ({
        id: r.id,
        title: r.title,
        date: r.date,
        country: r.country,
        status: r.status,
        trackCount: r['track-count'],
      })),
      tracks,
    });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
