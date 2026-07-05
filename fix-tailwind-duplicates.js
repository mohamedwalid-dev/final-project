#!/usr/bin/env node
/**
 * fix-tailwind-duplicates.js
 *
 * Scans the src/ folder for every .css file, and removes any
 * `@import "tailwindcss";` line found OUTSIDE of index.css.
 * This fixes the "multiple Tailwind preflight resets loaded at once"
 * bug that causes spacing/padding/gap classes to silently not apply.
 *
 * Usage (run from the frontend project root, next to package.json):
 *   node fix-tailwind-duplicates.js
 *
 * It is SAFE to run multiple times (idempotent).
 * It creates a .bak backup of every file it modifies.
 */

const fs = require("fs");
const path = require("path");

const SRC_DIR = path.join(process.cwd(), "src");
const MAIN_CSS_FILENAME = "index.css"; // the ONE file allowed to import tailwindcss

if (!fs.existsSync(SRC_DIR)) {
  console.error(`Could not find "src" folder at ${SRC_DIR}`);
  console.error("Run this script from your frontend project root (where package.json lives).");
  process.exit(1);
}

let scannedCount = 0;
let modifiedCount = 0;
const modifiedFiles = [];
const skippedMainFiles = [];

// Matches: @import "tailwindcss";  OR  @import 'tailwindcss';  (with optional whitespace)
const TAILWIND_IMPORT_REGEX = /^\s*@import\s+["']tailwindcss["'];\s*$/gm;

function walk(dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.name === "node_modules" || entry.name.startsWith(".")) continue;

    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(fullPath);
    } else if (entry.isFile() && entry.name.endsWith(".css")) {
      processFile(fullPath, entry.name);
    }
  }
}

function processFile(filePath, fileName) {
  scannedCount++;
  const content = fs.readFileSync(filePath, "utf8");

  const hasTailwindImport = TAILWIND_IMPORT_REGEX.test(content);
  TAILWIND_IMPORT_REGEX.lastIndex = 0; // reset regex state after .test()

  if (!hasTailwindImport) return;

  if (fileName === MAIN_CSS_FILENAME) {
    skippedMainFiles.push(filePath);
    return; // this is the allowed one, leave it alone
  }

  // Remove the import line(s) from this file
  const updated = content.replace(TAILWIND_IMPORT_REGEX, "").replace(/\n{3,}/g, "\n\n");

  // Backup original before touching it
  fs.writeFileSync(filePath + ".bak", content, "utf8");
  fs.writeFileSync(filePath, updated, "utf8");

  modifiedCount++;
  modifiedFiles.push(filePath);
}

console.log("Scanning for duplicate Tailwind imports under:", SRC_DIR);
walk(SRC_DIR);

console.log("\n--- Summary ---");
console.log(`CSS files scanned: ${scannedCount}`);
console.log(`Kept tailwind import (main entry): ${skippedMainFiles.length}`);
skippedMainFiles.forEach((f) => console.log("  KEPT:  " + f));
console.log(`Fixed (duplicate import removed): ${modifiedCount}`);
modifiedFiles.forEach((f) => console.log("  FIXED: " + f));

if (modifiedCount === 0) {
  console.log("\nNo duplicate @import \"tailwindcss\" found outside index.css.");
  console.log("The spacing bug may have a different cause — see the follow-up checklist printed below.");
}

console.log(`
Next steps:
1. If any files were FIXED above, restart your dev server (npm run dev) and check the landing page spacing again.
2. Backups were saved as <filename>.css.bak next to each modified file — safe to delete once you confirm everything looks right.
3. If NO files were fixed and the spacing bug persists, the cause is likely elsewhere (e.g. static imports of every page in App.jsx loading many independent CSS Modules at once). Reply here and we'll dig into App.jsx's import structure directly.
`);
