import { describe, it, expect, vi } from 'vitest';
import {
  calculateTargetDimensions,
  getQualitySteps,
  formatFileSize,
  optimizePhotoFile,
  MAX_LONGEST_SIDE,
  TARGET_MAX_BYTES,
  HARD_LIMIT_BYTES,
} from './photo-optimizer';

describe('calculateTargetDimensions (Pure Dimension Math)', () => {
  it('resizes portrait orientation images so longest side is 1600 px', () => {
    // 3000 x 4000 (portrait) -> 4000 is longest -> ratio 1600 / 4000 = 0.4
    // width: 3000 * 0.4 = 1200, height: 1600
    const dims = calculateTargetDimensions(3000, 4000, 1600);
    expect(dims.scaled).toBe(true);
    expect(dims.width).toBe(1200);
    expect(dims.height).toBe(1600);
    expect(Math.max(dims.width, dims.height)).toBe(1600);
  });

  it('resizes landscape orientation images so longest side is 1600 px', () => {
    // 4032 x 3024 (standard 12MP phone camera) -> ratio 1600 / 4032
    const dims = calculateTargetDimensions(4032, 3024, 1600);
    expect(dims.scaled).toBe(true);
    expect(dims.width).toBe(1600);
    expect(dims.height).toBe(1200);
    expect(Math.max(dims.width, dims.height)).toBe(1600);
  });

  it('resizes square images to exactly 1600 x 1600', () => {
    const dims = calculateTargetDimensions(2400, 2400, 1600);
    expect(dims.scaled).toBe(true);
    expect(dims.width).toBe(1600);
    expect(dims.height).toBe(1600);
  });

  it('never upscales images smaller than 1600 px on both sides', () => {
    const dims = calculateTargetDimensions(800, 600, 1600);
    expect(dims.scaled).toBe(false);
    expect(dims.width).toBe(800);
    expect(dims.height).toBe(600);
  });

  it('leaves images exactly at 1600 px unscaled', () => {
    const dims = calculateTargetDimensions(1600, 1200, 1600);
    expect(dims.scaled).toBe(false);
    expect(dims.width).toBe(1600);
    expect(dims.height).toBe(1200);
  });

  it('handles zero or negative dimensions safely', () => {
    const dims = calculateTargetDimensions(0, 0, 1600);
    expect(dims.scaled).toBe(false);
    expect(dims.width).toBe(0);
    expect(dims.height).toBe(0);
  });
});

describe('getQualitySteps (Compression Iteration Policy)', () => {
  it('generates descending steps starting at 0.82 down to 0.60', () => {
    const steps = getQualitySteps(0.82, 0.60, 0.05);
    expect(steps[0]).toBe(0.82);
    expect(steps[steps.length - 1]).toBe(0.60);
    // Strict monotonic decrease
    for (let i = 1; i < steps.length; i++) {
      expect(steps[i]).toBeLessThan(steps[i - 1]);
    }
  });

  it('terminates properly with finite steps', () => {
    const steps = getQualitySteps(0.82, 0.60, 0.05);
    expect(steps.length).toBeGreaterThan(2);
    expect(steps.length).toBeLessThan(10);
  });
});

describe('formatFileSize', () => {
  it('formats bytes, kilobytes, and megabytes cleanly', () => {
    expect(formatFileSize(450)).toBe('450 B');
    expect(formatFileSize(348160)).toBe('340 KB');
    expect(formatFileSize(4194304)).toBe('4.0 MB');
  });
});

describe('optimizePhotoFile (Fallback & Boundary Handling)', () => {
  it('falls back to original file if processing throws and file <= 4MB', async () => {
    // A synthetic unreadable file (e.g. simulated HEIC without browser canvas support)
    const fakeHeic = new File([new Uint8Array(1024 * 1024)], 'photo.heic', { type: 'image/heic' });
    const result = await optimizePhotoFile(fakeHeic);
    expect(result.fallback).toBe(true);
    expect(result.file).toBe(fakeHeic);
    expect(result.originalSize).toBe(1024 * 1024);
    expect(result.optimizedSize).toBe(1024 * 1024);
  });

  it('rejects with user-friendly error if unprocessable file exceeds 4MB', async () => {
    // 5MB unreadable file
    const oversizedFile = new File([new Uint8Array(5 * 1024 * 1024)], 'huge.raw', { type: 'application/octet-stream' });
    await expect(optimizePhotoFile(oversizedFile)).rejects.toThrow(/exceeds the 4 MB upload limit/);
  });
});
