import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: '/py/:path*',
        destination: 'http://192.168.1.146:8000/:path*',
      },
    ]
  },
};

export default nextConfig;
