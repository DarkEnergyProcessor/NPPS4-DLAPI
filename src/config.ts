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

import type { Env } from "./types";

export function isPublicAccessible(env: Env): boolean {
  return env.PUBLIC === "true";
}

function isEndpointAccessible(env: Env, endpoint: string): boolean {
  const mainPublic = env.PUBLIC === "true";
  if (!env.API_ACCESS) return mainPublic;

  let apiAccess: Record<string, unknown>;
  try {
    apiAccess = JSON.parse(env.API_ACCESS);
  } catch {
    return mainPublic;
  }

  // Split "/api/v1/update" -> ["api", "v1", "update"]
  const parts = (endpoint.startsWith("/") ? endpoint.slice(1) : endpoint).split("/");
  if (parts[0] !== "api") return false;

  let current: Record<string, unknown> = apiAccess;
  for (const part of parts.slice(1)) {
    const next = current[part];
    if (next === undefined || next === null || typeof next !== "object") break;
    current = next as Record<string, unknown>;
  }

  const pub = current["public"];
  return typeof pub === "boolean" ? pub : mainPublic;
}

export function isAccessible(env: Env, endpoint: string, sharedKey: string | null): boolean {
  if (!env.SHARED_KEY) return true;
  if (isEndpointAccessible(env, endpoint)) return true;
  return env.SHARED_KEY === sharedKey;
}
