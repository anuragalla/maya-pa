import { FileBadge, FileText, Image as ImageIcon, type LucideIcon } from "lucide-react";

export const ALLOWED_MIME_TYPES = [
  "application/pdf",
  "image/jpeg",
  "image/png",
  "image/webp",
  "image/heic",
  "image/heif",
] as const;
export type AllowedMime = (typeof ALLOWED_MIME_TYPES)[number];

export const MAX_UPLOAD_SIZE = 25 * 1024 * 1024; // 25 MB
export const ACCEPT_ATTRIBUTE = ".pdf,.jpg,.jpeg,.png,.webp,.heic,.heif";

export const DOC_TYPES = [
  "lab_result",
  "prescription",
  "insurance",
  "imaging",
  "visit_note",
  "vaccine",
  "other",
] as const;
export type DocType = (typeof DOC_TYPES)[number];

export const DOC_STATUS = [
  "pending",
  "uploaded",
  "processing",
  "ready",
  "failed",
  "cancelled",
] as const;
export type DocStatus = (typeof DOC_STATUS)[number];

export const DOC_STREAM_STAGES = [
  "reading",
  "context",
  "summarizing",
  "ready",
  "failed",
  "cancelled",
] as const;
export type DocStreamStage = (typeof DOC_STREAM_STAGES)[number];

export interface DocumentRow {
  document_id: string;
  doc_type: DocType;
  status: DocStatus;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  tags: string[];
  summary_detailed: string | null;
  structured: Record<string, unknown>;
  uploaded_at: string;
  processed_at: string | null;
  expiry_alert_date: string | null;
  error_message: string | null;
}

export interface DocStreamEvent {
  stage: DocStreamStage;
  label: string;
  payload?: Partial<DocumentRow>;
}

export interface DocUploadResponse {
  document_id: string;
  status: DocStatus;
}

/**
 * Per-message attachment shape returned by `/stream/history` and attached to
 * locally-sent user messages. Slimmer than `DocumentRow` — it's just the hints
 * a DocCard needs for first paint before its own TanStack Query fetch lands.
 */
export interface MessageDocAttachment {
  document_id: string;
  original_filename: string;
  doc_type: DocType;
  status: DocStatus;
  summary_detailed?: string | null;
}

export function mimeIcon(mime: string): LucideIcon {
  if (mime === "application/pdf") return FileText;
  if (mime.startsWith("image/")) return ImageIcon;
  return FileBadge;
}

export function formatFileSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(1)} ${units[unit]}`;
}

export function isAllowedMime(mime: string): mime is AllowedMime {
  return (ALLOWED_MIME_TYPES as readonly string[]).includes(mime);
}

export type FileValidation = { ok: true } | { ok: false; reason: string };

export function validateFile(file: File): FileValidation {
  if (file.size > MAX_UPLOAD_SIZE) {
    return { ok: false, reason: "File too large (max 25 MB)" };
  }
  if (file.size === 0) {
    return { ok: false, reason: "File is empty" };
  }
  if (!isAllowedMime(file.type)) {
    return { ok: false, reason: `Unsupported file type: ${file.type || "unknown"}` };
  }
  return { ok: true };
}

/**
 * Best-effort runtime parse for SSE event JSON. Returns null on malformed input
 * so the SSE consumer can drop the event without crashing the stream.
 */
export function parseDocStreamEvent(raw: string): DocStreamEvent | null {
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return null;
    const obj = parsed as Record<string, unknown>;
    const stage = obj.stage;
    if (typeof stage !== "string" || !(DOC_STREAM_STAGES as readonly string[]).includes(stage)) {
      return null;
    }
    const label = typeof obj.label === "string" ? obj.label : "";
    const payload =
      obj.payload && typeof obj.payload === "object"
        ? (obj.payload as Partial<DocumentRow>)
        : undefined;
    return { stage: stage as DocStreamStage, label, payload };
  } catch {
    return null;
  }
}
