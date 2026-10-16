---
name: RÉSIVO Design System
description: Institutional, high-trust student accommodation and facility operations design system
colors:
  primary: "#1e293b"
  primary-hover: "#0f172a"
  accent-blue: "#2563eb"
  accent-blue-hover: "#1d4ed8"
  accent-blue-subtle: "#eff6ff"
  canvas: "#f8fafc"
  surface: "#ffffff"
  surface-subtle: "#f1f5f9"
  border: "#e2e8f0"
  border-focus: "#2563eb"
  text-primary: "#0f172a"
  text-secondary: "#475569"
  text-muted: "#64748b"
  success: "#059669"
  success-bg: "#ecfdf5"
  success-border: "#a7f3d0"
  warning: "#d97706"
  warning-bg: "#fffbeb"
  warning-border: "#fde68a"
  danger: "#dc2626"
  danger-bg: "#fef2f2"
  danger-border: "#fecaca"
typography:
  display:
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: "1.875rem"
    fontWeight: 700
    lineHeight: 1.25
    letterSpacing: "-0.025em"
  heading:
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 600
    lineHeight: 1.35
    letterSpacing: "-0.015em"
  body:
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  small:
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "0.01em"
rounded:
  sm: "6px"
  md: "10px"
  lg: "14px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    rounded: "{rounded.sm}"
    padding: "8px 16px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
---

# Design System

## Overview

The visual design system for **RÉSIVO** reflects the civic dignity, dependability, and structured efficiency of a major higher-education student housing authority.

The system powers both:
1. **The Web Portal (Students)**: Clean, reassuring, mobile-responsive, and accessible.
2. **The Desktop Console (Department Staff)**: High-density, scan-friendly, dark-toned sidebar with clean white content cards, rich status pills, and zero visual clutter.

## Colors

- **Foundations**:
  - `Canvas`: `#f8fafc` (Slate 50) — calming, neutral background.
  - `Surface`: `#ffffff` (White) — crisp card & container surface.
  - `Subtle Surface`: `#f1f5f9` (Slate 100) — secondary panels, headers, table strips.
  - `Borders`: `#e2e8f0` (Slate 200) — delicate, crisp structural lines.
- **Accents**:
  - `Slate 900` (`#0f172a`) & `Slate 800` (`#1e293b`) — institutional primary actions and desktop sidebar.
  - `Blue 600` (`#2563eb`) — interactive highlights, active tabs, focus rings.
- **Semantic Badges**:
  - `Active / Resolved`: Emerald text `#065f46`, background `#ecfdf5`, border `#a7f3d0`.
  - `Pending / Review`: Amber text `#92400e`, background `#fffbeb`, border `#fde68a`.
  - `Rejected / Critical`: Rose text `#991b1b`, background `#fef2f2`, border `#fecaca`.

## Typography

- **Font Family**: Modern system sans stack: `Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`. Tabular figures (`tnum`) for IDs, numbers, and dates.
- **Scale**:
  - Display: 1.875rem (30px), bold, -0.025em tracking.
  - Section Headings: 1.25rem (20px), semibold, -0.015em tracking.
  - Subheadings: 1rem (16px), semibold.
  - Body: 0.875rem (14px), regular, 1.5 line height.
  - Metadata / Pills: 0.75rem (12px), medium/semibold.

## Layout

- **Web Portal**: Centered max-width container (`max-w-5xl`), generous vertical breathing room (`py-8 sm:py-12`), 12-column responsive grid on tablet/desktop, clean stacked layouts on mobile.
- **Desktop Console**: Two-column layout with 240px dark institutional sidebar (`#0f172a`) and flexible content canvas with standard 24px padding. Split master-detail views for quick inspection without navigation loss.

## Elevation & Depth

- Restrained elevation system:
  - Low elevation: `box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05), 0 1px 2px -1px rgba(0, 0, 0, 0.05)`
  - Card elevation: `box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.04), 0 2px 4px -2px rgba(0, 0, 0, 0.04)`
  - No harsh 0-blur block shadows. Soft, natural light from top.

## Shapes

- Rounded radii: `6px` for compact buttons, inputs, and badges; `10px` for cards and modals; `14px` for large hero containers. Full pill (`9999px`) for status chips.

## Components

- **Authored SVG Icons**: Unified 20x20 / 24x24 stroke icons (`stroke-width="1.75"`, round caps/joins). No emoji crutches.
- **Buttons**:
  - Primary: Deep slate `#1e293b` with white text, 6px radius, subtle active scale.
  - Accent: Blue `#2563eb` with white text for critical affirmations.
  - Secondary/Outline: White surface with `#cbd5e1` border, hover `#f8fafc`.
  - Danger: Red `#dc2626` for destructive actions with confirmation prompt.
- **Inputs**: Crisp 1px `#cbd5e1` borders with 2px `#2563eb` focus rings and clear helper text.
- **Data Tables**: Distinct header with uppercase tracking, alternating row tints, padded cells (12px vertical), hover states.

## Do's and Don'ts

- **DO**: Use crafted SVGs for all navigation, categories, and status indicators.
- **DO**: Provide clear empty states explaining how data appears.
- **DO**: Provide inline status banners explaining why certain actions are disabled.
- **DON'T**: Use emojis as primary UI icons.
- **DON'T**: Use low-contrast gray text on colored backgrounds.
- **DON'T**: Use abrasive bright gradients or arbitrary decorative shapes.
