import { describe, it, expect, vi } from 'vitest';
import {
  TIMEOUTS,
  TIMEOUT_MESSAGES,
  NetworkTimeoutError,
  getTimeoutForRequest,
  createTimeoutFetch,
} from './timeouts';

describe('Central Timeouts configuration', () => {
  it('defines the required timeout constants', () => {
    expect(TIMEOUTS.CONNECT_MS).toBe(5000);
    expect(TIMEOUTS.READ_MS).toBe(10000);
    expect(TIMEOUTS.WRITE_MS).toBe(20000);
    expect(TIMEOUTS.STORAGE_DOWNLOAD_MS).toBe(20000);
    expect(TIMEOUTS.STORAGE_UPLOAD_MS).toBe(30000);
    expect(TIMEOUTS.EDGE_FUNCTION_MS).toBe(30000);
  });

  it('defines the user-friendly timeout messages', () => {
    expect(TIMEOUT_MESSAGES.READ).toBe(
      'The server is taking too long to respond. Check your connection and try again.'
    );
    expect(TIMEOUT_MESSAGES.WRITE).toBe(
      'The result is unknown. Refresh to check before trying again.'
    );
  });
});

describe('getTimeoutForRequest', () => {
  it('assigns 10s to GET and HEAD reads', () => {
    expect(getTimeoutForRequest('https://xyz.supabase.co/rest/v1/rooms')).toBe(TIMEOUTS.READ_MS);
    expect(getTimeoutForRequest('https://xyz.supabase.co/rest/v1/rooms', { method: 'GET' })).toBe(
      TIMEOUTS.READ_MS
    );
    expect(getTimeoutForRequest('https://xyz.supabase.co/rest/v1/rooms', { method: 'HEAD' })).toBe(
      TIMEOUTS.READ_MS
    );
  });

  it('assigns 20s to mutating table writes and RPC actions', () => {
    expect(getTimeoutForRequest('https://xyz.supabase.co/rest/v1/rooms', { method: 'POST' })).toBe(
      TIMEOUTS.WRITE_MS
    );
    expect(getTimeoutForRequest('https://xyz.supabase.co/rest/v1/rooms?id=eq.1', { method: 'PATCH' })).toBe(
      TIMEOUTS.WRITE_MS
    );
    expect(getTimeoutForRequest('https://xyz.supabase.co/rest/v1/rooms?id=eq.1', { method: 'DELETE' })).toBe(
      TIMEOUTS.WRITE_MS
    );
    expect(getTimeoutForRequest('https://xyz.supabase.co/rest/v1/rpc/approve_application', { method: 'POST' })).toBe(
      TIMEOUTS.WRITE_MS
    );
  });

  it('assigns 20s to storage download and 30s to storage upload', () => {
    expect(getTimeoutForRequest('https://xyz.supabase.co/storage/v1/object/photos/abc.jpg', { method: 'GET' })).toBe(
      TIMEOUTS.STORAGE_DOWNLOAD_MS
    );
    expect(getTimeoutForRequest('https://xyz.supabase.co/storage/v1/object/photos/abc.jpg', { method: 'POST' })).toBe(
      TIMEOUTS.STORAGE_UPLOAD_MS
    );
    expect(getTimeoutForRequest('https://xyz.supabase.co/storage/v1/object/photos/abc.jpg', { method: 'PUT' })).toBe(
      TIMEOUTS.STORAGE_UPLOAD_MS
    );
  });

  it('assigns 30s to edge functions', () => {
    expect(getTimeoutForRequest('https://xyz.supabase.co/functions/v1/admin-users', { method: 'POST' })).toBe(
      TIMEOUTS.EDGE_FUNCTION_MS
    );
  });
});

