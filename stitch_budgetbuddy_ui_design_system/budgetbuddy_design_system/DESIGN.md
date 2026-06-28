---
name: BudgetBuddy Design System
colors:
  surface: '#fef8fb'
  surface-dim: '#ded8dc'
  surface-bright: '#fef8fb'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f8f2f6'
  surface-container: '#f2ecf0'
  surface-container-high: '#ece7ea'
  surface-container-highest: '#e6e1e5'
  on-surface: '#1d1b1e'
  on-surface-variant: '#4a454d'
  inverse-surface: '#323033'
  inverse-on-surface: '#f5eff3'
  outline: '#7b757e'
  outline-variant: '#cbc4ce'
  surface-tint: '#68577e'
  primary: '#66547b'
  on-primary: '#ffffff'
  primary-container: '#7f6d95'
  on-primary-container: '#fffbff'
  inverse-primary: '#d3beeb'
  secondary: '#69577e'
  on-secondary: '#ffffff'
  secondary-container: '#e8d1ff'
  on-secondary-container: '#69577f'
  tertiary: '#63602c'
  on-tertiary: '#ffffff'
  tertiary-container: '#b2ae71'
  on-tertiary-container: '#44410f'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#eddcff'
  primary-fixed-dim: '#d3beeb'
  on-primary-fixed: '#231437'
  on-primary-fixed-variant: '#503f65'
  secondary-fixed: '#eedbff'
  secondary-fixed-dim: '#d4beeb'
  on-secondary-fixed: '#231437'
  on-secondary-fixed-variant: '#503f65'
  tertiary-fixed: '#eae5a3'
  tertiary-fixed-dim: '#cec98a'
  on-tertiary-fixed: '#1e1c00'
  on-tertiary-fixed-variant: '#4b4816'
  background: '#fef8fb'
  on-background: '#1d1b1e'
  surface-variant: '#e6e1e5'
typography:
  headline-xl:
    fontFamily: Plus Jakarta Sans
    fontSize: 40px
    fontWeight: '700'
    lineHeight: 48px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
  headline-xl-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
  headline-lg-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 28px
    fontWeight: '700'
    lineHeight: 36px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 4px
  xs: 8px
  sm: 16px
  md: 24px
  lg: 32px
  xl: 48px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 40px
---

## Brand & Style

The design system is centered on the concept of **Financial Serenity**. Eschewing the cold, rigid aesthetics of traditional banking, this system prioritizes a calm and supportive atmosphere designed for young adults navigating personal finance. It balances the trustworthiness of a financial tool with the approachability of a lifestyle app.

The visual style is **Modern Minimalist with a Soft-Tactile edge**. It utilizes a lavender-centric palette to reduce "money anxiety," replacing sharp edges and aggressive greens with soft curves and airy whitespace. The interface feels smart but not clinical, encouraging long-term engagement through a sense of visual ease and clarity.

## Colors

The palette is built on a foundation of **monochromatic purple hues** to create a unified, soothing experience.

- **Primary (#9784ae):** Used for main actions, active states, and branding elements. It is soft enough to be approachable but saturated enough to remain legible.
- **Secondary/Interactive (#7e6b94):** A deeper shade for hover states, focused inputs, and high-priority interactive elements to provide necessary contrast.
- **Background (#ccb3e7):** A tinted wash that provides a distinctive, non-corporate backdrop for content.
- **Surface (#ffffff):** Pure white is reserved for cards and containers to create a "lifted" effect against the tinted background.
- **Neutral/Muted:** Secondary text should use a desaturated version of the primary purple (e.g., #948ba0) to maintain the tonal harmony.
- **Error (#e5a5a5):** A muted, soft red that signals issues without causing alarm.

## Typography

This design system uses a two-font pairing to distinguish between brand "voice" and functional data.

**Plus Jakarta Sans** is used for headlines. Its friendly, geometric terminals and open counters provide a welcoming and modern feel that resonates with a younger audience.

**Inter** is used for body copy, forms, and data. It provides exceptional legibility for financial figures and dense information. A generous line height (1.5x) is applied to body text to maintain the "airy" feel of the brand.

**Formatting Rules:**
- Large headlines should use negative letter spacing for a tighter, more editorial look.
- Labels for data visualization or small metadata should use semi-bold weights and slight tracking for readability at small sizes.

## Layout & Spacing

The layout follows a **fluid grid model** with a heavy emphasis on "Safe Zones"—generous margins that prevent the UI from feeling cluttered.

- **Desktop:** 12-column grid with 24px gutters. Maximum content width of 1200px.
- **Mobile:** 4-column grid with 16px gutters and 16px side margins.
- **Spacing Rhythm:** An 8px base grid is used for all component-level spacing. 
- **Philosophy:** Components are grouped using logical proximity. Information-heavy views (like transaction lists) should utilize `md` (24px) padding to ensure the "calm" brand promise is maintained even when data is dense.

## Elevation & Depth

Depth is created through **Tonal Layering and Soft Ambient Shadows**, rather than heavy borders or dark overlays.

- **Surface Tiers:** The background uses the primary-tinted purple. Content lives on white `surface` cards, creating immediate natural contrast.
- **Shadows:** Use a single, highly diffused shadow style for cards. Shadows should be tinted with the primary color to keep them "warm." 
    - *Example:* `0px 4px 20px rgba(151, 132, 174, 0.15)`
- **Interactive Depth:** When a user interacts with a card or button, the elevation should decrease slightly (moving "closer" to the page) to mimic a physical press.

## Shapes

The shape language is **Soft and Friendly**. 

- **Cards & Major Containers:** Use a 16px (`rounded-lg`) corner radius. This creates a soft, approachable frame for financial data.
- **Buttons & Inputs:** Use an 8px (`base`) corner radius.
- **Chips & Tags:** Use a fully rounded pill-shape to distinguish them from interactive buttons.
- **Consistency:** Never mix sharp corners with rounded ones. Even progress bars and chart elements should utilize rounded caps to match the system's softness.

## Components

### Buttons
- **Primary:** Solid `#9784ae` with white text. High-contrast, 8px radius.
- **Ghost:** Transparent background with a 1.5px border of `#7e6b94`. Used for secondary actions like "Cancel" or "Export."

### Input Fields
- **Default:** White background with a subtle `#9784ae` (20% opacity) border. 
- **Focus:** 2px border of `#7e6b94` with a soft outer glow in the primary color.
- **Error State:** Border becomes `#e5a5a5` with helper text in the same color below the field.

### Stat Cards
The hero component of the app. These are white cards with `headline-md` for the primary figure and `body-sm` (muted) for the label. They should always feature a subtle padding of 24px.

### Category Chips
Used for transaction tagging (e.g., "Food," "Rent"). These use a light tint of the primary color (10% opacity) with the text in the primary color.

### Chart Cards
Charts (Bar, Line, or Pie) should use a palette derived from the Primary and Secondary purples. Avoid high-contrast clashing colors; instead, use varying opacities and shades of lavender to represent different data segments.