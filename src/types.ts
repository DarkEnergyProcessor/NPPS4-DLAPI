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

export interface Env {
  ARCHIVE_BUCKET: R2Bucket;
  SYNC_KV: KVNamespace;
  PUBLIC: string;
  SHARED_KEY?: string;
  API_ACCESS?: string;
  UPSTREAM_URL?: string;
  UPSTREAM_SHARED_KEY?: string;
}

export enum PlatformType {
  IOS = 1,
  ANDROID = 2,
}

export enum PackageType {
  BOOTSTRAP = 0,
  LIVE = 1,
  SCENARIO = 2,
  SUBSCENARIO = 3,
  MICRO = 4,
  EVENT_SCENARIO = 5,
  MULTI_UNIT_SCENARIO = 6,
}

export const PLATFORM_MAP = ["iOS", "Android"] as const;

export interface ChecksumModel {
  md5: string;
  sha256: string;
}

export interface DownloadInfoModel {
  url: string;
  size: number;
  checksums: ChecksumModel;
}

export interface DownloadUpdateModel extends DownloadInfoModel {
  version: string;
}

export interface BatchDownloadInfoModel extends DownloadInfoModel {
  packageId: number;
}

export interface VersionModel {
  major: number;
  minor: number;
}

export interface PublicInfoModel {
  publicApi: boolean;
  dlapiVersion: VersionModel;
  serveTimeLimit: number;
  gameVersion: string;
  application: Record<string, string>;
}

export interface ErrorResponseModel {
  detail: string;
}

// Request bodies

export interface UpdateRequestBody {
  version: string;
  platform: PlatformType;
}

export interface BatchDownloadRequestBody {
  package_type: PackageType;
  platform: PlatformType;
  exclude?: number[];
}

export interface DownloadRequestBody {
  package_type: PackageType;
  package_id: number;
  platform: PlatformType;
}

export interface MicroDownloadRequestBody {
  files: string[];
  platform: PlatformType;
}

// Metadata JSON shapes stored in R2

export interface FileDataV2 {
  name: string;
  size: number;
  md5: string;
  sha256: string;
}

export interface MicroDlInfo {
  [path: string]: {
    size: number;
    md5: string;
    sha256: string;
  };
}

// ── Sync types ──

export type SyncPhase = "fetch_links" | "update" | "packages" | "metadata" | "done";

export interface SyncFileLink {
  url: string;
  r2Key: string;
  size: number;
  md5: string;
  sha256: string;
}

export interface SyncCursor {
  phase: SyncPhase;
  upstreamVersion: string;
  /** All file links to download, collected during fetch_links phase */
  files: SyncFileLink[];
  /** Index into files array — how far we've gotten */
  fileIndex: number;
  /** Bytes uploaded so far */
  bytesUploaded: number;
  /** Files uploaded so far */
  filesUploaded: number;
  /** Total bytes to upload */
  totalBytes: number;
  /** Total files to upload */
  totalFiles: number;
  /** Timestamp when sync started */
  startedAt: number;
  /** Timestamp of last activity */
  lastActivityAt: number;
  /** Error message if last run failed */
  lastError?: string;
  /** Metadata JSON files to write (collected during fetch_links) */
  metadataWrites: Array<{ key: string; data: unknown }>;
}
