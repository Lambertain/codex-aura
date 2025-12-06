import type { Metadata } from 'next'
import { Geist, Geist_Mono } from 'next/font/google'
import './globals.css'

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
})

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
})

export const metadata: Metadata = {
  title: 'Codex Aura Dashboard',
  description: 'Repository analysis dashboard',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <header className="flex justify-end items-center p-4 gap-4 h-16">
          <button className="bg-blue-600 text-white rounded px-4 py-2">Sign In</button>
          <button className="bg-purple-600 text-white rounded px-4 py-2">Sign Up</button>
        </header>
        {children}
      </body>
    </html>
  )
}
