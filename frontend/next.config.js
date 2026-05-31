/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/v1/query/stream',
        destination: '/api/query',
      },
    ];
  },
};

module.exports = nextConfig;
