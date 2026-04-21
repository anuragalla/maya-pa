/**
 * Read SSE frames from a `Response.body` stream.
 *
 * We use fetch + ReadableStream instead of native `EventSource` because
 * EventSource can't send custom headers (we need `X-Phone-Number`).
 *
 * Yields one frame per logical SSE message. Handles:
 *  - CRLF line endings
 *  - Comment lines (`:` heartbeat) — dropped
 *  - Multiline `data:` concatenation per the spec
 *  - Aborts cleanly when the caller cancels the signal
 */

export interface SseFrame {
  event: string;
  data: string;
}

export async function* readSseFrames(
  response: Response,
  signal: AbortSignal,
): AsyncIterable<SseFrame> {
  if (!response.ok || !response.body) return;
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (!signal.aborted) {
      const { done, value } = await reader.read();
      if (done) return;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split(/\r?\n\r?\n/);
      buffer = parts.pop() ?? "";
      for (const frame of parts) {
        let event = "message";
        let data = "";
        for (const line of frame.split(/\r?\n/)) {
          if (!line || line.startsWith(":")) continue;
          if (line.startsWith("event:")) event = line.slice(6).trim();
          else if (line.startsWith("data:")) data += line.slice(5).trim();
        }
        if (data) yield { event, data };
      }
    }
  } finally {
    try {
      reader.releaseLock();
    } catch {
      // already released
    }
  }
}
