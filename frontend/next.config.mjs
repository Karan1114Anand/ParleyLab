/** @type {import('next').NextConfig} */
const nextConfig = {
  // Backend API URL — set NEXT_PUBLIC_API_URL in .env.local to override
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000',
  },
};

export default nextConfig;
