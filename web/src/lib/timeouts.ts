/**
 * Central timeout constants and fetch timeout wrappers for R\u00c9SIVO Web Portal.
 */

export const TIMEOUTS = {
  CONNECT_MS: 5000,
  READ_MS: 10000,
  WRITE_MS: 20000,
  STORAGE_DOWNLOAD_MS: 20000,
  STORAGE_UPLOAD_MS: 30000,
  EDGE_FUNCTION_MS: 30000,
} as const;

export const TIMEOUT_MESSAGES = {
  READ: 'The server is taking too long to respond. Check your connection and try again.',
  WRITE: 'The result is unknown. Refresh to check before trying again.',
} as const;

export class NetworkTimeoutError extends Error {
  isWrite: boolean;

  constructor(message?: string, isWrite = false) {
    super(message ?? (isWrite ? TIMEOUT_MESSAGES.WRITE : TIMEOUT_MESSAGES.READ));
    this.name = 'NetworkTimeoutError';
    this.isWrite = isWrite;
  }
}

/**
 * Determine the appropriate timeout in milliseconds based on URL and HTTP method.
 */
export function getTimeoutForRequest(input: RequestInfo | URL, init?: RequestInit): number {
  const method = (
    init?.method ||
    (typeof input === 'object' && 'method' in input ? (input as Request).method : 'GET')
  ).toUpperCase();
  const urlStr = typeof input === 'string' ? input : input instanceof URL ? input.toString() : (input as Request).url;

  // Storage upload
  if (urlStr.includes('/storage/v1/object') && (method === 'POST' || method === 'PUT')) {
    return TIMEOUTS.STORAGE_UPLOAD_MS;
  }
  // Edge Functions
  if (urlStr.includes('/functions/v1/')) {
    return TIMEOUTS.EDGE_FUNCTION_MS;
  }
  // Storage download / signed URLs
  if (urlStr.includes('/storage/v1/')) {
    return TIMEOUTS.STORAGE_DOWNLOAD_MS;
  }
  // Database mutations / RPCs
  if (
    method === 'POST' ||
    method === 'PUT' ||
    method === 'PATCH' ||
    method === 'DELETE' ||
    urlStr.includes('/rest/v1/rpc/')
  ) {
    return TIMEOUTS.WRITE_MS;
  }
  // Default read
  return TIMEOUTS.READ_MS;
}

/**
 * Creates a custom fetch wrapper that applies AbortSignal.timeout based on request type.
 */
export function createTimeoutFetch(customFetch: typeof fetch = fetch): typeof fetch {
  return async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const timeoutMs = getTimeoutForRequest(input, init);
    const timeoutSignal = AbortSignal.timeout(timeoutMs);

    let signal: AbortSignal;
    if (init?.signal) {
      signal = (typeof AbortSignal.any === 'function')
        ? AbortSignal.any([init.signal, timeoutSignal])
        : timeoutSignal;
    } else {
      signal = timeoutSignal;
    }

    try {
      return await customFetch(input, { ...init, signal });
    } catch (err: any) {
      if (err?.name === 'TimeoutError' || (err?.name === 'AbortError' && timeoutSignal.aborted)) {
        const isWrite = getTimeoutForRequest(input, init) === TIMEOUTS.WRITE_MS;
        throw new NetworkTimeoutError(undefined, isWrite);
      }
      throw err;
    }
  };
}
