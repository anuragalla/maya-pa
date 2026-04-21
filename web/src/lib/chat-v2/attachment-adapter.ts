import type {
  AttachmentAdapter,
  PendingAttachment,
  CompleteAttachment,
} from "@assistant-ui/react";
import { nanoid } from "nanoid";

import { ACCEPT_ATTRIBUTE } from "@/lib/documents";

/**
 * Defers real upload to the runtime's onNew. This adapter just stages the File
 * on the composer; the runtime reads `attachment.file` during send and POSTs
 * to /api/v1/documents there. Simpler than coupling upload to adapter state.
 */
export class DeferredUploadAttachmentAdapter implements AttachmentAdapter {
  accept = ACCEPT_ATTRIBUTE;

  async add({ file }: { file: File }): Promise<PendingAttachment> {
    return {
      id: nanoid(),
      type: "document",
      name: file.name,
      contentType: file.type,
      file,
      status: { type: "requires-action", reason: "composer-send" },
    };
  }

  async send(attachment: PendingAttachment): Promise<CompleteAttachment> {
    // Preserve the File on the completed attachment so onNew can upload it.
    return {
      id: attachment.id,
      type: attachment.type,
      name: attachment.name,
      contentType: attachment.contentType,
      file: attachment.file,
      content: [
        {
          type: "file",
          filename: attachment.name,
          mimeType: attachment.contentType ?? "application/octet-stream",
          // Placeholder — the actual bytes live on attachment.file, which the
          // runtime reads during onNew to upload.
          data: "",
        },
      ],
      status: { type: "complete" },
    };
  }

  async remove(): Promise<void> {
    // No server cleanup at stage time — the document row is only created on send.
  }
}
