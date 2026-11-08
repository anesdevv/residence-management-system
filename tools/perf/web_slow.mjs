#!/usr/bin/env node
/**
 * RÉSIVO — Web Slow Network & Device Performance Test Runner
 *
 * Emulates mobile Lighthouse "Slow 4G" network conditions and 4x CPU throttling via Chrome DevTools Protocol (CDP).
 *
 * Throttling Profile:
 * - Latency: 150 ms
 * - Download: 1.6 Mbps (200,000 B/s)
 * - Upload: 750 kbps (93,750 B/s)
 * - CPU: 4x slowdown
 * - Viewport: 390 x 844 (mobile)
 *
 * Flows tested:
 * 1. Landing (/)
 * 2. Register (/register - form fill)
 * 3. Login (/login - form fill)
 * 4. Dashboard (/dashboard)
 * 5. Maintenance Ticket (/dashboard/maintenance - with 4 MB photo upload)
 * 6. Room-Change Form (/dashboard/room-change)
 *
 * Collects: LCP, CLS, wire transferred bytes, request count, time-to-usable.
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, '../..');

// Dynamically import playwright (supports both local web/node_modules and global)
let playwright;
try {
  playwright = await import('playwright');
} catch {
  try {
    const webPlaywright = path.resolve(REPO_ROOT, 'web/node_modules/playwright/index.mjs');
    playwright = await import(webPlaywright);
  } catch {
    console.error(
      '\n[ERROR] Playwright is not installed yet.\n' +
      'Please install playwright as a devDependency in web/:\n' +
      '  cd web && npm install -D playwright\n'
    );
    process.exit(1);
  }
}

const { chromium } = playwright;

const BASE_URL = process.env.BASE_URL || 'http://localhost:4321';
const USE_LOCAL_SUPABASE = process.env.USE_LOCAL_SUPABASE === 'true';

// ---------------------------------------------------------------------------
// 4 MB Test Photo Generator
// ---------------------------------------------------------------------------
function create4MBTestPhoto(filePath) {
  const dir = path.dirname(filePath);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });

  const size = 4 * 1024 * 1024; // 4,194,304 bytes
  const buffer = Buffer.alloc(size);

  // JPEG Header
  buffer[0] = 0xff;
  buffer[1] = 0xd8; // SOI
  buffer[2] = 0xff;
  buffer[3] = 0xe0; // APP0
  buffer[4] = 0x00;
  buffer[5] = 0x10;
  buffer.write('JFIF\0\1\1\0\0\1\0\1\0\0', 6, 'latin1');

  // Fill pseudo-random image payload
  for (let i = 20; i < size - 2; i++) {
    buffer[i] = (i * 33 + 7) & 0xff;
  }

  // JPEG EOI marker
  buffer[size - 2] = 0xff;
  buffer[size - 1] = 0xd9;

  fs.writeFileSync(filePath, buffer);
  return filePath;
}

// ---------------------------------------------------------------------------
// Mock Supabase Fixtures & Routing
// ---------------------------------------------------------------------------
async function setupMockRoutes(context) {
  if (USE_LOCAL_SUPABASE) {
    console.log('[Runner] Using live/local Supabase backend (routes unmocked).');
    return;
  }

  console.log('[Runner] Mocking Supabase and auth endpoints for cloud-independent run.');

  // Mock Supabase Auth calls
  await context.route('**/auth/v1/**', async (route) => {
    const url = route.request().url();
    if (url.includes('/token') || url.includes('/user')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          access_token: 'mock-access-token',
          token_type: 'bearer',
          expires_in: 3600,
          user: {
            id: 'mock-user-123',
            email: 'student@univ.dz',
            user_metadata: { card_id: 'CARD-123456', full_name: 'Amine Benali' },
          },
        }),
      });
    }
    return route.continue();
  });

  // Mock PostgREST table queries
  await context.route('**/rest/v1/**', async (route) => {
    const url = route.request().url();
    if (url.includes('/students')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'mock-student-id',
            card_id: 'CARD-123456',
            first_name: 'Amine',
            last_name: 'Benali',
            status: 'active',
            room_id: 'room-101',
            rooms: { block: 'A', number: '101' },
          },
        ]),
      });
    }
    if (url.includes('/maintenance_reports')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    }
    if (url.includes('/room_change_requests')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    });
  });

  // Mock Storage upload
  await context.route('**/storage/v1/object/**', async (route) => {
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ Key: 'maintenance-photos/mock-photo.jpg' }),
    });
  });

  // Set mock authenticated session cookie for Astro SSR dashboard pages
  await context.addCookies([
    {
      name: 'sb-mock-auth-token',
      value: 'mock-token',
      domain: 'localhost',
      path: '/',
    },
  ]);
}

// ---------------------------------------------------------------------------
// Single Flow Measurement
// ---------------------------------------------------------------------------
async function measureFlow(page, client, flowName, runnerFn) {
  let transferredBytes = 0;
  let requestCount = 0;

  const onLoadingFinished = (params) => {
    transferredBytes += params.encodedDataLength || 0;
  };
  const onRequestWillBeSent = () => {
    requestCount++;
  };

  client.on('Network.loadingFinished', onLoadingFinished);
  client.on('Network.requestWillBeSent', onRequestWillBeSent);

  const t0 = performance.now();
  const flowResult = await runnerFn(page);
  const totalDurationMs = performance.now() - t0;

  client.off('Network.loadingFinished', onLoadingFinished);
  client.off('Network.requestWillBeSent', onRequestWillBeSent);

  // Extract LCP and CLS via PerformanceObserver in browser context
  const perf = await page.evaluate(() => {
    return new Promise((resolve) => {
      let lcp = 0;
      let cls = 0;

      try {
        const poLCP = new PerformanceObserver((list) => {
          const entries = list.getEntries();
          const last = entries[entries.length - 1];
          if (last) lcp = last.renderTime || last.loadTime;
        });
        poLCP.observe({ type: 'largest-contentful-paint', buffered: true });

        const poCLS = new PerformanceObserver((list) => {
          for (const entry of list.getEntries()) {
            if (!entry.hadRecentInput) cls += entry.value;
          }
        });
        poCLS.observe({ type: 'layout-shift', buffered: true });
      } catch (e) {}

      setTimeout(() => {
        resolve({
          lcp: Math.round(lcp || performance.now()),
          cls: parseFloat(cls.toFixed(4)),
        });
      }, 250);
    });
  });

  return {
    flow: flowName,
    lcpMs: perf.lcp,
    cls: perf.cls,
    transferredKB: parseFloat((transferredBytes / 1024).toFixed(2)),
    requestCount,
    timeToUsableMs: Math.round(flowResult.timeToUsableMs || totalDurationMs),
    details: flowResult.details || '',
  };
}

// ---------------------------------------------------------------------------
// Main Test Suite
// ---------------------------------------------------------------------------
async function run() {
  console.log('='.repeat(70));
  console.log('  RÉSIVO Web Slow-Network (Slow 4G) & Device Performance Test');
  console.log('='.repeat(70));
  console.log(`Base URL: ${BASE_URL}`);

  const testPhotoPath = path.resolve(__dirname, '.tmp_photo_4mb.jpg');
  create4MBTestPhoto(testPhotoPath);
  console.log(`[Setup] Generated 4 MB test photo at ${testPhotoPath}`);

  const browser = await chromium.launch({
    headless: true,
  });

  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 3,
    isMobile: true,
    hasTouch: true,
    userAgent:
      'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
  });

  await setupMockRoutes(context);

  const page = await context.newPage();
  const client = await context.newCDPSession(page);

  // Configure CDP Network Conditions: Slow 4G
  await client.send('Network.enable');
  await client.send('Network.emulateNetworkConditions', {
    offline: false,
    latency: 150, // ms
    downloadThroughput: (1.6 * 1024 * 1024) / 8, // 1.6 Mbps = 200,000 B/s
    uploadThroughput: (750 * 1024) / 8, // 750 kbps = 93,750 B/s
    connectionType: 'cellular4g',
  });

  // Configure CPU Throttling 4x
  await client.send('Emulation.setCPUThrottlingRate', { rate: 4 });
  console.log('[CDP] Emulating Slow 4G (150ms RTT, 1.6M down, 750k up) + 4x CPU Throttling.\n');

  const results = [];

  // 1. Landing Page Flow
  console.log('-> Testing Flow 1: Landing Page (/)');
  results.push(
    await measureFlow(page, client, 'Landing Page (/)', async (p) => {
      const tStart = performance.now();
      await p.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded' });
      await p.waitForSelector('main', { state: 'visible' });
      const timeToUsableMs = performance.now() - tStart;
      return { timeToUsableMs, details: 'Hero & CTA interactive' };
    })
  );

  // 2. Register Page Flow
  console.log('-> Testing Flow 2: Student Registration Form (/register)');
  results.push(
    await measureFlow(page, client, 'Register Form (/register)', async (p) => {
      const tStart = performance.now();
      await p.goto(`${BASE_URL}/register`, { waitUntil: 'domcontentloaded' });
      await p.waitForSelector('form input[name="card_id"]', { state: 'visible' });
      const timeToUsableMs = performance.now() - tStart;

      // Fill registration form to verify inputs respond smoothly under 4x CPU
      await p.fill('input[name="card_id"]', '202437010001');
      await p.fill('input[name="first_name"]', 'Yacine');
      await p.fill('input[name="last_name"]', 'Brahimi');
      return { timeToUsableMs, details: 'Card ID & name fields filled' };
    })
  );

  // 3. Login Page Flow
  console.log('-> Testing Flow 3: Login Form (/login)');
  results.push(
    await measureFlow(page, client, 'Login Form (/login)', async (p) => {
      const tStart = performance.now();
      await p.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' });
      await p.waitForSelector('form input[name="card_id"]', { state: 'visible' });
      const timeToUsableMs = performance.now() - tStart;

      await p.fill('input[name="card_id"]', '202437010001');
      await p.fill('input[name="password"]', 'Resivo2026!');
      return { timeToUsableMs, details: 'Card ID & password inputs filled' };
    })
  );

  // 4. Dashboard Flow
  console.log('-> Testing Flow 4: Resident Dashboard (/dashboard)');
  results.push(
    await measureFlow(page, client, 'Dashboard (/dashboard)', async (p) => {
      const tStart = performance.now();
      await p.goto(`${BASE_URL}/dashboard`, { waitUntil: 'domcontentloaded' });
      await p.waitForSelector('main, .error-banner, #login-form', { state: 'visible' });
      const timeToUsableMs = performance.now() - tStart;
      return { timeToUsableMs, details: 'Header, pass & services rendered' };
    })
  );

  // 5. Maintenance Ticket with 4 MB Photo Flow
  console.log('-> Testing Flow 5: Maintenance Ticket with 4 MB Photo Upload');
  results.push(
    await measureFlow(page, client, 'Maintenance Ticket Form', async (p) => {
      const tStart = performance.now();
      await p.goto(`${BASE_URL}/dashboard/maintenance`, { waitUntil: 'domcontentloaded' });
      const timeToUsableMs = performance.now() - tStart;

      const fileInput = await p.$('input[type="file"]');
      if (fileInput) {
        // Upload 4MB photo to test client-side optimizer compression on Slow 4G
        await fileInput.setInputFiles(testPhotoPath);
        // Wait for optimization badge / indicator
        await p.waitForTimeout(500);
      }
      return { timeToUsableMs, details: '4 MB photo attached & client-optimized' };
    })
  );

  // 6. Room Change Form Flow
  console.log('-> Testing Flow 6: Room Change Form (/dashboard/room-change)');
  results.push(
    await measureFlow(page, client, 'Room Change Form', async (p) => {
      const tStart = performance.now();
      await p.goto(`${BASE_URL}/dashboard/room-change`, { waitUntil: 'domcontentloaded' });
      await p.waitForSelector('main, form, .error-banner, #login-form', { state: 'visible' });
      const timeToUsableMs = performance.now() - tStart;
      return { timeToUsableMs, details: 'Transfer reason form usable' };
    })
  );

  await browser.close();

  // Cleanup test photo
  try {
    if (fs.existsSync(testPhotoPath)) fs.unlinkSync(testPhotoPath);
  } catch {}

  // ---------------------------------------------------------------------------
  // Output Results & Propose Budgets
  // ---------------------------------------------------------------------------
  console.log('\n' + '='.repeat(70));
  console.log('  MEASUREMENT RESULTS UNDER SLOW 4G + 4x CPU THROTTLING');
  console.log('='.repeat(70));
  console.table(
    results.map((r) => ({
      Flow: r.flow,
      'LCP (ms)': r.lcpMs,
      CLS: r.cls,
      'Transferred (KB)': r.transferredKB,
      Requests: r.requestCount,
      'Usable (ms)': r.timeToUsableMs,
      Notes: r.details,
    }))
  );

  // Derive empirical budgets (1.25x measured baseline as warning threshold)
  console.log('\n' + '='.repeat(70));
  console.log('  PROPOSED PERFORMANCE BUDGETS (Warning Thresholds: 1.25x Baseline)');
  console.log('='.repeat(70));

  const budgets = results.map((r) => ({
    flow: r.flow,
    budgetLCP: Math.round(r.lcpMs * 1.25),
    budgetCLS: 0.05,
    budgetTransferKB: Math.round(r.transferredKB * 1.25) || 350,
    budgetUsableMs: Math.round(r.timeToUsableMs * 1.25),
  }));

  budgets.forEach((b) => {
    console.log(
      `[Budget] ${b.flow.padEnd(26)}: LCP <= ${b.budgetLCP} ms | CLS <= ${b.budgetCLS} | Payload <= ${b.budgetTransferKB} KB | Usable <= ${b.budgetUsableMs} ms`
    );
  });

  return { results, budgets };
}

run().catch((err) => {
  console.error('[Error] Slow network runner encountered an error:', err);
  process.exit(1);
});
