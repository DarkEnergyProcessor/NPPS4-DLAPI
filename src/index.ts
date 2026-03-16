// Copyright (c) 2023 Dark Energy Processor
//
// This software is provided 'as-is', without any express or implied
// warranty. In no event will the authors be held liable for any damages
// arising from the use of this software.
//
// Permission is granted to anyone to use this software for any purpose,
// including commercial applications, and to alter it and redistribute it
// freely, subject to the following restrictions:
//
// 1. The origin of this software must not be misrepresented; you must not
//    claim that you wrote the original software. If you use this software
//    in a product, an acknowledgment in the product documentation would be
//    appreciated but is not required.
// 2. Altered source versions must be plainly marked as such, and must not be
//    misrepresented as being the original software.
// 3. This notice may not be removed or altered from any source distribution.

import type {
  Env,
  PublicInfoModel,
  UpdateRequestBody,
  BatchDownloadRequestBody,
  DownloadRequestBody,
  MicroDownloadRequestBody,
} from "./types";
import { isAccessible, isPublicAccessible } from "./config";
import {
  getLatestVersion,
  getReleaseInfo,
  getUpdateFile,
  getBatchList,
  getSinglePackage,
  getDatabaseFile,
  getMicroDlFile,
} from "./file";
import { runSync, getSyncStatus } from "./sync";
import { renderDashboard, renderDashboardJson } from "./dashboard";

const DLAPI_MAJOR_VERSION = 1;
const DLAPI_MINOR_VERSION = 1;
const NPPS4_DLAPI_PROGRAM_VERSION = "2023.05.14";

function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function notFound(detail = "Not found."): Response {
  return jsonResponse({ detail }, 404);
}

/**
 * Build the base URL for archive file links.
 * Files are served directly from R2 via the /archive/ path prefix.
 */
function archiveBaseUrl(request: Request): string {
  const url = new URL(request.url);
  return `${url.origin}/archive`;
}

/**
 * Check access control. Returns a 404 Response if denied, or null if allowed.
 */
function checkAccess(env: Env, request: Request, endpoint: string): Response | null {
  const sharedKey = request.headers.get("DLAPI-Shared-Key");
  if (!isAccessible(env, endpoint, sharedKey)) {
    return notFound();
  }
  return null;
}

async function parseJsonBody<T>(request: Request): Promise<T> {
  return request.json<T>();
}

// ─── Route handlers ───

async function handlePublicInfo(request: Request, env: Env): Promise<Response> {
  const denied = checkAccess(env, request, "/api/publicinfo");
  if (denied) return denied;

  const latest = await getLatestVersion(env.ARCHIVE_BUCKET);
  const info: PublicInfoModel = {
    publicApi: isPublicAccessible(env),
    dlapiVersion: { major: DLAPI_MAJOR_VERSION, minor: DLAPI_MINOR_VERSION },
    serveTimeLimit: 0,
    gameVersion: `${latest[0]}.${latest[1]}`,
    application: {
      NPPS4DLAPIVersion: NPPS4_DLAPI_PROGRAM_VERSION,
      runtime: "cloudflare-workers",
    },
  };
  return jsonResponse(info);
}

async function handleUpdate(request: Request, env: Env): Promise<Response> {
  const denied = checkAccess(env, request, "/api/v1/update");
  if (denied) return denied;

  const body = await parseJsonBody<UpdateRequestBody>(request);
  const baseUrl = archiveBaseUrl(request);
  const downloads = await getUpdateFile(env, baseUrl, body.version, body.platform);
  return jsonResponse(downloads);
}

async function handleBatch(request: Request, env: Env): Promise<Response> {
  const denied = checkAccess(env, request, "/api/v1/batch");
  if (denied) return denied;

  const body = await parseJsonBody<BatchDownloadRequestBody>(request);
  const baseUrl = archiveBaseUrl(request);
  const downloads = await getBatchList(env, baseUrl, body.package_type, body.platform, body.exclude ?? []);

  if (downloads === null) {
    return jsonResponse({ detail: "Package type not found" }, 404);
  }
  return jsonResponse(downloads);
}

