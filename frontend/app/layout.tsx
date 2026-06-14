import type { Metadata } from 'next';
import { Inter, JetBrains_Mono } from 'next/font/google';
import { ThemeToggle } from '@/components/ThemeToggle';
import Link from 'next/link';
import './globals.css';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
  display: 'swap',
  weight: ['400', '500', '700'],
});

export const metadata: Metadata = {
  title: 'ParleyLab — AI Negotiation Simulator',
  description:
    'Practice high-stakes negotiations against an AI opponent powered by reinforcement learning and LLMs. Get real-time coaching feedback on every move.',
  keywords: ['negotiation', 'AI coach', 'practice', 'salary', 'RL', 'LLM'],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable}`}>
      <head>
        {/* Prevent flash of unstyled theme on first load */}
        <script
          dangerouslySetInnerHTML={{
            __html: `try{var t=localStorage.getItem('pl-theme');document.documentElement.setAttribute('data-theme',t==='light'?'light':'dark')}catch(e){}`,
          }}
        />
      </head>
      <body className="antialiased">
        {/* Global top bar — orange accent bar */}
        <nav className="topbar">
          <Link href="/" className="topbar-wordmark">
            ParleyLab
          </Link>
          <div className="topbar-actions">
            <Link
              href="/settings"
              className="topbar-icon-btn"
              aria-label="Settings"
            >
              ⚙
            </Link>
            <ThemeToggle />
          </div>
        </nav>
        {children}
      </body>
    </html>
  );
}
