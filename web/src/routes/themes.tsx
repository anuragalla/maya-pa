import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";

// Font imports
import "@fontsource-variable/plus-jakarta-sans";
import "@fontsource-variable/inter";
import "@fontsource-variable/dm-sans";
import "@fontsource/dm-mono";
import "@fontsource-variable/outfit";
import "@fontsource/fira-code";
import "@fontsource-variable/nunito-sans";
import "@fontsource-variable/source-sans-3";
import "@fontsource/source-code-pro";
import "@fontsource-variable/fraunces";
import "@fontsource-variable/newsreader";
import "@fontsource-variable/instrument-sans";
import "@fontsource/ibm-plex-mono";
import "@fontsource/jetbrains-mono";
import "@fontsource-variable/geist";
import "@fontsource-variable/geist-mono";

export const Route = createFileRoute("/themes")({
  component: ThemePreview,
});

type ThemeVars = Record<string, string>;

interface Palette {
  name: string;
  description: string;
  dark: ThemeVars;
  light: ThemeVars;
}

interface FontCombo {
  name: string;
  description: string;
  heading: string;
  body: string;
  mono: string;
}

const fontCombos: FontCombo[] = [
  {
    name: "Jakarta",
    description: "Friendly geometric — current stack",
    heading: "'Plus Jakarta Sans Variable', sans-serif",
    body: "'Plus Jakarta Sans Variable', sans-serif",
    mono: "'JetBrains Mono', monospace",
  },
  {
    name: "Inter",
    description: "Clean and confident — gold standard UI",
    heading: "'Inter Variable', sans-serif",
    body: "'Inter Variable', sans-serif",
    mono: "'JetBrains Mono', monospace",
  },
  {
    name: "Fraunces + DM Sans",
    description: "Premium serif headlines — boutique wellness",
    heading: "'Fraunces Variable', serif",
    body: "'DM Sans Variable', sans-serif",
    mono: "'DM Mono', monospace",
  },
  {
    name: "Outfit",
    description: "Geometric minimalist — airy health-tech",
    heading: "'Outfit Variable', sans-serif",
    body: "'Outfit Variable', sans-serif",
    mono: "'Fira Code', monospace",
  },
  {
    name: "Nunito + Source Sans",
    description: "Trustworthy and calming — like a good doctor",
    heading: "'Nunito Sans Variable', sans-serif",
    body: "'Source Sans 3 Variable', sans-serif",
    mono: "'Source Code Pro', monospace",
  },
  {
    name: "Newsreader + Instrument",
    description: "Editorial health — longevity journal feel",
    heading: "'Newsreader Variable', serif",
    body: "'Instrument Sans Variable', sans-serif",
    mono: "'IBM Plex Mono', monospace",
  },
  {
    name: "Geist",
    description: "Vercel's typeface — sharp, technical, modern",
    heading: "'Geist Variable', sans-serif",
    body: "'Geist Variable', sans-serif",
    mono: "'Geist Mono Variable', monospace",
  },
];

