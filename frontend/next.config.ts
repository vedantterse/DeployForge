import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The repo's own CLAUDE.md / SCHEMA.md / PROJECT_STRUCTURE.md are the
  // source of truth; don't let Next regenerate template agent docs here.
  agentRules: false,
};

export default nextConfig;
