import createNextIntlPlugin from 'next-intl/plugin';

const withNextIntl = createNextIntlPlugin(
  './src/i18n.ts' // Path to the configuration file
);

/** @type {import('next').NextConfig} */
const nextConfig = {
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },

  // Required for @ricky0123/vad-react (onnxruntime-web uses SharedArrayBuffer)
  transpilePackages: ['@ricky0123/vad-react', '@ricky0123/vad-web'],

  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          { key: 'Cross-Origin-Opener-Policy',   value: 'same-origin' },
          { key: 'Cross-Origin-Embedder-Policy',  value: 'require-corp' },
        ],
      },
    ];
  },

  webpack(config, { isServer }) {
    if (!isServer) {
      // onnxruntime-node is server-only; exclude from client bundle
      config.resolve.fallback = { ...config.resolve.fallback, fs: false };
    }
    // Allow .wasm and .onnx as static assets
    config.module.rules.push({
      test: /\.(wasm|onnx)$/,
      type: 'asset/resource',
    });
    return config;
  },
};

export default withNextIntl(nextConfig);

