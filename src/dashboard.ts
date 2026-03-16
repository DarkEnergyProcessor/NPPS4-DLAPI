import type { SyncCursor } from "./types";

function fmtBytes(bytes: number): string {
  if (bytes >= 1 << 30) return `${(bytes / (1 << 30)).toFixed(2)} GB`;
  if (bytes >= 1 << 20) return `${(bytes / (1 << 20)).toFixed(2)} MB`;
  if (bytes >= 1 << 10) return `${(bytes / (1 << 10)).toFixed(2)} KB`;
  return `${bytes} B`;
}

function fmtDuration(ms: number): string {
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const rs = s % 60;
  if (m < 60) return `${m}m ${rs}s`;
  const h = Math.floor(m / 60);
  const rm = m % 60;
  return `${h}h ${rm}m`;
}

function fmtTime(ts: number): string {
  return new Date(ts).toISOString().replace("T", " ").replace(/\.\d+Z/, " UTC");
}

function progressBar(pct: number, width = 30): string {
  const filled = Math.round((pct / 100) * width);
  const empty = width - filled;
  return `[${"█".repeat(filled)}${"░".repeat(empty)}]`;
}

function phaseLabel(phase: string): string {
  switch (phase) {
    case "fetch_links": return "Fetching file list from upstream";
    case "update": return "Downloading files";
    case "packages": return "Downloading files";
    case "metadata": return "Writing metadata";
    case "done": return "Sync complete";
    default: return phase;
  }
}

function phaseEmoji(phase: string): string {
  switch (phase) {
    case "fetch_links": return "🔍";
    case "update": return "⬇️";
    case "packages": return "⬇️";
    case "metadata": return "📝";
    case "done": return "✅";
    default: return "❓";
  }
}

export function renderDashboard(cursor: SyncCursor | null): string {
  const now = Date.now();

  if (!cursor) {
    return page("Sync Dashboard", `
      <div class="card">
        <h2>No sync in progress</h2>
        <p class="muted">No upstream URL configured or sync has not been triggered yet.</p>
        <p class="muted">Set <code>UPSTREAM_URL</code> via <code>wrangler secret put</code> to enable sync.</p>
      </div>
    `);
  }

  const pctFiles = cursor.totalFiles > 0 ? (cursor.filesUploaded / cursor.totalFiles) * 100 : 0;
  const pctBytes = cursor.totalBytes > 0 ? (cursor.bytesUploaded / cursor.totalBytes) * 100 : 0;
  const elapsed = now - cursor.startedAt;
  const lastActive = now - cursor.lastActivityAt;

  // ETA calculation
  let eta = "";
  if (cursor.phase !== "done" && cursor.phase !== "fetch_links" && pctBytes > 0) {
    const remaining = (elapsed / pctBytes) * (100 - pctBytes);
    eta = `~${fmtDuration(remaining)} remaining`;
  }

  // Speed calculation
  let speed = "";
  if (elapsed > 0 && cursor.bytesUploaded > 0) {
    const bytesPerSec = (cursor.bytesUploaded / elapsed) * 1000;
    speed = `${fmtBytes(bytesPerSec)}/s avg`;
  }

  return page("Sync Dashboard", `
    <div class="card">
      <div class="status-row">
        <span class="phase-emoji">${phaseEmoji(cursor.phase)}</span>
        <div>
          <h2>${phaseLabel(cursor.phase)}</h2>
          <span class="muted">Target version: ${cursor.upstreamVersion || "detecting..."}</span>
        </div>
      </div>
    </div>

    ${cursor.lastError ? `
    <div class="card error">
      <h3>Last Error</h3>
      <pre>${escapeHtml(cursor.lastError)}</pre>
      <p class="muted">Will retry on next cron invocation.</p>
    </div>
    ` : ""}

    <div class="card">
      <h3>Progress</h3>
      <div class="progress-section">
        <div class="progress-label">
          <span>Files</span>
          <span>${cursor.filesUploaded.toLocaleString()} / ${cursor.totalFiles.toLocaleString()}</span>
        </div>
        <div class="progress-bar">
          <div class="progress-fill" style="width: ${pctFiles.toFixed(1)}%"></div>
        </div>
        <span class="pct">${pctFiles.toFixed(1)}%</span>
      </div>
      <div class="progress-section">
        <div class="progress-label">
          <span>Data</span>
          <span>${fmtBytes(cursor.bytesUploaded)} / ${fmtBytes(cursor.totalBytes)}</span>
        </div>
        <div class="progress-bar">
          <div class="progress-fill" style="width: ${pctBytes.toFixed(1)}%"></div>
        </div>
        <span class="pct">${pctBytes.toFixed(1)}%</span>
      </div>
    </div>

    <div class="grid">
      <div class="card stat">
        <div class="stat-value">${fmtDuration(elapsed)}</div>
        <div class="stat-label">Elapsed</div>
      </div>
      <div class="card stat">
        <div class="stat-value">${speed || "—"}</div>
        <div class="stat-label">Avg Speed</div>
      </div>
      <div class="card stat">
        <div class="stat-value">${eta || "—"}</div>
        <div class="stat-label">ETA</div>
      </div>
      <div class="card stat">
        <div class="stat-value">${fmtDuration(lastActive)} ago</div>
        <div class="stat-label">Last Activity</div>
      </div>
    </div>

    <div class="card">
      <h3>Timing</h3>
      <table>
        <tr><td class="muted">Started</td><td>${fmtTime(cursor.startedAt)}</td></tr>
        <tr><td class="muted">Last active</td><td>${fmtTime(cursor.lastActivityAt)}</td></tr>
      </table>
    </div>

    <div class="card">
      <p class="muted" style="text-align:center;margin:0">
        Auto-refreshes every 30 seconds.
        Sync runs via cron trigger every 5 minutes.
      </p>
    </div>
  `);
}

