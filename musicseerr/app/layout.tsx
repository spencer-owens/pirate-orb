import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'MusicSeerr',
  description: 'Request music for your library',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-zinc-950">{children}</body>
    </html>
  )
}
