import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  experimental: {
    reactCompiler: false,
  },
  eslint: {
    ignoreDuringBuilds: false,
  },
  typescript: {
    ignoreBuildErrors: false,
  },
  // Явно указываем корень для output file tracing — убирает warning о множественных lockfile
  outputFileTracingRoot: path.join(process.cwd(), ".."),
};

export default nextConfig;
