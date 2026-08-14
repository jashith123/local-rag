import type { NextConfig } from "next";

// Where the FastAPI backend is listening.
const BACKEND = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // Proxy /api/* through Next to the backend. The browser only ever talks to
  // localhost:3000, so every request is same-origin and FastAPI needs no CORS
  // middleware. /api/documents -> http://127.0.0.1:8000/documents
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND}/:path*`,
      },
    ];
  },
};

export default nextConfig;