const palettes: Record<string, Palette> = {
  current: {
    name: "Current",
    description: "Existing theme — low contrast cards, muted readability",
    dark: {
      "--background": "#1A1025",
      "--foreground": "#F1E8FF",
      "--card": "#2D2040",
      "--card-foreground": "#F1E8FF",
      "--primary": "#FB7185",
      "--primary-foreground": "#FFFFFF",
      "--secondary": "#2D2040",
      "--secondary-foreground": "#F1E8FF",
      "--muted": "#2D2040",
      "--muted-foreground": "#9B8AB8",
      "--accent": "#A78BFA",
      "--accent-foreground": "#FFFFFF",
      "--destructive": "#FB7185",
      "--destructive-foreground": "#FFFFFF",
      "--success": "#34D399",
      "--notification": "#FBBF24",
      "--border": "rgba(167, 139, 250, 0.12)",
      "--input": "rgba(167, 139, 250, 0.18)",
      "--ring": "#A78BFA",
      "--surface-hover": "#3D2E55",
    },
    light: {
      "--background": "#FAF8FF",
      "--foreground": "#1A1025",
      "--card": "#FFFFFF",
      "--card-foreground": "#1A1025",
      "--primary": "#E11D48",
      "--primary-foreground": "#FFFFFF",
      "--secondary": "#F3F0F8",
      "--secondary-foreground": "#1A1025",
      "--muted": "#F3F0F8",
      "--muted-foreground": "#6B5A85",
      "--accent": "#7C3AED",
      "--accent-foreground": "#FFFFFF",
      "--destructive": "#E11D48",
      "--destructive-foreground": "#FFFFFF",
      "--success": "#059669",
      "--notification": "#D97706",
      "--border": "#E5E0F0",
      "--input": "#E5E0F0",
      "--ring": "#7C3AED",
      "--surface-hover": "#F0ECF7",
    },
  },
  deep_luxury: {
    name: "Deep Luxury",
    description: "Premium, rich — better card separation, warm lavender text",
    dark: {
      "--background": "#0F0B1A",
      "--foreground": "#F0EAFF",
      "--card": "#1A1425",
      "--card-foreground": "#F0EAFF",
      "--primary": "#7C3AED",
      "--primary-foreground": "#FFFFFF",
      "--secondary": "#1A1425",
      "--secondary-foreground": "#F0EAFF",
      "--muted": "#1A1425",
      "--muted-foreground": "#B8A8D9",
      "--accent": "#A78BFA",
      "--accent-foreground": "#FFFFFF",
      "--destructive": "#F87171",
      "--destructive-foreground": "#FFFFFF",
      "--success": "#34D399",
      "--notification": "#FBBF24",
      "--border": "#2D2440",
      "--input": "#2D2440",
      "--ring": "#A78BFA",
      "--surface-hover": "#251E35",
    },
    light: {
      "--background": "#FDFBFF",
      "--foreground": "#0F0B1A",
      "--card": "#FFFFFF",
      "--card-foreground": "#0F0B1A",
      "--primary": "#7C3AED",
      "--primary-foreground": "#FFFFFF",
      "--secondary": "#F5F0FF",
      "--secondary-foreground": "#0F0B1A",
      "--muted": "#F5F0FF",
      "--muted-foreground": "#5B4A78",
      "--accent": "#8B5CF6",
      "--accent-foreground": "#FFFFFF",
      "--destructive": "#DC2626",
      "--destructive-foreground": "#FFFFFF",
      "--success": "#059669",
      "--notification": "#D97706",
      "--border": "#E8E0F5",
      "--input": "#E8E0F5",
      "--ring": "#7C3AED",
      "--surface-hover": "#F0EAFC",
    },
  },
  soft_wellness: {
    name: "Soft Wellness",
    description: "Calming, health-first — cyan accent, neutral darks",
    dark: {
      "--background": "#111118",
      "--foreground": "#E8E4F0",
      "--card": "#1C1B26",
      "--card-foreground": "#E8E4F0",
      "--primary": "#8B5CF6",
      "--primary-foreground": "#FFFFFF",
      "--secondary": "#1C1B26",
      "--secondary-foreground": "#E8E4F0",
      "--muted": "#1C1B26",
      "--muted-foreground": "#A39BB8",
      "--accent": "#67E8F9",
      "--accent-foreground": "#111118",
      "--destructive": "#FB7185",
      "--destructive-foreground": "#FFFFFF",
      "--success": "#4ADE80",
      "--notification": "#FCD34D",
      "--border": "#28243A",
      "--input": "#28243A",
      "--ring": "#8B5CF6",
      "--surface-hover": "#26243A",
    },
    light: {
      "--background": "#F8FAFB",
      "--foreground": "#111118",
      "--card": "#FFFFFF",
      "--card-foreground": "#111118",
      "--primary": "#7C3AED",
      "--primary-foreground": "#FFFFFF",
      "--secondary": "#F0F4F8",
      "--secondary-foreground": "#111118",
      "--muted": "#F0F4F8",
      "--muted-foreground": "#5A5470",
      "--accent": "#0891B2",
      "--accent-foreground": "#FFFFFF",
      "--destructive": "#E11D48",
      "--destructive-foreground": "#FFFFFF",
      "--success": "#059669",
      "--notification": "#D97706",
      "--border": "#E2E0EC",
      "--input": "#E2E0EC",
      "--ring": "#7C3AED",
      "--surface-hover": "#EDEAF5",
    },
  },
  vibrant_energy: {
    name: "Vibrant Energy",
    description: "Bold, high-contrast — amber accent, maximum readability",
    dark: {
      "--background": "#09090B",
      "--foreground": "#FAFAFA",
      "--card": "#18141F",
      "--card-foreground": "#FAFAFA",
      "--primary": "#9333EA",
      "--primary-foreground": "#FFFFFF",
      "--secondary": "#18141F",
      "--secondary-foreground": "#FAFAFA",
      "--muted": "#18141F",
      "--muted-foreground": "#8B7CA6",
      "--accent": "#F59E0B",
      "--accent-foreground": "#09090B",
      "--destructive": "#EF4444",
      "--destructive-foreground": "#FFFFFF",
      "--success": "#22C55E",
      "--notification": "#F59E0B",
      "--border": "#2A2235",
      "--input": "#2A2235",
      "--ring": "#9333EA",
      "--surface-hover": "#221C2E",
    },
    light: {
      "--background": "#FFFFFF",
      "--foreground": "#09090B",
      "--card": "#FAFAFA",
      "--card-foreground": "#09090B",
      "--primary": "#7C3AED",
      "--primary-foreground": "#FFFFFF",
      "--secondary": "#F4F4F5",
      "--secondary-foreground": "#09090B",
      "--muted": "#F4F4F5",
      "--muted-foreground": "#52455E",
      "--accent": "#D97706",
      "--accent-foreground": "#FFFFFF",
      "--destructive": "#DC2626",
      "--destructive-foreground": "#FFFFFF",
      "--success": "#16A34A",
      "--notification": "#D97706",
      "--border": "#E4E4E7",
      "--input": "#E4E4E7",
      "--ring": "#7C3AED",
      "--surface-hover": "#F0ECF7",
    },
  },
  vital_teal: {
    name: "Vital Teal",
    description: "Clinical precision meets human warmth — health-tech feel",
    dark: {
      "--background": "#0C1616",
      "--foreground": "#E8F0EF",
      "--card": "#132020",
      "--card-foreground": "#E8F0EF",
      "--primary": "#2DD4BF",
      "--primary-foreground": "#0C1616",
      "--secondary": "#1A3333",
      "--secondary-foreground": "#5EEAD4",
      "--muted": "#162828",
      "--muted-foreground": "#7DA5A0",
      "--accent": "#14B8A6",
      "--accent-foreground": "#0C1616",
      "--destructive": "#EF4444",
      "--destructive-foreground": "#FFFFFF",
      "--success": "#22C55E",
      "--notification": "#FBBF24",
      "--border": "#1E3A3A",
      "--input": "#244444",
      "--ring": "#2DD4BF",
      "--surface-hover": "#1A3030",
    },
    light: {
      "--background": "#FAFCFC",
      "--foreground": "#0F1D1D",
      "--card": "#FFFFFF",
      "--card-foreground": "#0F1D1D",
      "--primary": "#0D9488",
      "--primary-foreground": "#FFFFFF",
      "--secondary": "#E0F5F2",
      "--secondary-foreground": "#0A6B62",
      "--muted": "#F0F5F4",
      "--muted-foreground": "#5F7A77",
      "--accent": "#14B8A6",
      "--accent-foreground": "#FFFFFF",
      "--destructive": "#DC2626",
      "--destructive-foreground": "#FFFFFF",
      "--success": "#16A34A",
      "--notification": "#F59E0B",
      "--border": "#D4E4E1",
      "--input": "#C8DBD8",
      "--ring": "#0D9488",
      "--surface-hover": "#E8F0EF",
    },
  },
  desert_dusk: {
    name: "Desert Dusk",
    description: "Organic wellness — sand, terracotta, earth tones",
    dark: {
      "--background": "#141110",
      "--foreground": "#EDE5DA",
      "--card": "#1C1816",
      "--card-foreground": "#EDE5DA",
      "--primary": "#F59E0B",
      "--primary-foreground": "#141110",
      "--secondary": "#2A2320",
      "--secondary-foreground": "#FBBF24",
      "--muted": "#221D1A",
      "--muted-foreground": "#A08C7A",
      "--accent": "#D97706",
      "--accent-foreground": "#141110",
      "--destructive": "#EF4444",
      "--destructive-foreground": "#FFFFFF",
      "--success": "#4ADE80",
      "--notification": "#FB923C",
      "--border": "#332A24",
      "--input": "#3D322A",
      "--ring": "#F59E0B",
      "--surface-hover": "#261F1C",
    },
    light: {
      "--background": "#FAF8F5",
      "--foreground": "#1C1410",
      "--card": "#FFFFFF",
      "--card-foreground": "#1C1410",
      "--primary": "#B45309",
      "--primary-foreground": "#FFFFFF",
      "--secondary": "#F5EDE4",
      "--secondary-foreground": "#8B4513",
      "--muted": "#F0E8DF",
      "--muted-foreground": "#78685A",
      "--accent": "#D97706",
      "--accent-foreground": "#FFFFFF",
      "--destructive": "#C53030",
      "--destructive-foreground": "#FFFFFF",
      "--success": "#2D6A4F",
      "--notification": "#E07B39",
      "--border": "#E2D5C7",
      "--input": "#D9CABB",
      "--ring": "#B45309",
      "--surface-hover": "#EDE5DA",
    },
  },
  admiral: {
    name: "Admiral",
    description: "Navy + gold — trust, authority, premium longevity",
    dark: {
      "--background": "#0A0F1A",
      "--foreground": "#E2E8F0",
      "--card": "#111827",
      "--card-foreground": "#E2E8F0",
      "--primary": "#60A5FA",
      "--primary-foreground": "#0A0F1A",
      "--secondary": "#1E293B",
      "--secondary-foreground": "#93C5FD",
      "--muted": "#162032",
      "--muted-foreground": "#8494AA",
      "--accent": "#EAB308",
      "--accent-foreground": "#0A0F1A",
      "--destructive": "#EF4444",
      "--destructive-foreground": "#FFFFFF",
      "--success": "#4ADE80",
      "--notification": "#FACC15",
      "--border": "#1E2D44",
      "--input": "#263550",
      "--ring": "#60A5FA",
      "--surface-hover": "#152238",
    },
    light: {
      "--background": "#F8F9FC",
      "--foreground": "#0F172A",
      "--card": "#FFFFFF",
      "--card-foreground": "#0F172A",
      "--primary": "#1E3A5F",
      "--primary-foreground": "#FFFFFF",
      "--secondary": "#E8EDF5",
      "--secondary-foreground": "#1E3A5F",
      "--muted": "#EEF1F6",
      "--muted-foreground": "#64748B",
      "--accent": "#C8910A",
      "--accent-foreground": "#FFFFFF",
      "--destructive": "#DC2626",
      "--destructive-foreground": "#FFFFFF",
      "--success": "#15803D",
      "--notification": "#D4A017",
      "--border": "#D6DCE8",
      "--input": "#C8D0DF",
      "--ring": "#1E3A5F",
      "--surface-hover": "#E4E9F2",
    },
  },
  graphite_coral: {
    name: "Graphite Coral",
    description: "Modern minimal with a pulse — slate + coral pop",
    dark: {
      "--background": "#09090B",
      "--foreground": "#F4F4F5",
      "--card": "#121215",
      "--card-foreground": "#F4F4F5",
      "--primary": "#F47458",
      "--primary-foreground": "#09090B",
      "--secondary": "#1C1C22",
      "--secondary-foreground": "#A1A1AA",
      "--muted": "#18181B",
      "--muted-foreground": "#8B8B94",
      "--accent": "#FF8C73",
      "--accent-foreground": "#09090B",
      "--destructive": "#EF4444",
      "--destructive-foreground": "#FFFFFF",
      "--success": "#34D399",
      "--notification": "#F47458",
      "--border": "#27272A",
      "--input": "#303036",
      "--ring": "#F47458",
      "--surface-hover": "#1A1A1E",
    },
    light: {
      "--background": "#F9FAFB",
      "--foreground": "#111827",
      "--card": "#FFFFFF",
      "--card-foreground": "#111827",
      "--primary": "#E1654B",
      "--primary-foreground": "#FFFFFF",
      "--secondary": "#F3F4F6",
      "--secondary-foreground": "#374151",
      "--muted": "#F0F1F3",
      "--muted-foreground": "#6B7280",
      "--accent": "#F47458",
      "--accent-foreground": "#FFFFFF",
      "--destructive": "#B91C1C",
      "--destructive-foreground": "#FFFFFF",
      "--success": "#059669",
      "--notification": "#E1654B",
      "--border": "#E5E7EB",
      "--input": "#D1D5DB",
      "--ring": "#E1654B",
      "--surface-hover": "#EDEEF0",
    },
  },
  evergreen: {
    name: "Evergreen",
    description: "Natural health — forest green + cream, longevity and growth",
    dark: {
      "--background": "#0A120A",
      "--foreground": "#E4EDE4",
      "--card": "#111E11",
      "--card-foreground": "#E4EDE4",
      "--primary": "#4ADE80",
      "--primary-foreground": "#0A120A",
      "--secondary": "#1A2E1A",
      "--secondary-foreground": "#86EFAC",
      "--muted": "#142414",
      "--muted-foreground": "#7DA87D",
      "--accent": "#22C55E",
      "--accent-foreground": "#0A120A",
      "--destructive": "#EF4444",
      "--destructive-foreground": "#FFFFFF",
      "--success": "#4ADE80",
      "--notification": "#FACC15",
      "--border": "#1E3A1E",
      "--input": "#264026",
      "--ring": "#4ADE80",
      "--surface-hover": "#172C17",
    },
    light: {
      "--background": "#FAFAF6",
      "--foreground": "#1A2E1A",
      "--card": "#FFFFFF",
      "--card-foreground": "#1A2E1A",
      "--primary": "#15653A",
      "--primary-foreground": "#FFFFFF",
      "--secondary": "#E8F0E4",
      "--secondary-foreground": "#15653A",
      "--muted": "#EFF2EC",
      "--muted-foreground": "#5C7A5C",
      "--accent": "#22883E",
      "--accent-foreground": "#FFFFFF",
      "--destructive": "#DC2626",
      "--destructive-foreground": "#FFFFFF",
      "--success": "#16A34A",
      "--notification": "#CA8A04",
      "--border": "#D4DED0",
      "--input": "#C4D4BE",
      "--ring": "#15653A",
      "--surface-hover": "#E6ECE2",
    },
  },
};

