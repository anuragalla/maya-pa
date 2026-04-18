# Live150 Chat UI — Design System

## Vision

A longevity companion that feels like texting a coach who genuinely knows you. Not a clinical dashboard, not a generic chatbot — a focused, data-aware conversation that respects your time.

## Aesthetic

- **Clean, not minimal.** Content-dense when needed (tool results, health data), spacious when not (empty state, input).
- **Dark-first.** Health data is easier to read on dark backgrounds. Purple accent from the preset for energy and focus.
- **Functional motion.** Framer Motion for message entry, tool state transitions, and conversation scroll. No gratuitous animation.
- **Typography-driven.** Geist Variable — let the font do the work. Tight tracking on headings, relaxed leading on body.

## Layout

```
┌─────────────────────────────────────┐
│ [Logo] Live150          [User ▼]    │  ← Header: 48px, border-b
├─────────────────────────────────────┤
│                                     │
│  [Empty state / Messages]           │  ← Conversation: flex-1, overflow-y
│  ┌─────────────────────────┐        │
│  │ 🔧 Tool: Health Goals   │        │     Tool pills: collapsible
│  │    ✓ Done               │        │
│  └─────────────────────────┘        │
│                                     │
│  Agent response with markdown...    │     Messages: max-w-3xl centered
│                                     │
├─────────────────────────────────────┤
│ [Suggestions row (when empty)]      │  ← Suggestions: horizontal scroll
├─────────────────────────────────────┤
│ [  Type a message...     ] [Send]   │  ← PromptInput: sticky bottom
└─────────────────────────────────────┘
```

## Components (from ai-elements)

| Component | Use |
|---|---|
| `Conversation` + `ConversationContent` | Auto-scroll container with sticky-to-bottom |
| `Message` + `MessageContent` + `MessageResponse` | Message bubbles with markdown rendering |
| `PromptInput` + `PromptInputTextarea` + `PromptInputSubmit` | Input bar with auto-resize, Enter/Shift+Enter |
| `Tool` + `ToolHeader` + `ToolContent` + `ToolOutput` | Collapsible tool call display |
| `Suggestion` + `Suggestions` | Quick-action chips |
| `Shimmer` | Loading placeholder text |

## Motion (Framer Motion)

- **Message enter:** `opacity: 0→1, y: 8→0`, 200ms ease-out
- **Tool expand/collapse:** `height: auto` with layout animation
- **Suggestion appear:** staggered fade, 50ms delay each
- **Notification slide-in:** `y: -20→0, opacity: 0→1`

## Color

From shadcn preset `b2BVFVaq0`:
- Primary: purple (`oklch(0.491 0.27 292)`)
- Background: near-black dark, white light
- Muted: neutral grays
- Chart colors: teal gradient (for future health viz)

## Responsive

- **Desktop (>640px):** max-w-3xl centered, comfortable padding
- **Mobile (<640px):** full-width messages, compact input, safe-area-inset-bottom
- No sidebar. Single-screen chat. User selector in header.
