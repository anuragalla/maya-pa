import { useState } from "react";
import { ChevronDown, ChevronRight, AlertCircle } from "lucide-react";
import { Streamdown } from "streamdown";

import type { DocumentRow } from "@/lib/documents";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface DocSummaryProps {
  document: DocumentRow;
}

interface LabMarker {
  name: string;
  value: string | number | null;
  unit: string | null;
  range: string | null;
}

interface PrescriptionStructured {
  drug?: string;
  dose?: string;
  frequency?: string;
  fill_date?: string;
  days_supply?: string | number;
  expiry_alert_date?: string;
}

function parseLabMarkers(structured: Record<string, unknown>): LabMarker[] {
  const raw = structured.markers;
  if (!Array.isArray(raw)) return [];
  return raw.flatMap((entry): LabMarker[] => {
    if (!entry || typeof entry !== "object") return [];
    const obj = entry as Record<string, unknown>;
    const name = typeof obj.name === "string" ? obj.name : "";
    if (!name) return [];
    const value =
      typeof obj.value === "string" || typeof obj.value === "number"
        ? obj.value
        : null;
    const unit = typeof obj.unit === "string" ? obj.unit : null;
    const range = typeof obj.range === "string" ? obj.range : null;
    return [{ name, value, unit, range }];
  });
}

function parsePrescription(
  structured: Record<string, unknown>,
): PrescriptionStructured {
  const pick = (k: string): string | undefined => {
    const v = structured[k];
    if (typeof v === "string") return v;
    if (typeof v === "number") return String(v);
    return undefined;
  };
  const days = structured.days_supply;
  return {
    drug: pick("drug"),
    dose: pick("dose"),
    frequency: pick("frequency"),
    fill_date: pick("fill_date"),
    days_supply:
      typeof days === "string" || typeof days === "number" ? days : undefined,
    expiry_alert_date: pick("expiry_alert_date"),
  };
}

function LabTable({ markers }: { markers: LabMarker[] }) {
  if (markers.length === 0) return null;
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Value</TableHead>
          <TableHead>Unit</TableHead>
          <TableHead>Range</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {markers.map((m, i) => (
          <TableRow key={`${m.name}-${i}`}>
            <TableCell className="font-medium">{m.name}</TableCell>
            <TableCell>{m.value ?? "—"}</TableCell>
            <TableCell className="text-muted-foreground">
              {m.unit ?? ""}
            </TableCell>
            <TableCell className="text-muted-foreground">
              {m.range ?? ""}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function PrescriptionBlock({ data }: { data: PrescriptionStructured }) {
  const rows: Array<[string, string | undefined]> = [
    ["Drug", data.drug],
    ["Dose", data.dose],
    ["Frequency", data.frequency],
    ["Fill date", data.fill_date],
    [
      "Days supply",
      data.days_supply != null ? String(data.days_supply) : undefined,
    ],
    ["Expiry alert", data.expiry_alert_date],
  ];
  return (
    <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-2 text-sm">
      {rows.map(([label, value]) => (
        <div key={label} className="contents">
          <dt className="text-muted-foreground">{label}</dt>
          <dd className="font-medium">{value ?? "—"}</dd>
        </div>
      ))}
    </dl>
  );
}

function StructuredSection({ document }: { document: DocumentRow }) {
  if (document.doc_type === "lab_result") {
    const markers = parseLabMarkers(document.structured);
    if (markers.length === 0) return null;
    return (
      <section>
        <h4 className="mb-2 text-sm font-medium">Markers</h4>
        <LabTable markers={markers} />
      </section>
    );
  }

  if (document.doc_type === "prescription") {
    const data = parsePrescription(document.structured);
    return (
      <section>
        <h4 className="mb-2 text-sm font-medium">Prescription</h4>
        <PrescriptionBlock data={data} />
      </section>
    );
  }

  const keys = Object.keys(document.structured);
  if (keys.length === 0) return null;
  return (
    <CollapsibleBlock label="Structured data">
      <pre className="max-h-80 overflow-auto rounded-md bg-muted p-3 font-mono text-xs">
        {JSON.stringify(document.structured, null, 2)}
      </pre>
    </CollapsibleBlock>
  );
}

function CollapsibleBlock({
  label,
  children,
  defaultOpen = false,
}: {
  label: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setOpen((v) => !v)}
        className="-ml-2"
      >
        {open ? (
          <ChevronDown className="size-3.5" />
        ) : (
          <ChevronRight className="size-3.5" />
        )}
        {label}
      </Button>
      {open && <div className="mt-2">{children}</div>}
    </section>
  );
}

function StatusBanner({ document }: { document: DocumentRow }) {
  if (document.status === "ready") return null;
  if (document.status === "failed") {
    return (
      <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
        <AlertCircle className="mt-0.5 size-4 shrink-0" />
        <div>
          <p className="font-medium">Processing failed</p>
          {document.error_message && (
            <p className="mt-0.5 text-xs opacity-80">
              {document.error_message}
            </p>
          )}
        </div>
      </div>
    );
  }
  const msg =
    document.status === "cancelled"
      ? "Processing was cancelled."
      : "Still processing — summary will appear here.";
  return (
    <div className="rounded-md border border-border bg-muted/40 p-3 text-sm text-muted-foreground">
      {msg}
    </div>
  );
}

interface ExtractedTextLike {
  extracted_text?: unknown;
}

function extractedText(document: DocumentRow): string | null {
  const value = (document.structured as ExtractedTextLike).extracted_text;
  return typeof value === "string" && value.trim().length > 0 ? value : null;
}

export function DocSummary({ document }: DocSummaryProps) {
  const rawText = extractedText(document);

  return (
    <ScrollArea className="h-full">
      <div className="flex flex-col gap-5 p-4">
        <StatusBanner document={document} />

        {document.tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {document.tags.map((tag) => (
              <Badge key={tag} variant="tag">
                {tag}
              </Badge>
            ))}
          </div>
        )}

        {document.summary_detailed ? (
          <div className="prose prose-sm dark:prose-invert max-w-none">
            <Streamdown>{document.summary_detailed}</Streamdown>
          </div>
        ) : document.status === "ready" ? (
          <p className="text-sm text-muted-foreground">
            No summary available for this document.
          </p>
        ) : null}

        <StructuredSection document={document} />

        {rawText && (
          <>
            <Separator />
            <CollapsibleBlock label="Show raw text">
              <ScrollArea className="h-60 rounded-md border border-border bg-muted/30">
                <pre className="whitespace-pre-wrap p-3 font-mono text-xs">
                  {rawText}
                </pre>
              </ScrollArea>
            </CollapsibleBlock>
          </>
        )}
      </div>
    </ScrollArea>
  );
}
