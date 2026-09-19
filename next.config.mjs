/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  experimental: {
    serverActions: {
      bodySizeLimit: "5mb", // formularios de carga de contratos con varios campos
    },
  },
};

export default nextConfig;
