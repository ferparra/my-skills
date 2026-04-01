#!/usr/bin/env node
/**
 * Decompress Excalidraw compressed-json using LZString.
 *
 * Usage:
 *   node decompress_excalidraw.js <path-to-excalidraw.md>
 *
 * Outputs the decompressed JSON to stdout.
 */

const fs = require('fs');
const path = require('path');

// Try multiple lz-string locations
let LZString;
const lzPaths = [
  path.join(__dirname, '..', 'node_modules', 'lz-string', 'libs', 'lz-string.js'),
  '/tmp/node_modules/lz-string/libs/lz-string.js',
  path.join(process.env.HOME || '/root', '.hermes', 'skills', 'obsidian', 'obsidian-excalidraw-file-generation', 'node_modules', 'lz-string', 'libs', 'lz-string.js'),
];
for (const lp of lzPaths) {
  try { LZString = require(lp); break; } catch(e) { /* try next */ }
}
if (!LZString) {
  console.error('Error: lz-string not found. Tried:', lzPaths.join(', '));
  process.exit(1);
}

const filePath = process.argv[2];
if (!filePath) {
  console.error('Usage: node decompress_excalidraw.js <path-to-excalidraw.md>');
  process.exit(1);
}

const content = fs.readFileSync(filePath, 'utf-8');
const match = content.match(/```compressed-json\s+([\s\S]+?)\n```/);

if (!match) {
  console.error('Error: No compressed-json block found in file');
  process.exit(1);
}

const compressed = match[1].trim().replace(/\n+/g, '');
const jsonStr = LZString.decompressFromBase64(compressed);

if (!jsonStr) {
  console.error('Error: LZString.decompressFromBase64 returned null — data may not be LZString format');
  process.exit(1);
}

console.log(jsonStr);
