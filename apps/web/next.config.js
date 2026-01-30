/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enable standalone output for Docker
  output: 'standalone',

  // Strict mode for React
  reactStrictMode: true,

  // Environment variables exposed to the browser
  env: {
    NEXT_PUBLIC_APP_NAME: 'TRJM',
    NEXT_PUBLIC_APP_VERSION: '1.0.0',
  },

  // Image optimization
  images: {
    domains: ['localhost'],
    formats: ['image/avif', 'image/webp'],
  },

  // Security headers
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'X-DNS-Prefetch-Control',
            value: 'on',
          },
          {
            key: 'X-Frame-Options',
            value: 'SAMEORIGIN',
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'Referrer-Policy',
            value: 'strict-origin-when-cross-origin',
          },
          {
            key: 'Permissions-Policy',
            value: 'camera=(), microphone=(), geolocation=()',
          },
        ],
      },
    ];
  },

  // Rewrites for API proxy (development)
  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    return {
      beforeFiles: [],
      afterFiles: [],
      fallback: [
        {
          source: '/api/:path*',
          destination: `${apiUrl}/:path*`,
        },
      ],
    };
  },

  // Webpack configuration
  webpack: (config, { isServer }) => {
    // Handle SVG imports
    config.module.rules.push({
      test: /\.svg$/,
      use: ['@svgr/webpack'],
    });

    return config;
  },

  // Experimental features
  experimental: {
    // Enable server actions
    serverActions: {
      bodySizeLimit: '2mb',
    },
  },

  // TypeScript configuration
  typescript: {
    // Allow production builds even with type errors (not recommended for production)
    ignoreBuildErrors: false,
  },

  // ESLint configuration
  eslint: {
    // Run ESLint during builds
    ignoreDuringBuilds: false,
  },

  // Logging
  logging: {
    fetches: {
      fullUrl: true,
    },
  },
};

module.exports = nextConfig;
