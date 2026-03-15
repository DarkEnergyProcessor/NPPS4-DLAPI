import { describe, it, expect, beforeAll } from "vitest";
import { env, SELF, createExecutionContext, waitOnExecutionContext } from "cloudflare:test";
import { seedBucket } from "./fixtures";
import worker from "../src/index";

const BASE = "http://localhost";

beforeAll(async () => {
  await seedBucket(env.ARCHIVE_BUCKET);
});

describe("Access control with shared key", () => {
  // Test directly using the worker export with a modified env
  // to simulate SHARED_KEY being set.

  function envWithKey(sharedKey: string, apiAccess?: string): typeof env {
    return {
      ...env,
      SHARED_KEY: sharedKey,
      PUBLIC: "false",
      ...(apiAccess ? { API_ACCESS: apiAccess } : {}),
    };
  }

  it("denies access when shared key is required but not provided", async () => {
    const testEnv = envWithKey("my-secret-key");
    const ctx = createExecutionContext();
    const res = await worker.fetch(new Request(`${BASE}/api/publicinfo`), testEnv, ctx);
    await waitOnExecutionContext(ctx);

    expect(res.status).toBe(404);
  });

  it("allows access with correct shared key", async () => {
    const testEnv = envWithKey("my-secret-key");
    const ctx = createExecutionContext();
    const res = await worker.fetch(
      new Request(`${BASE}/api/publicinfo`, {
        headers: { "DLAPI-Shared-Key": "my-secret-key" },
      }),
      testEnv,
      ctx
    );
    await waitOnExecutionContext(ctx);

    expect(res.status).toBe(200);
  });

  it("denies access with incorrect shared key", async () => {
    const testEnv = envWithKey("my-secret-key");
    const ctx = createExecutionContext();
    const res = await worker.fetch(
      new Request(`${BASE}/api/publicinfo`, {
        headers: { "DLAPI-Shared-Key": "wrong-key" },
      }),
      testEnv,
      ctx
    );
    await waitOnExecutionContext(ctx);

    expect(res.status).toBe(404);
  });

  it("allows access to public endpoint even without key", async () => {
    const testEnv = envWithKey("my-secret-key", JSON.stringify({ publicinfo: { public: true } }));
    const ctx = createExecutionContext();
    const res = await worker.fetch(new Request(`${BASE}/api/publicinfo`), testEnv, ctx);
    await waitOnExecutionContext(ctx);

    expect(res.status).toBe(200);
  });

  it("per-endpoint access control works for nested paths", async () => {
    const apiAccess = JSON.stringify({
      v1: {
        release_info: { public: true },
        getdb: { public: false },
      },
    });
    const testEnv = envWithKey("my-secret-key", apiAccess);

    // release_info is public
    const ctx1 = createExecutionContext();
    const res1 = await worker.fetch(new Request(`${BASE}/api/v1/release_info`), testEnv, ctx1);
    await waitOnExecutionContext(ctx1);
    expect(res1.status).toBe(200);

    // getdb is not public, and no key provided
    const ctx2 = createExecutionContext();
    const res2 = await worker.fetch(new Request(`${BASE}/api/v1/getdb/testdb`), testEnv, ctx2);
    await waitOnExecutionContext(ctx2);
    expect(res2.status).toBe(404);

    // getdb with correct key
    const ctx3 = createExecutionContext();
    const res3 = await worker.fetch(
      new Request(`${BASE}/api/v1/getdb/testdb`, {
        headers: { "DLAPI-Shared-Key": "my-secret-key" },
      }),
      testEnv,
      ctx3
    );
    await waitOnExecutionContext(ctx3);
    expect(res3.status).toBe(200);
  });

  it("allows all access when no shared key is configured", async () => {
    // Default env has no SHARED_KEY
    const ctx = createExecutionContext();
    const res = await worker.fetch(new Request(`${BASE}/api/publicinfo`), env, ctx);
    await waitOnExecutionContext(ctx);

    expect(res.status).toBe(200);
  });
});