type PaletteKey = keyof typeof palettes;
type Mode = "dark" | "light";

function ThemePreview() {
  const [selected, setSelected] = useState<PaletteKey | null>(null);
  const [mode, setMode] = useState<Mode>("dark");
  const [fontIdx, setFontIdx] = useState(0);
  const font = fontCombos[fontIdx];

  return (
    <div className="min-h-dvh bg-neutral-950 p-6" style={{ fontFamily: font.body }}>
      <div className="mx-auto max-w-7xl">
        <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="mb-1 text-2xl font-bold text-white" style={{ fontFamily: font.heading }}>
              Live150 Theme Preview
            </h1>
            <p className="text-neutral-400">
              Toggle dark/light and font. Click a theme to expand.
            </p>
          </div>
          <div className="flex gap-3">
            {/* Dark/Light toggle */}
            <div className="flex overflow-hidden rounded-lg border border-neutral-700">
              <button
                onClick={() => setMode("dark")}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  mode === "dark"
                    ? "bg-white text-black"
                    : "bg-transparent text-neutral-400 hover:text-white"
                }`}
              >
                Dark
              </button>
              <button
                onClick={() => setMode("light")}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  mode === "light"
                    ? "bg-white text-black"
                    : "bg-transparent text-neutral-400 hover:text-white"
                }`}
              >
                Light
              </button>
            </div>
          </div>
        </div>

        {/* Font switcher */}
        <div className="mb-8 flex flex-wrap gap-2">
          {fontCombos.map((fc, i) => (
            <button
              key={fc.name}
              onClick={() => setFontIdx(i)}
              className={`rounded-lg border px-3 py-2 text-left transition-all ${
                i === fontIdx
                  ? "border-white bg-neutral-800"
                  : "border-neutral-700 hover:border-neutral-500"
              }`}
            >
              <div
                className="text-sm font-semibold text-white"
                style={{ fontFamily: fc.heading }}
              >
                {fc.name}
              </div>
              <div className="text-xs text-neutral-400">{fc.description}</div>
            </button>
          ))}
        </div>

        {/* Grid of all themes */}
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
          {(Object.entries(palettes) as [PaletteKey, Palette][]).map(
            ([key, palette]) => (
              <button
                key={key}
                onClick={() => setSelected(selected === key ? null : key)}
                className={`rounded-lg border-2 text-left transition-all ${
                  selected === key
                    ? "border-white"
                    : "border-transparent hover:border-neutral-700"
                }`}
              >
                <ThemeCard palette={palette} mode={mode} font={font} />
              </button>
            )
          )}
        </div>

        {/* Full-size preview */}
        {selected && (
          <div className="mt-10">
            <h2 className="mb-1 text-xl font-bold text-white">
              Full Preview — {palettes[selected].name}{" "}
              <span className="text-neutral-500">({mode})</span>
            </h2>
            <p className="mb-4 text-sm text-neutral-500">
              Side-by-side dark and light
            </p>
            <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
              <div>
                <div className="mb-2 text-xs font-medium uppercase tracking-wider text-neutral-500">
                  Dark
                </div>
                <FullPreview vars={palettes[selected].dark} font={font} />
              </div>
              <div>
                <div className="mb-2 text-xs font-medium uppercase tracking-wider text-neutral-500">
                  Light
                </div>
                <FullPreview vars={palettes[selected].light} font={font} />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function ThemeCard({ palette, mode, font }: { palette: Palette; mode: Mode; font: FontCombo }) {
  const v = mode === "dark" ? palette.dark : palette.light;

  return (
    <div
      className="overflow-hidden rounded-lg"
      style={{ background: v["--background"], color: v["--foreground"], fontFamily: font.body }}
    >
      {/* Header */}
      <div className="border-b px-5 py-4" style={{ borderColor: v["--border"] }}>
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-bold" style={{ fontFamily: font.heading }}>{palette.name}</h3>
            <p className="text-sm" style={{ color: v["--muted-foreground"] }}>
              {palette.description}
            </p>
          </div>
          <div
            className="flex h-8 w-8 items-center justify-center rounded-md text-sm font-bold"
            style={{ background: v["--primary"], color: v["--primary-foreground"] }}
          >
            L
          </div>
        </div>
      </div>

      {/* Body */}
      <div className="space-y-4 p-5">
        {/* Chat bubbles */}
        <div className="space-y-2">
          <div
            className="ml-auto w-fit max-w-[80%] rounded-2xl rounded-br-md px-4 py-2.5 text-sm"
            style={{ background: v["--primary"], color: v["--primary-foreground"] }}
          >
            How did I sleep last night?
          </div>
          <div className="max-w-[90%] text-sm leading-relaxed">
            You logged <span className="font-bold">6h 42m</span> — 48 minutes
            short of your 7.5h target. HRV was{" "}
            <span style={{ color: v["--accent"] }}>down 12%</span> from baseline.
          </div>
        </div>

        {/* Tool call */}
        <div
          className="rounded-lg border px-3 py-2"
          style={{ borderColor: v["--border"], background: v["--card"] }}
        >
          <div className="flex items-center gap-2 text-xs">
            <span style={{ color: v["--accent"] }}>&#9881;</span>
            <span style={{ color: v["--muted-foreground"] }}>get_sleep_summary</span>
            <span
              className="ml-auto rounded-full px-2 py-0.5 text-[10px]"
              style={{ background: v["--background"], color: v["--success"] }}
            >
              Completed
            </span>
          </div>
        </div>

        {/* Card */}
        <div
          className="rounded-lg border p-4"
          style={{ borderColor: v["--border"], background: v["--card"] }}
        >
          <div className="mb-2 text-sm font-semibold" style={{ fontFamily: font.heading }}>Today's Actions</div>
          <ul
            className="space-y-1.5 text-sm"
            style={{ color: v["--muted-foreground"] }}
          >
            <li className="flex items-center gap-2">
              <span style={{ color: v["--success"] }}>&#10003;</span> Zone 2
              cardio — 30 min
            </li>
            <li className="flex items-center gap-2">
              <span style={{ color: v["--notification"] }}>&#9679;</span> Dinner
              by 7:30pm
            </li>
            <li className="flex items-center gap-2">
              <span style={{ color: v["--accent"] }}>&#9679;</span> Lights out by
              10:45pm
            </li>
          </ul>
        </div>

        {/* Buttons row */}
        <div className="flex gap-2">
          <div
            className="rounded-md px-3 py-1.5 text-sm font-medium"
            style={{ background: v["--primary"], color: v["--primary-foreground"] }}
          >
            Primary
          </div>
          <div
            className="rounded-md border px-3 py-1.5 text-sm font-medium"
            style={{ borderColor: v["--border"], color: v["--foreground"] }}
          >
            Secondary
          </div>
          <div
            className="rounded-md px-3 py-1.5 text-sm font-medium"
            style={{ background: v["--accent"], color: v["--accent-foreground"] }}
          >
            Accent
          </div>
          <div
            className="rounded-md px-3 py-1.5 text-sm font-medium"
            style={{
              background: v["--destructive"],
              color: v["--destructive-foreground"],
            }}
          >
            Error
          </div>
        </div>

        {/* Input */}
        <div
          className="flex items-center rounded-xl border px-4 py-3"
          style={{ borderColor: v["--border"], background: v["--card"] }}
        >
          <span className="flex-1 text-sm" style={{ color: v["--muted-foreground"] }}>
            Ask me anything...
          </span>
          <span
            className="flex h-7 w-7 items-center justify-center rounded-md text-sm"
            style={{ background: v["--primary"], color: v["--primary-foreground"] }}
          >
            &#8593;
          </span>
        </div>

        {/* Color swatches */}
        <div className="flex flex-wrap gap-1.5 pt-2">
          {(
            [
              ["bg", "--background"],
              ["fg", "--foreground"],
              ["card", "--card"],
              ["primary", "--primary"],
              ["accent", "--accent"],
              ["muted-fg", "--muted-foreground"],
              ["border", "--border"],
              ["success", "--success"],
              ["error", "--destructive"],
              ["warn", "--notification"],
            ] as const
          ).map(([label, varName]) => (
            <div key={label} className="flex items-center gap-1">
              <div
                className="h-4 w-4 rounded border border-neutral-600"
                style={{ background: v[varName] }}
              />
              <span
                className="text-[10px]"
                style={{ color: v["--muted-foreground"] }}
              >
                {label}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function FullPreview({ vars: v, font }: { vars: ThemeVars; font: FontCombo }) {
  return (
    <div
      className="mx-auto max-w-2xl overflow-hidden rounded-xl border"
      style={{
        background: v["--background"],
        color: v["--foreground"],
        borderColor: v["--border"],
        fontFamily: font.body,
      }}
    >
      {/* App header */}
      <div
        className="flex items-center justify-between border-b px-6 py-4"
        style={{ borderColor: v["--border"] }}
      >
        <div className="flex items-center gap-3">
          <div
            className="flex h-9 w-9 items-center justify-center rounded-lg text-sm font-bold"
            style={{ background: v["--primary"], color: v["--primary-foreground"], fontFamily: font.heading }}
          >
            L
          </div>
          <div>
            <div className="text-sm font-bold" style={{ fontFamily: font.heading }}>Live150</div>
            <div className="text-xs" style={{ color: v["--muted-foreground"] }}>
              Nigel's longevity companion
            </div>
          </div>
        </div>
        <div
          className="rounded-md border px-2.5 py-1 text-xs"
          style={{ borderColor: v["--border"], color: v["--muted-foreground"] }}
        >
          +1 (908) 432-9987
        </div>
      </div>

      {/* Chat messages */}
      <div className="space-y-5 p-6">
        {/* User message */}
        <div className="flex justify-end">
          <div
            className="max-w-[80%] rounded-2xl rounded-br-md px-4 py-3 text-sm"
            style={{ background: v["--primary"], color: v["--primary-foreground"] }}
          >
            What's my plan for today? I slept terribly.
          </div>
        </div>

        {/* Thinking shimmer */}
        <div
          className="rounded-lg border px-4 py-3"
          style={{ borderColor: v["--border"], background: v["--card"] }}
        >
          <div className="flex items-center gap-2">
            <div
              className="h-2 w-2 animate-pulse rounded-full"
              style={{ background: v["--accent"] }}
            />
            <span
              className="text-xs font-medium"
              style={{ color: v["--muted-foreground"] }}
            >
              Thinking...
            </span>
          </div>
          <div className="mt-2 space-y-1.5">
            <div
              className="flex items-center gap-2 text-xs"
              style={{ color: v["--muted-foreground"] }}
            >
              <span style={{ color: v["--success"] }}>&#10003;</span>
              <span>get_sleep_summary</span>
              <span
                className="ml-auto text-[10px]"
                style={{ color: v["--success"] }}
              >
                done
              </span>
            </div>
            <div
              className="flex items-center gap-2 text-xs"
              style={{ color: v["--muted-foreground"] }}
            >
              <span style={{ color: v["--success"] }}>&#10003;</span>
              <span>get_health_goals</span>
              <span
                className="ml-auto text-[10px]"
                style={{ color: v["--success"] }}
              >
                done
              </span>
            </div>
            <div
              className="flex items-center gap-2 text-xs"
              style={{ color: v["--muted-foreground"] }}
            >
              <span className="animate-pulse" style={{ color: v["--accent"] }}>
                &#9881;
              </span>
              <span>get_calendar_schedule</span>
              <span
                className="ml-auto text-[10px]"
                style={{ color: v["--accent"] }}
              >
                running
              </span>
            </div>
          </div>
        </div>

        {/* Assistant response */}
        <div className="space-y-3 text-sm leading-relaxed">
          <p>
            Rough night — <span className="font-bold">5h 12m</span> logged, well
            below your 7.5h target. HRV dropped to{" "}
            <span style={{ color: v["--accent"] }}>38</span>, which tracks with
            the poor sleep.
          </p>
          <p>Given the deficit, here's today adjusted:</p>
          <ul className="space-y-1 pl-1">
            <li className="flex items-start gap-2">
              <span className="mt-0.5 font-bold">1.</span>
              <span>
                <span className="font-bold">Skip the HIIT</span> — swap to a
                25-min Zone 2 walk. Your body needs recovery, not stress.
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span className="mt-0.5 font-bold">2.</span>
              <span>
                <span className="font-bold">Caffeine cutoff at 1pm</span> — you
                had coffee at 3pm yesterday, which likely contributed.
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span className="mt-0.5 font-bold">3.</span>
              <span>
                <span className="font-bold">Lights out by 10pm</span> tonight.
                You have a 9am meeting tomorrow — I can see it on your calendar.
              </span>
            </li>
          </ul>
        </div>

        {/* Collapsed tool section */}
        <div
          className="rounded-lg border px-4 py-2.5"
          style={{ borderColor: v["--border"], background: v["--card"] }}
        >
          <div className="flex items-center gap-2 text-xs">
            <span style={{ color: v["--accent"] }}>&#9881;</span>
            <span style={{ color: v["--muted-foreground"] }}>
              3 tool calls completed in 1.2s
            </span>
            <span className="ml-auto" style={{ color: v["--muted-foreground"] }}>
              &#9660;
            </span>
          </div>
        </div>

        {/* Another user message */}
        <div className="flex justify-end">
          <div
            className="max-w-[80%] rounded-2xl rounded-br-md px-4 py-3 text-sm"
            style={{ background: v["--primary"], color: v["--primary-foreground"] }}
          >
            Put the walk on my calendar
          </div>
        </div>

        {/* Success confirmation */}
        <div className="text-sm leading-relaxed">
          <p>
            Done — added{" "}
            <span className="font-bold">Zone 2 walk (25 min)</span> to your
            Live150 calendar at <span className="font-bold">4:00pm</span>. Heads
            up: you have{" "}
            <span style={{ color: v["--accent"] }}>Lunch with Ravi</span> at 1pm,
            so the afternoon slot works.
          </p>
        </div>

        {/* Notification-style callout */}
        <div
          className="flex items-center gap-2 rounded-lg border px-4 py-2.5 text-sm"
          style={{
            borderColor: v["--border"],
            background: v["--card"],
            color: v["--muted-foreground"],
          }}
        >
          <span style={{ color: v["--success"] }}>&#10003;</span>
          <span>
            Calendar event created:{" "}
            <span style={{ color: v["--foreground"] }}>Zone 2 Walk</span> —
            4:00-4:25pm
          </span>
        </div>
      </div>

      {/* Input area */}
      <div className="border-t p-4" style={{ borderColor: v["--border"] }}>
        {/* Suggestions */}
        <div className="mb-3 flex gap-2">
          {["How did I sleep?", "Weekly review", "What's for dinner?"].map(
            (s) => (
              <div
                key={s}
                className="rounded-lg border px-3 py-1.5 text-xs"
                style={{
                  borderColor: v["--border"],
                  color: v["--muted-foreground"],
                }}
              >
                {s}
              </div>
            )
          )}
        </div>
        {/* Text input */}
        <div
          className="flex items-center rounded-xl border px-4 py-3"
          style={{ borderColor: v["--border"], background: v["--card"] }}
        >
          <span
            className="flex-1 text-sm"
            style={{ color: v["--muted-foreground"] }}
          >
            Ask me anything...
          </span>
          <span
            className="flex h-8 w-8 items-center justify-center rounded-lg text-sm"
            style={{ background: v["--primary"], color: v["--primary-foreground"] }}
          >
            &#8593;
          </span>
        </div>
      </div>
    </div>
  );
}