describe('createTimeoutFetch', () => {
  it('delegates successful requests and returns response', async () => {
    const mockResponse = new Response(JSON.stringify({ ok: true }), { status: 200 });
    const customFetch = vi.fn().mockResolvedValue(mockResponse);
    const timeoutFetch = createTimeoutFetch(customFetch);

    const res = await timeoutFetch('https://example.com/api/test', { method: 'GET' });
    expect(res).toBe(mockResponse);
    expect(customFetch).toHaveBeenCalledTimes(1);
  });

  it('throws NetworkTimeoutError when timed out', async () => {
    const customFetch = vi.fn().mockImplementation((_url, init) => {
      return new Promise((_, reject) => {
        if (init?.signal) {
          init.signal.addEventListener('abort', () => {
            const err = new Error('The operation was aborted');
            err.name = 'TimeoutError';
            reject(err);
          });
        }
      });
    });

    const timeoutFetch = createTimeoutFetch(customFetch);

    // Call with a very short timeout signal by mocking getTimeoutForRequest or letting TimeoutError occur
    await expect(
      timeoutFetch('https://example.com/api/test', {
        signal: AbortSignal.timeout(20),
      })
    ).rejects.toThrow(NetworkTimeoutError);
  });

  it('honors caller-supplied AbortSignal cancellation', async () => {
    const controller = new AbortController();
    const customFetch = vi.fn().mockImplementation((_url, init) => {
      return new Promise((_, reject) => {
        if (init?.signal) {
          init.signal.addEventListener('abort', () => {
            const err = new Error('The operation was aborted');
            err.name = 'AbortError';
            reject(err);
          });
        }
      });
    });

    const timeoutFetch = createTimeoutFetch(customFetch);
    const promise = timeoutFetch('https://example.com/api/test', {
      signal: controller.signal,
    });

    controller.abort();

    await expect(promise).rejects.toThrow('The operation was aborted');
  });

  it('coalesces concurrent identical GET requests into one network call', async () => {
    let callCount = 0;
    const customFetch = vi.fn().mockImplementation(async () => {
      callCount++;
      await new Promise((r) => setTimeout(r, 20));
      return new Response(JSON.stringify({ value: 42 }), { status: 200 });
    });

    const timeoutFetch = createTimeoutFetch(customFetch);

    // Launch two identical GET requests at the exact same moment
    const [res1, res2] = await Promise.all([
      timeoutFetch('https://example.com/api/data', { method: 'GET' }),
      timeoutFetch('https://example.com/api/data', { method: 'GET' }),
    ]);

    expect(customFetch).toHaveBeenCalledTimes(1);
    expect(callCount).toBe(1);

    const data1 = await res1.json();
    const data2 = await res2.json();
    expect(data1).toEqual({ value: 42 });
    expect(data2).toEqual({ value: 42 });
  });

  it('does not coalesce mutating POST/PUT/DELETE writes', async () => {
    const customFetch = vi.fn().mockImplementation(async () => {
      await new Promise((r) => setTimeout(r, 10));
      return new Response(JSON.stringify({ ok: true }), { status: 200 });
    });

    const timeoutFetch = createTimeoutFetch(customFetch);

    await Promise.all([
      timeoutFetch('https://example.com/api/mutate', { method: 'POST', body: '{"a":1}' }),
      timeoutFetch('https://example.com/api/mutate', { method: 'POST', body: '{"a":1}' }),
    ]);

    expect(customFetch).toHaveBeenCalledTimes(2);
  });

  it('does not cache or lock on network errors', async () => {
    let callCount = 0;
    const customFetch = vi.fn().mockImplementation(async () => {
      callCount++;
      throw new Error('Connection failed');
    });

    const timeoutFetch = createTimeoutFetch(customFetch);

    await expect(timeoutFetch('https://example.com/api/failing', { method: 'GET' })).rejects.toThrow(
      'Connection failed'
    );

    // Subsequent call executes again and does not return a cached error
    await expect(timeoutFetch('https://example.com/api/failing', { method: 'GET' })).rejects.toThrow(
      'Connection failed'
    );

    expect(callCount).toBe(2);
  });
});
