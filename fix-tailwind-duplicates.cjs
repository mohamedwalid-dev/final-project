#!/usr/bin/env node
const fs = require("fs");
const path = require("path");

const SRC_DIR = path.join(process.cwd(), "src");
const MAIN_CSS_FILENAME = "index.css";

if (!fs.existsSync(SRC_DIR)) {
  console.error(`Could not find "src" folder at ${SRC_DIR}`);
  console.error("Run this script from your frontend project root (where package.json lives).");
  process.exit(1);
}

let scannedCount = 0;
let modifiedCount = 0;
const modifiedFiles = [];
const skippedMainFiles = [];

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
  TAILWIND_IMPORT_REGEX.lastIndex = 0;

  if (!hasTailwindImport) return;

  if (fileName === MAIN_CSS_FILENAME) {
    skippedMainFiles.push(filePath);
    return;
  }

  const updated = content.replace(TAILWIND_IMPORT_REGEX, "").replace(/\n{3,}/g, "\n\n");

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
  console.log("\nNo duplicate @import tailwindcss found outside index.css.");
}

console.log("\nDone. If files were fixed, restart npm run dev and check spacing again.");