/* Shared helpers for the unreasonable-craft scripts: argument parsing, Chrome,
   and labelled contact sheets. Dependencies live next to this file; if they're
   missing, run: npm install --prefix <this folder> */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const HERE = path.dirname(fileURLToPath(import.meta.url));

export function fail(message) {
  console.error(`error: ${message}`);
  process.exit(1);
}

export async function need(name) {
  try {
    return await import(name);
  } catch {
    fail(`missing dependency "${name}". Run: npm install --prefix "${HERE}"`);
  }
}

// --name value, --flag (when listed in bools), and positionals in `_`.
export function parseArgs(argv, bools = []) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const token = argv[i];
    if (!token.startsWith("--")) {
      out._.push(token);
      continue;
    }
    const name = token.slice(2);
    if (bools.includes(name)) out[name] = true;
    else if (i + 1 < argv.length) out[name] = argv[++i];
    else fail(`--${name} needs a value`);
  }
  return out;
}

const CHROMES = [
  process.env.CHROME_PATH,
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/Applications/Chromium.app/Contents/MacOS/Chromium",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
  "/usr/bin/chromium-browser",
];

export async function launchChrome() {
  const { chromium } = await need("playwright-core");
  const options = {
    headless: true,
    // SwiftShader keeps WebGL working headless; sRGB keeps colors comparable across captures.
    args: [
      "--use-gl=angle",
      "--use-angle=swiftshader",
      "--enable-unsafe-swiftshader",
      "--force-color-profile=srgb",
      "--hide-scrollbars",
    ],
  };
  const executablePath = CHROMES.find((p) => p && fs.existsSync(p));
  try {
    return await chromium.launch(executablePath ? { ...options, executablePath } : options);
  } catch (error) {
    fail(
      `couldn't start Chrome (${error.message.split("\n")[0]}). Install Google Chrome or set CHROME_PATH. ` +
        "If a sandbox blocked it, rerun this command with permission to run outside the sandbox.",
    );
  }
}

const escapeXml = (s) => String(s).replace(/[<>&"]/g, (c) => `&#${c.charCodeAt(0)};`);

// tiles: [{ input: file path or Buffer, label }]. Labels sit in a strip above each
// frame so they never cover what you're inspecting.
export async function contactSheet(tiles, out, { cols = 8, width = 240, gap = 6 } = {}) {
  const sharp = (await need("sharp")).default;
  const strip = 22;
  const rendered = [];
  let tileHeight = 0;
  for (const { input, label } of tiles) {
    const image = await sharp(input).resize({ width }).png().toBuffer();
    const { height } = await sharp(image).metadata();
    tileHeight = Math.max(tileHeight, height + strip);
    const text = Buffer.from(
      `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${strip}">` +
        `<rect width="100%" height="100%" fill="#0b0b0c"/>` +
        `<text x="6" y="15.5" font-family="Menlo, monospace" font-size="12" fill="#e8e8e8">${escapeXml(label)}</text></svg>`,
    );
    rendered.push(
      await sharp({ create: { width, height: height + strip, channels: 3, background: "#0b0b0c" } })
        .composite([
          { input: text, top: 0, left: 0 },
          { input: image, top: strip, left: 0 },
        ])
        .png()
        .toBuffer(),
    );
  }
  const columns = Math.min(cols, rendered.length);
  const rows = Math.ceil(rendered.length / cols);
  await sharp({
    create: {
      width: columns * (width + gap) + gap,
      height: rows * (tileHeight + gap) + gap,
      channels: 3,
      background: "#2a2b2d",
    },
  })
    .composite(
      rendered.map((input, i) => ({
        input,
        left: gap + (i % cols) * (width + gap),
        top: gap + Math.floor(i / cols) * (tileHeight + gap),
      })),
    )
    .png()
    .toFile(out);
  return out;
}
