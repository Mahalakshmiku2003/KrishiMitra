# Design System Strategy: The Digital Agronomist

## 1. Overview & Creative North Star
The "Digital Agronomist" is the guiding philosophy of this design system. We are moving away from the "utility app" aesthetic and toward a "High-End Editorial" experience. Agriculture is a blend of ancient wisdom and cutting-edge science; our UI must reflect this through **Organic Precision**.

The system rejects the rigid, boxy constraints of standard mobile templates. Instead, it utilizes **intentional asymmetry** and **tonal layering** to create a sense of breathability and prestige. By overlapping elements and using a dramatic typography scale, we transform data into a narrative, making the farmer feel like a curator of their land rather than a user of an interface.

---

## 2. Colors: Tonal Depth & The "No-Line" Rule
We utilize a sophisticated palette that mimics the natural gradients of a flourishing field.

### The "No-Line" Rule
**Explicit Instruction:** Designers are prohibited from using 1px solid borders for sectioning. Boundaries must be defined solely through background color shifts. For example, a `surface-container-low` section sitting on a `surface` background creates a natural, soft transition that feels premium and integrated.

### Surface Hierarchy & Nesting
Treat the UI as a series of physical layers—like stacked sheets of fine paper. 
- **Nesting Logic:** Place a `surface-container-lowest` card on a `surface-container` background to create a "lifted" focus without artificial shadows.
- **Glass & Gradient:** For high-impact areas (e.g., Yield Forecasts), use Glassmorphism. Use semi-transparent variants of `primary-container` with a 16px backdrop-blur to allow the background hues to bleed through.

### Key Tokens
- **Primary (`#0d631b`):** Used for signature actions. Apply a subtle linear gradient from `primary` to `primary-container` for CTAs to add "soul" and depth.
- **Tertiary/Accent (`#774c00`):** Use for critical insights and "harvest-ready" alerts.
- **Surface Tiers:** Use `surface-container-low` (#f3f3f3) for secondary content blocks and `surface-container-highest` (#e2e2e2) for deep-set interactive wells.

---

## 3. Typography: The Editorial Scale
We use a high-contrast pairing: **Manrope** for authoritative headers and **Work Sans** for legible, utilitarian data.

| Level | Token | Font | Size | Character |
| :--- | :--- | :--- | :--- | :--- |
| **Display** | `display-lg` | Manrope | 3.5rem | Bold, intentional, for hero metrics. |
| **Headline** | `headline-md` | Manrope | 1.75rem | High-contrast, tight tracking (-2%). |
| **Title** | `title-lg` | Work Sans | 1.375rem | Professional, semi-bold. |
| **Body** | `body-md` | Work Sans | 0.875rem | Generous line-height (1.6) for readability. |
| **Label** | `label-md` | Work Sans | 0.75rem | All-caps for metadata/tags. |

**Editorial Direction:** Use `display-md` for data points (e.g., "88%") and immediately follow it with a `label-sm` descriptor. This asymmetry creates a "magazine" feel that elevates the data's importance.

---

## 4. Elevation & Depth: Tonal Layering
Traditional drop shadows are often messy. In this system, depth is achieved through light and material properties.

- **The Layering Principle:** Stack `surface-container-lowest` (pure white) cards on `surface-container` (soft grey) backgrounds. This creates a crisp, natural lift.
- **Ambient Shadows:** When an element must float (e.g., a Bottom Sheet), use an extra-diffused shadow: `Y: 8px, Blur: 24px, Color: On-Surface @ 6%`.
- **The Ghost Border:** If a border is essential for accessibility, use the `outline-variant` token at **15% opacity**. Never use 100% opaque lines.
- **Soft Corners:** Use the **XL (1.5rem / 24px)** radius for major containers and **LG (1rem / 16px)** for internal cards to create a "nested" organic feel.

---

## 5. Components: Organic Primitives

### Cards & Lists
**Rule:** Forbid the use of divider lines. 
- Use vertical white space (Spacing Scale `6` or `8`) to separate list items.
- Cards should use a "Subtle Inset" style: use `surface-container-low` for the card body and a `surface-container-lowest` header area to guide the eye.

### Buttons (The "Field" Button)
- **Primary:** `primary` background, `on-primary` text. No border. Radius: `full`.
- **Tertiary:** No background. `primary` text. Use for low-priority actions like "View History."

### Input Fields (The "Clean Soil" Input)
- Avoid the traditional "box." Use a `surface-container-highest` background with a soft `lg` radius. 
- On focus, transition the background color to `primary-container` at 10% opacity.

### Custom Component: The "Growth Tracker"
A specialized horizontal chip-set using `secondary-container` to track crop stages. Each chip uses a `surface-variant` icon and `on-secondary-container` text, creating a high-fidelity dashboard look.

---

## 6. Do’s and Don’ts

### Do
- **Do** use asymmetrical spacing. Allow a larger margin on the left (e.g., `8`) than the right (`5`) for headline text to create an editorial "hang."
- **Do** use the `tertiary-fixed` amber for weather alerts—it mimics the sun and provides immediate warmth and urgency.
- **Do** lean into `surface-bright` for full-screen takeovers to emphasize clarity and "freshness."

### Don’t
- **Don’t** use black (`#000000`). Use `on-surface-variant` for body text to maintain a soft, professional tone.
- **Don’t** use standard Material Design dividers. Use a 4px gap or a subtle background shift.
- **Don’t** use sharp corners. Agriculture is organic; every corner should have at least an `md` radius.