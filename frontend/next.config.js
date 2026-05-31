/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/v1/query/stream',
        destination: '/api/query',
      },
      {
        source: '/api/v1/:path*',
        destination: `${process.env.API_PROXY_TARGET || 'http://127.0.0.1:7860'}/api/v1/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