async function handleDownload(request: Request, env: Env): Promise<Response> {
  const denied = checkAccess(env, request, "/api/v1/download");
  if (denied) return denied;

  const body = await parseJsonBody<DownloadRequestBody>(request);
  const baseUrl = archiveBaseUrl(request);
  const downloads = await getSinglePackage(env, baseUrl, body.package_type, body.package_id, body.platform);

  if (downloads === null) {
    return jsonResponse({ detail: "Package not found" }, 404);
  }
  return jsonResponse(downloads);
}

async function handleGetDb(request: Request, env: Env, name: string): Promise<Response> {
  const denied = checkAccess(env, request, "/api/v1/getdb");
  if (denied) return denied;

  const db = await getDatabaseFile(env, name);
  if (db === null) {
    return jsonResponse({ detail: "Database not found" }, 404);
  }

  return new Response(db, {
    headers: {
      "Content-Type": "application/vnd.sqlite3",
      "Content-Disposition": `attachment; filename="${name}.db_"`,
    },
  });
}

async function handleGetFile(request: Request, env: Env): Promise<Response> {
  const denied = checkAccess(env, request, "/api/v1/getfile");
  if (denied) return denied;

  const body = await parseJsonBody<MicroDownloadRequestBody>(request);
  const baseUrl = archiveBaseUrl(request);
  const downloads = await Promise.all(body.files.map((f) => getMicroDlFile(env, baseUrl, f, body.platform)));
  return jsonResponse(downloads);
}

async function handleReleaseInfo(request: Request, env: Env): Promise<Response> {
  const denied = checkAccess(env, request, "/api/v1/release_info");
  if (denied) return denied;

  const info = await getReleaseInfo(env.ARCHIVE_BUCKET);
  return jsonResponse(info);
}

// ─── Archive file serving (R2) ───

async function handleArchiveGet(request: Request, env: Env, key: string): Promise<Response> {
  const obj = await env.ARCHIVE_BUCKET.get(key);
  if (obj === null) {
    return new Response("Not Found", { status: 404 });
  }

  const headers = new Headers();
  obj.writeHttpMetadata(headers);
  headers.set("etag", obj.httpEtag);
  headers.set("Content-Length", obj.size.toString());

  // Set content type based on extension if not already set
  if (!headers.has("Content-Type")) {
    if (key.endsWith(".zip")) {
      headers.set("Content-Type", "application/zip");
    } else {
      headers.set("Content-Type", "application/octet-stream");
    }
  }

  return new Response(obj.body, { headers });
}

// ─── Router ───

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const path = url.pathname;

    // Archive file serving: GET /archive/...
    if (request.method === "GET" && path.startsWith("/archive/")) {
      const key = path.slice("/archive/".length);
      if (!key) return new Response("Not Found", { status: 404 });
      return handleArchiveGet(request, env, key);
    }

    // API routes
    if (path === "/api/publicinfo" && request.method === "GET") {
      return handlePublicInfo(request, env);
    }
    if (path === "/api/v1/update" && request.method === "POST") {
      return handleUpdate(request, env);
    }
    if (path === "/api/v1/batch" && request.method === "POST") {
      return handleBatch(request, env);
    }
    if (path === "/api/v1/download" && request.method === "POST") {
      return handleDownload(request, env);
    }
    if (path.startsWith("/api/v1/getdb/") && request.method === "GET") {
      const name = path.slice("/api/v1/getdb/".length);
      if (!name) return notFound();
      return handleGetDb(request, env, name);
    }
    if (path === "/api/v1/getfile" && request.method === "POST") {
      return handleGetFile(request, env);
    }
    if (path === "/api/v1/release_info" && request.method === "GET") {
      return handleReleaseInfo(request, env);
    }

    // Dashboard routes
    if (path === "/dashboard" && request.method === "GET") {
      const cursor = await getSyncStatus(env.SYNC_KV);
      return new Response(renderDashboard(cursor), {
        headers: { "Content-Type": "text/html; charset=utf-8" },
      });
    }
    if (path === "/dashboard/json" && request.method === "GET") {
      const cursor = await getSyncStatus(env.SYNC_KV);
      return jsonResponse(renderDashboardJson(cursor));
    }

    return notFound();
  },

  async scheduled(_event: ScheduledEvent, env: Env, ctx: ExecutionContext): Promise<void> {
    ctx.waitUntil(runSync(env));
  },
} satisfies ExportedHandler<Env>;
