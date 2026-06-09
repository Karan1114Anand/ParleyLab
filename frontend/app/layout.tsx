import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'ParleyLab — AI Negotiation Coach',
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
    <html lang="en" className={inter.variable}>
      <body className="antialiased">{children}</body>
    </html>
  );
}
