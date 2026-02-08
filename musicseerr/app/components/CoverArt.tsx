'use client';

import { useState } from 'react';
import { Disc3 } from 'lucide-react';

interface CoverArtProps {
  mbid: string;
  alt: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
  type?: 'artist' | 'album';
}

const sizeMap = {
  sm: 'w-12 h-12',
  md: 'w-20 h-20',
  lg: 'w-32 h-32',
  xl: 'w-48 h-48',
};

const iconSize = {
  sm: 'w-6 h-6',
  md: 'w-8 h-8',
  lg: 'w-12 h-12',
  xl: 'w-16 h-16',
};

export default function CoverArt({ mbid, alt, size = 'md', className = '', type = 'album' }: CoverArtProps) {
  const [error, setError] = useState(false);
  const sizeClass = sizeMap[size];
  const rounded = type === 'artist' ? 'rounded-full' : 'rounded-lg';

  if (error || !mbid) {
    return (
      <div className={`${sizeClass} ${rounded} bg-zinc-800 flex items-center justify-center flex-shrink-0 ${className}`}>
        <Disc3 className={`${iconSize[size]} text-zinc-600`} />
      </div>
    );
  }

  return (
    <div className={`${sizeClass} ${rounded} overflow-hidden flex-shrink-0 bg-zinc-800 ${className}`}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={`https://coverartarchive.org/release-group/${mbid}/front-250`}
        alt={alt}
        className={`${sizeClass} object-cover`}
        onError={() => setError(true)}
        loading="lazy"
      />
    </div>
  );
}
