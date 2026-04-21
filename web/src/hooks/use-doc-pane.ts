import { useCallback, useMemo } from "react";
import { useNavigate, useSearch } from "@tanstack/react-router";

export type DocPaneTab = "preview" | "summary";

export interface DocPaneSearch {
  doc?: string;
  tab?: DocPaneTab;
}

export interface DocPaneState {
  open: boolean;
  doc: string | null;
  tab: DocPaneTab;
  openDoc: (id: string, tab?: DocPaneTab) => void;
  setTab: (tab: DocPaneTab) => void;
  close: () => void;
}

const VALID_TABS: readonly DocPaneTab[] = ["preview", "summary"];

function readSearch(raw: unknown): DocPaneSearch {
  if (!raw || typeof raw !== "object") return {};
  const obj = raw as Record<string, unknown>;
  const doc = typeof obj.doc === "string" && obj.doc.length > 0 ? obj.doc : undefined;
  const tabRaw = obj.tab;
  const tab =
    typeof tabRaw === "string" && (VALID_TABS as readonly string[]).includes(tabRaw)
      ? (tabRaw as DocPaneTab)
      : undefined;
  return { doc, tab };
}

/**
 * URL-synced doc pane state via TanStack Router search params:
 * `?doc=<id>&tab=preview|summary`. Uses `strict: false` so the hook works
 * from any route without coupling to a route's typed search schema.
 */
export function useDocPane(): DocPaneState {
  const navigate = useNavigate();
  const search = useSearch({ strict: false });
  const parsed = useMemo(() => readSearch(search), [search]);

  const doc = parsed.doc ?? null;
  const tab: DocPaneTab = parsed.tab ?? "summary";
  const open = doc !== null;

  const openDoc = useCallback(
    (id: string, nextTab: DocPaneTab = "summary") => {
      void navigate({
        to: ".",
        search: (prev: Record<string, unknown> | undefined) => ({
          ...(prev ?? {}),
          doc: id,
          tab: nextTab,
        }),
        replace: false,
      });
    },
    [navigate],
  );

  const setTab = useCallback(
    (nextTab: DocPaneTab) => {
      void navigate({
        to: ".",
        search: (prev: Record<string, unknown> | undefined) => ({
          ...(prev ?? {}),
          tab: nextTab,
        }),
        replace: true,
      });
    },
    [navigate],
  );

  const close = useCallback(() => {
    void navigate({
      to: ".",
      search: (prev: Record<string, unknown> | undefined) => {
        const next = { ...(prev ?? {}) };
        delete next.doc;
        delete next.tab;
        return next;
      },
      replace: false,
    });
  }, [navigate]);

  return { open, doc, tab, openDoc, setTab, close };
}
