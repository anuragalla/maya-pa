/**
 * Parses the Vercel AI SDK v1 data-stream protocol that our FastAPI emits.
 *
 * Each line is `TYPE:JSON\n`:
 *   0:"text chunk"
 *   b:{"toolCallId","toolName","args"}
 *   a:{"toolCallId","result"}
 *   2:[{"type":"suggestions","items":[...]}, ...]   (custom data parts)
 *   e:{"finishReason","usage"}                       (step finish)
 *   d:{"finishReason","usage"}                       (message finish)
 *
 * Designed for streaming: handles partial lines across chunks.
 */

export type StreamEvent =
  | { type: "text"; value: string }
  | { type: "tool-call"; toolCallId: string; toolName: string; args: unknown }
  | { type: "tool-result"; toolCallId: string; result: unknown }
  | { type: "data"; items: unknown[] }
  | { type: "step-finish"; finishReason?: string }
  | { type: "message-finish"; finishReason?: string };

export async function* parseDataStream(
  response: Response,
  signal?: AbortSignal,
): AsyncGenerator<StreamEvent, void, unknown> {
  if (!response.body) return;
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      if (signal?.aborted) break;
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let idx: number;
      while ((idx = buffer.indexOf("\n")) !== -1) {
        const line = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 1);
        if (!line) continue;
        const event = parseLine(line);
        if (event) yield event;
      }
    }
    // Flush any trailing partial line
    if (buffer) {
      const event = parseLine(buffer);
      if (event) yield event;
    }
  } finally {
    try {
      reader.releaseLock();
    } catch {
      /* noop */
    }
  }
}

function parseLine(line: string): StreamEvent | null {
  const colon = line.indexOf(":");
  if (colon < 1) return null;
  const code = line.slice(0, colon);
  const payload = line.slice(colon + 1);
  let parsed: unknown;
  try {
    parsed = JSON.parse(payload);
  } catch {
    return null;
  }
  switch (code) {
    case "0":
      return typeof parsed === "string" ? { type: "text", value: parsed } : null;
    case "b": {
      const p = parsed as { toolCallId?: string; toolName?: string; args?: unknown };
      if (!p.toolCallId || !p.toolName) return null;
      return {
        type: "tool-call",
        toolCallId: p.toolCallId,
        toolName: p.toolName,
        args: p.args ?? {},
      };
    }
    case "a": {
      const p = parsed as { toolCallId?: string; result?: unknown };
      if (!p.toolCallId) return null;
      return { type: "tool-result", toolCallId: p.toolCallId, result: p.result ?? null };
    }
    case "2":
      return Array.isArray(parsed) ? { type: "data", items: parsed } : null;
    case "e": {
      const p = parsed as { finishReason?: string };
      return { type: "step-finish", finishReason: p.finishReason };
    }
    case "d": {
      const p = parsed as { finishReason?: string };
      return { type: "message-finish", finishReason: p.finishReason };
    }
    default:
      return null;
  }
}
