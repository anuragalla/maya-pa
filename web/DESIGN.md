# Design System — Maya Health Agent

## Product Context
- **What this is:** Personal wellness chat assistant with autonomous execution
- **Who it's for:** Health-conscious users tracking nutrition, activity, sleep, mindfulness, weight, glucose
- **Space/industry:** Consumer health & wellness (peers: Oura, Calm, Headspace)
- **Project type:** Single-page chat web app (dev/internal testing)

## Aesthetic Direction
- **Direction:** Bold & Playful
- **Decoration level:** Expressive (gradients, glow effects, bouncy motion)
- **Mood:** Warm, energetic, premium — like a fun wellness app, not a clinical dashboard. Should feel like talking to a witty friend who happens to know nutrition science.
- **Reference sites:** Oura Ring app (dark premium), Headspace (playful illustrations), Calm (soothing dark)

## Typography
- **Display/Headers:** Plus Jakarta Sans Bold — rounded, warm, friendly
- **Body:** Plus Jakarta Sans Regular — clean, highly readable
- **Steps/Technical:** JetBrains Mono — clear monospace for tool calls and execution steps
- **Loading:** `@fontsource-variable/plus-jakarta-sans`, `@fontsource/jetbrains-mono` (self-hosted via npm)
- **Scale:**
  - Micro/badge → `text-[10px]` (below Tailwind's default floor of `text-xs`)
  - Steps → `text-xs` (12px)
  - Body → `text-sm` (14px)
  - Header → `text-base` (16px)
  - Hero → `text-2xl` (24px)

## Color
- **Approach:** Expressive — color is a primary design tool
- **Background:** `#1A1025` — deep purple-black (warm, not cold zinc)
- **Surface/Cards:** `#2D2040` — purple-tinted surface
- **Surface hover:** `#3D2E55`
- **Primary (user bubbles):** `#FB7185` — coral/rose (energetic, warm) *(matches Tailwind `rose-400`)*
- **Accent:** `#A78BFA` — violet, used for steps/badges *(matches Tailwind `violet-400`)*
- **Foreground text:** `#F1E8FF` — soft lavender-white (not harsh pure white)
- **Muted text:** `#9B8AB8` — warm purple-gray
- **Notification:** `#FBBF24` — warm amber *(matches Tailwind `amber-400`)*
- **Success:** `#34D399` — emerald *(matches Tailwind `emerald-400`)*
- **Error:** `#FB7185` — rose (same as primary — intentional cohesion)
- **Border:** `rgba(167, 139, 250, 0.12)` — subtle violet tint (`violet-400` @ 12% opacity → `border-violet-400/10`)

## Spacing
- **Base unit:** Tailwind default (`1` = 4px)
- **Density:** Comfortable
- **Message gap:** `gap-5` (20px between messages)
- **Bubble padding:** `px-4 py-3` (16px horizontal, 12px vertical)
- **Input padding:** `p-4` (16px all sides)

## Layout
- **Approach:** Single-column chat, centered
- **Max content width:** `max-w-[640px]` (custom — sits between Tailwind's `max-w-xl` 576px and `max-w-2xl` 672px)
- **Border radius:**
  - Bubbles, cards → `rounded-2xl` (16px)
  - Input, buttons → `rounded-xl` (12px)
  - Badges, avatars → `rounded-full`
- **Input bar:** `rounded-3xl` (pill-shaped, ChatGPT-style)
- **User bubbles:** `rounded-2xl rounded-br-md` (tail bottom-right), coral bg
- **Agent messages:** No bubble — plain flowing text on background (ChatGPT-style). Tool cards use subtle `rounded-xl` border.

## Motion
- **Approach:** Expressive — bouncy entrances, smooth transitions
- **Message enter:** fade-in + slide-up (`duration-300`, `ease-out`)
- **Steps expand:** fade-in + slide-down (`duration-200`)
- **Notification enter:** slide-in-from-top (`duration-[400ms]`, spring ease)
- **Status dots:** bounce animation with staggered delay (150ms intervals)
- **Send button hover:** `-translate-y-px` + coral glow shadow
- **Easing:** `ease-out` for entrances, `ease-in-out` for hover states

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-13 | Bold & Playful direction chosen | User wanted premium wellness feel, not dev tool. Purple-black + coral matches Maya's "warm, witty" persona. |
| 2026-04-13 | Plus Jakarta Sans over Inter | Rounded terminals feel friendlier. Inter is overused and feels clinical. |
| 2026-04-13 | Coral primary over teal/green | Stands out from every other health app (all use green/teal). Coral is energetic and warm. |
| 2026-04-13 | Agent bubble glow effect | Subtle coral glow on Maya's messages creates visual warmth and distinguishes from user messages. |
| 2026-04-18 | Standardized to Tailwind default tokens | Removed raw pixel values in favor of Tailwind's spacing/type/radius scales for consistency. Kept `max-w-[640px]` as an intentional custom width and `text-[10px]` for the micro/badge size below Tailwind's `text-xs` floor. |
