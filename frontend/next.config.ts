import path from "node:path";

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  turbopack: {
    // Pin the root to this app. Left unset, Turbopack infers one from the
    // nearest lockfile, which here resolved to the home directory — it then
    // warned on every boot and took 29s to start. Pinned, it starts in under a
    // second.
    root: path.resolve(import.meta.dirname),
  },
};

export default nextConfig;
