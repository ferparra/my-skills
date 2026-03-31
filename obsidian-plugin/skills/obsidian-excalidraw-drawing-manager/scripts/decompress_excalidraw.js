#!/usr/bin/env node
/**
 * Decompress Excalidraw compressed-json using pako.
 *
 * Usage:
 *   node decompress_excalidraw.js <path-to-excalidraw.md>
 *
 * Outputs the decompressed JSON to stdout.
 */

const fs = require('fs');
const path = require('path');

// Try to require pako - if not installed, provide helpful error
let pako;
try {
  pako = require('pako');
} catch (e) {
  console.error('Error: pako is not installed.');
  console.error('Install it with: npm install -g pako');
  console.error('Or run: uvx --from pako --with pako node decompress_excalidraw.js <file>');
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

const compressed = match[1].trim();

try {
  // Decode base64
  const binaryString = atob ? atob(compressed) : Buffer.from(compressed, 'base64').toString('binary');
  const charData = binaryString.split('').map(x => x.charCodeAt(0));
  const binData = new Uint8Array(charData);

  // Decompress with pako (uses raw inflate)
  const decompressed = pako.inflate(binData, { raw: true });

  // Convert to string
  const jsonStr = new TextDecoder().decode(decompressed);

  // Output the JSON
  console.log(jsonStr);
} catch (e) {
  console.error('Error decompressing:', e.message);
  process.exit(1);
}
