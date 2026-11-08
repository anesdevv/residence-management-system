/**
 * RÉSIVO — Maintenance Photo Client-Side Optimizer
 *
 * Implements client-side image processing before form upload:
 * 1. Resizes so the longest side is at most 1600 px (never upscales).
 * 2. Respects EXIF orientation via createImageBitmap(..., { imageOrientation: 'from-image' }).
 * 3. Re-encodes as JPEG starting at quality ~0.82 down to 0.60 until file is <= 500 KB.
 * 4. Fallback path: If processing fails (e.g. unreadable HEIC), falls back to original
 *    if within existing 4 MB limit, otherwise produces a clear user error.
 * 5. Pure math and step functions for deterministic testing in Vitest.
 */

export const MAX_LONGEST_SIDE = 1600;
export const TARGET_MAX_BYTES = 500 * 1024; // 500 KB target
export const HARD_LIMIT_BYTES = 4 * 1024 * 1024; // 4 MB hard limit
export const INITIAL_JPEG_QUALITY = 0.82;
export const MIN_JPEG_QUALITY = 0.60;
export const QUALITY_STEP = 0.05;

export interface TargetDimensions {
  width: number;
  height: number;
  scaled: boolean;
}

export interface OptimizationResult {
  file: File;
  originalSize: number;
  optimizedSize: number;
  width: number;
  height: number;
  quality: number;
  fallback: boolean;
  error?: string;
}

/**
 * Calculates resized dimensions keeping aspect ratio so longest side <= maxSide.
 * Never upscales images where both width and height are already <= maxSide.
 */
export function calculateTargetDimensions(
  width: number,
  height: number,
  maxSide: number = MAX_LONGEST_SIDE,
): TargetDimensions {
  if (width <= 0 || height <= 0) {
    return { width: Math.max(0, width), height: Math.max(0, height), scaled: false };
  }
  const longest = Math.max(width, height);
  if (longest <= maxSide) {
    return { width, height, scaled: false };
  }
  const ratio = maxSide / longest;
  return {
    width: Math.max(1, Math.round(width * ratio)),
    height: Math.max(1, Math.round(height * ratio)),
    scaled: true,
  };
}

/**
 * Generates decreasing JPEG compression qualities from initial down to minQuality.
 */
export function getQualitySteps(
  initialQuality: number = INITIAL_JPEG_QUALITY,
  minQuality: number = MIN_JPEG_QUALITY,
  step: number = QUALITY_STEP,
): number[] {
  const steps: number[] = [];
  let current = initialQuality;
  while (current >= minQuality - 0.001) {
    steps.push(Math.round(current * 100) / 100);
    current -= step;
  }
  const last = steps[steps.length - 1];
  if (last !== undefined && last > minQuality) {
    steps.push(minQuality);
  }
  return steps;
}

/**
 * Formats byte counts into human-readable strings (e.g. "340 KB", "4.2 MB").
 */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Helper to encode canvas to a Blob with specific quality and MIME type.
 */
export async function canvasToBlob(
  canvas: HTMLCanvasElement | OffscreenCanvas,
  type: string,
  quality: number,
): Promise<Blob> {
  if ('convertToBlob' in canvas && typeof canvas.convertToBlob === 'function') {
    return await canvas.convertToBlob({ type, quality });
  }
  if ('toBlob' in canvas && typeof canvas.toBlob === 'function') {
    return new Promise<Blob>((resolve, reject) => {
      (canvas as HTMLCanvasElement).toBlob(
        (blob) => {
          if (blob) resolve(blob);
          else reject(new Error('Canvas toBlob returned null'));
        },
        type,
        quality,
      );
    });
  }
  throw new Error('Canvas blob conversion not supported in this environment');
}

/**
 * Optimizes a photo File in the browser:
 * - Decodes using createImageBitmap with imageOrientation: 'from-image' (EXIF correction).
 * - Downscales to longest side <= 1600 px.
 * - Re-encodes as JPEG iterating quality steps (0.82 down to 0.60) until size <= 500 KB.
 * - Returns the optimized File, ready for FormData submission.
 */
