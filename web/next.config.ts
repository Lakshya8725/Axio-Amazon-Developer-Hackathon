import path from "path";
import { fileURLToPath } from "url";
import type { NextConfig } from "next";

const proxyTarget = process.env.API_PROXY_TARGET || "http://127.0.0.1:8000";
const configDir = path.dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  reactStrictMode: true,
  outputFileTracingRoot: configDir,
  async rewrites() {
    return [
      {
        source: "/axio-api/:path*",
        destination: `${proxyTarget}/:path*`,
      },
    ];
  },
};

export default nextConfig;
