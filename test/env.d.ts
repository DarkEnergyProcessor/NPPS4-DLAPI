declare module "cloudflare:test" {
  interface ProvidedEnv {
    ARCHIVE_BUCKET: R2Bucket;
    PUBLIC: string;
    SHARED_KEY?: string;
    API_ACCESS?: string;
  }
}
