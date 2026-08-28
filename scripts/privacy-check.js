#!/usr/bin/env node
/**
 * Release gate: fail if anything private, secret or personal is about to be
 * committed. Runs over every tracked file (or the whole tree outside git).
 *
 * Real private identifiers belong in an untracked `.privacy-denylist.local`
 * (one pattern per line, # for comments). They must never appear in this file.
 *
 *   node scripts/privacy-check.js
 */
"use strict";
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const ROOT = path.resolve(__dirname, "..");

const DENY = [
  { name: "bot-token",        re: /\b\d{8,12}:[A-Za-z0-9_-]{20,}\b/ },
  { name: "absolute-home",    re: /\/home\/[a-z0-9_-]+\//i },
  { name: "tailnet-hostname", re: /[a-z0-9-]+\.ts\.net/i },
  { name: "telegram-config",  re: /TELEGRAM_(BOT_TOKEN|ALLOWED_USERS|CHAT_ID)\s*=\s*\S+/ },
  { name: "private-key",      re: /-----BEGIN (RSA |OPENSSH |EC |PGP )?PRIVATE KEY-----/ },
  { name: "aws-key",          re: /\bAKIA[0-9A-Z]{16}\b/ },
  { name: "generic-secret",   re: /\b(api[_-]?key|secret|passwd|password)\s*[:=]\s*["'][^"'\s]{8,}["']/i },
  { name: "bearer-token",     re: /\bBearer\s+[A-Za-z0-9._~+/-]{20,}/ },
];

const BAD_EXT = new Set([".db", ".sqlite", ".sqlite3", ".log", ".pem", ".key", ".env"]);
const SKIP_DIRS = new Set([".git", "node_modules", "__pycache__", ".venv", "dist", "build"]);
const TEXT_EXT = new Set([".md", ".js", ".mjs", ".ts", ".tsx", ".json", ".yaml", ".yml",
                          ".html", ".css", ".py", ".sh", ".toml", ".txt", ".example", ""]);

// user-supplied local patterns, never committed
const localFile = path.join(ROOT, ".privacy-denylist.local");
if (fs.existsSync(localFile)) {
  fs.readFileSync(localFile, "utf8").split("\n")
    .map(l => l.trim())
    .filter(l => l && !l.startsWith("#"))
    .forEach((l, i) => DENY.push({ name: "local-denylist#" + (i + 1), re: new RegExp(l) }));
  console.log("Loaded local denylist (" + localFile + ") — patterns not displayed.\n");
}

function listFiles() {
  try {
    const out = execSync("git ls-files -z", { cwd: ROOT, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] });
    const tracked = out.split("\0").filter(Boolean);
    if (tracked.length) return tracked;
  } catch (_) { /* not a git repo yet */ }
  const acc = [];
  (function walk(dir) {
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      if (e.isDirectory()) { if (!SKIP_DIRS.has(e.name)) walk(path.join(dir, e.name)); }
      else acc.push(path.relative(ROOT, path.join(dir, e.name)));
    }
  })(ROOT);
  return acc;
}

// A security test suite must contain the strings it tests against. The only
// exemption is a same-line pragma, which is greppable and counted below so it
// can never grow silently.
const PRAGMA = "privacy-check: test-fixture";
const failures = [];
let exempted = 0;
const files = listFiles();

for (const rel of files) {
  const abs = path.join(ROOT, rel);
  const ext = path.extname(rel).toLowerCase();
  const base = path.basename(rel);

  if (BAD_EXT.has(ext) && base !== ".env.example") {
    failures.push({ file: rel, rule: "forbidden-file-type", line: 0,
                    detail: ext + " must never be tracked" });
    continue;
  }
  if (base === ".privacy-denylist.local") {
    failures.push({ file: rel, rule: "denylist-committed", line: 0,
                    detail: "the local denylist must stay untracked" });
    continue;
  }
  if (!TEXT_EXT.has(ext)) continue;

  let text;
  try { text = fs.readFileSync(abs, "utf8"); } catch (_) { continue; }
  if (text.includes("\0")) continue;

  text.split("\n").forEach((line, i) => {
    for (const rule of DENY) {
      if (rule.re.test(line)) {
        if (line.includes(PRAGMA)) { exempted++; continue; }
        failures.push({ file: rel, rule: rule.name, line: i + 1,
                        detail: rule.name.startsWith("local-") ? "(redacted)" : line.trim().slice(0, 90) });
      }
    }
  });
}

console.log("privacy-check — scanned " + files.length + " files"
  + (exempted ? ", " + exempted + " line(s) exempted by pragma" : "") + "\n");
if (failures.length === 0) {
  console.log("PASS — nothing private found.");
  process.exit(0);
}
for (const f of failures) {
  console.log("FAIL  " + f.file + (f.line ? ":" + f.line : "") + "  [" + f.rule + "]\n      " + f.detail);
}
console.log("\n" + failures.length + " problem(s). Nothing should be committed until these are resolved.");
process.exit(1);