export async function optimizePhotoFile(
  file: File,
  options?: {
    maxSide?: number;
    targetBytes?: number;
    initialQuality?: number;
    minQuality?: number;
    step?: number;
  },
): Promise<OptimizationResult> {
  const maxSide = options?.maxSide ?? MAX_LONGEST_SIDE;
  const targetBytes = options?.targetBytes ?? TARGET_MAX_BYTES;
  const initialQuality = options?.initialQuality ?? INITIAL_JPEG_QUALITY;
  const minQuality = options?.minQuality ?? MIN_JPEG_QUALITY;
  const step = options?.step ?? QUALITY_STEP;

  const originalSize = file.size;

  try {
    let sourceWidth = 0;
    let sourceHeight = 0;
    let drawSource: ImageBitmap | HTMLImageElement;

    if (typeof createImageBitmap === 'function') {
      try {
        const bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' });
        sourceWidth = bitmap.width;
        sourceHeight = bitmap.height;
        drawSource = bitmap;
      } catch {
        // Fallback to Image element if createImageBitmap with options failed
        drawSource = await loadImageElement(file);
        sourceWidth = drawSource.naturalWidth || drawSource.width;
        sourceHeight = drawSource.naturalHeight || drawSource.height;
      }
    } else {
      drawSource = await loadImageElement(file);
      sourceWidth = drawSource.naturalWidth || drawSource.width;
      sourceHeight = drawSource.naturalHeight || drawSource.height;
    }

    const dims = calculateTargetDimensions(sourceWidth, sourceHeight, maxSide);

    // Create canvas
    let canvas: HTMLCanvasElement | OffscreenCanvas;
    let ctx: CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D | null = null;

    if (typeof OffscreenCanvas !== 'undefined') {
      canvas = new OffscreenCanvas(dims.width, dims.height);
      ctx = canvas.getContext('2d');
    } else if (typeof document !== 'undefined') {
      canvas = document.createElement('canvas');
      canvas.width = dims.width;
      canvas.height = dims.height;
      ctx = canvas.getContext('2d');
    } else {
      throw new Error('Canvas not available in current environment');
    }

    if (!ctx) {
      throw new Error('Could not obtain canvas 2D rendering context');
    }

    // High quality downscaling
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(drawSource as CanvasImageSource, 0, 0, dims.width, dims.height);

    // Free ImageBitmap if created
    if ('close' in drawSource && typeof drawSource.close === 'function') {
      drawSource.close();
    }

    // Iterative quality loop
    const qualitySteps = getQualitySteps(initialQuality, minQuality, step);
    let chosenBlob: Blob | null = null;
    let chosenQuality = initialQuality;

    for (const q of qualitySteps) {
      chosenQuality = q;
      const blob = await canvasToBlob(canvas, 'image/jpeg', q);
      chosenBlob = blob;
      if (blob.size <= targetBytes) {
        break;
      }
    }

    if (!chosenBlob) {
      throw new Error('Failed to encode image to JPEG blob');
    }

    // Generate output filename preserving base name with .jpg extension
    const baseName = file.name.replace(/\.[^/.]+$/, '');
    const outName = `${baseName || 'maintenance_photo'}.jpg`;
    const optimizedFile = new File([chosenBlob], outName, {
      type: 'image/jpeg',
      lastModified: Date.now(),
    });

    return {
      file: optimizedFile,
      originalSize,
      optimizedSize: optimizedFile.size,
      width: dims.width,
      height: dims.height,
      quality: chosenQuality,
      fallback: false,
    };
  } catch (err: any) {
    // Fallback path: If processing fails (e.g. HEIC, unsupported format, or environment limitations)
    if (file.size <= HARD_LIMIT_BYTES) {
      return {
        file,
        originalSize,
        optimizedSize: file.size,
        width: 0,
        height: 0,
        quality: 1.0,
        fallback: true,
        error: err?.message || 'Processing failed; using original image',
      };
    }
    throw new Error(
      `Photo could not be processed and exceeds the 4 MB upload limit (${formatFileSize(file.size)}). Please choose a standard JPEG or PNG photo.`,
    );
  }
}

function loadImageElement(file: File): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    if (typeof Image === 'undefined') {
      return reject(new Error('HTMLImageElement not available'));
    }
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      URL.revokeObjectURL(url);
      resolve(img);
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error('Failed to decode image with HTMLImageElement'));
    };
    img.src = url;
  });
}
