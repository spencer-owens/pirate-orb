/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  images: {
    remotePatterns: [
      { hostname: 'coverartarchive.org' },
      { hostname: 'archive.org' },
      { hostname: 'images.lidarr.audio' },
    ],
  },
}

module.exports = nextConfig