export function renderDashboardJson(cursor: SyncCursor | null): object {
  if (!cursor) {
    return { status: "idle", message: "No sync in progress" };
  }
  return {
    status: cursor.phase,
    upstreamVersion: cursor.upstreamVersion,
    filesUploaded: cursor.filesUploaded,
    totalFiles: cursor.totalFiles,
    bytesUploaded: cursor.bytesUploaded,
    totalBytes: cursor.totalBytes,
    progressPercent: cursor.totalBytes > 0 ? +((cursor.bytesUploaded / cursor.totalBytes) * 100).toFixed(1) : 0,
    startedAt: cursor.startedAt,
    lastActivityAt: cursor.lastActivityAt,
    lastError: cursor.lastError ?? null,
  };
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function page(title: string, body: string): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${title}</title>
<meta http-equiv="refresh" content="30">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #0f1117;
    color: #e1e4e8;
    padding: 24px;
    max-width: 720px;
    margin: 0 auto;
  }
  h1 { font-size: 1.5rem; margin-bottom: 20px; color: #fff; }
  h2 { font-size: 1.1rem; color: #fff; }
  h3 { font-size: 0.9rem; color: #8b949e; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 12px; }
  .card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 12px;
  }
  .card.error {
    border-color: #f85149;
    background: #1c1210;
  }
  .card.error h3 { color: #f85149; }
  .card.error pre {
    color: #f85149;
    font-size: 0.85rem;
    white-space: pre-wrap;
    word-break: break-all;
  }
  .status-row { display: flex; align-items: center; gap: 12px; }
  .phase-emoji { font-size: 2rem; }
  .muted { color: #8b949e; font-size: 0.85rem; }
  code { background: #21262d; padding: 2px 6px; border-radius: 4px; font-size: 0.85rem; }
  .progress-section { margin-bottom: 12px; }
  .progress-label { display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 4px; }
  .progress-bar {
    height: 8px;
    background: #21262d;
    border-radius: 4px;
    overflow: hidden;
  }
  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #238636, #2ea043);
    border-radius: 4px;
    transition: width 0.5s ease;
  }
  .pct { font-size: 0.8rem; color: #8b949e; }
  .grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-bottom: 12px; }
  .stat { text-align: center; }
  .stat-value { font-size: 1.3rem; font-weight: 600; color: #fff; }
  .stat-label { font-size: 0.8rem; color: #8b949e; margin-top: 4px; }
  table { width: 100%; }
  td { padding: 4px 0; font-size: 0.9rem; }
  td.muted { width: 120px; }
  @media (max-width: 480px) {
    .grid { grid-template-columns: 1fr 1fr; }
    body { padding: 12px; }
  }
</style>
</head>
<body>
<h1>${title}</h1>
${body}
</body>
</html>`;
}
