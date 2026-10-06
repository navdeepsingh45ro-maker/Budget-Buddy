/** @type {import('tailwindcss').Config} */
// Merged from the per-page inline configs that used to ship with the Tailwind Play CDN.
// Notes on the merge:
//  - colors.secondary is #69577e everywhere (add_expense.html had the typo "#69577elo",
//    which produced no CSS, and that page never used the bare "secondary" utility).
//  - borderRadius.2xl is NOT overridden here: dashboard, history and budget_history used
//    1.25rem while the other pages used Tailwind's default 1rem. Those three pages keep
//    1.25rem through a small <style> override in their <head>.
module.exports = Object.assign({
  "darkMode": "class",
  "theme": {
    "extend": {
      "colors": {
        "on-secondary-container": "#69577f",
        "on-primary-fixed": "#231437",
        "error": "#ba1a1a",
        "on-background": "#1d1b1e",
        "secondary-container": "#e8d1ff",
        "surface-container-low": "#f8f2f6",
        "tertiary-fixed": "#eae5a3",
        "on-primary": "#ffffff",
        "on-tertiary-container": "#44410f",
        "on-tertiary-fixed": "#1e1c00",
        "tertiary-container": "#b2ae71",
        "secondary-fixed-dim": "#d4beeb",
        "primary-fixed-dim": "#d3beeb",
        "error-container": "#ffdad6",
        "inverse-on-surface": "#f5eff3",
        "on-primary-fixed-variant": "#503f65",
        "tertiary": "#63602c",
        "on-secondary": "#ffffff",
        "surface-dim": "#ded8dc",
        "outline-variant": "#cbc4ce",
        "background": "#fef8fb",
        "on-surface-variant": "#4a454d",
        "tertiary-fixed-dim": "#cec98a",
        "primary-fixed": "#eddcff",
        "outline": "#7b757e",
        "on-error": "#ffffff",
        "secondary-fixed": "#eedbff",
        "on-primary-container": "#fffbff",
        "surface-tint": "#68577e",
        "surface-container": "#f2ecf0",
        "surface-container-highest": "#e6e1e5",
        "on-error-container": "#93000a",
        "secondary": "#69577e",
        "surface-container-high": "#ece7ea",
        "primary-container": "#7f6d95",
        "primary": "#66547b",
        "on-surface": "#1d1b1e",
        "on-secondary-fixed-variant": "#503f65",
        "surface-container-lowest": "#ffffff",
        "surface": "#fef8fb",
        "on-tertiary": "#ffffff",
        "surface-bright": "#fef8fb",
        "inverse-primary": "#d3beeb",
        "surface-variant": "#e6e1e5",
        "inverse-surface": "#323033",
        "on-secondary-fixed": "#231437",
        "on-tertiary-fixed-variant": "#4b4816"
      },
      "borderRadius": {
        "DEFAULT": "0.25rem",
        "lg": "0.5rem",
        "xl": "0.75rem",
        "full": "9999px"
      },
      "spacing": {
        "md": "24px",
        "margin-mobile": "16px",
        "xl": "48px",
        "base": "4px",
        "margin-desktop": "40px",
        "lg": "32px",
        "sm": "16px",
        "gutter": "24px",
        "xs": "8px"
      },
      "fontFamily": {
        "headline-xl": [
          "Plus Jakarta Sans"
        ],
        "body-lg": [
          "Inter"
        ],
        "label-md": [
          "Inter"
        ],
        "body-md": [
          "Inter"
        ],
        "headline-xl-mobile": [
          "Plus Jakarta Sans"
        ],
        "headline-sm": [
          "Plus Jakarta Sans"
        ],
        "headline-lg-mobile": [
          "Plus Jakarta Sans"
        ],
        "headline-md": [
          "Plus Jakarta Sans"
        ],
        "body-sm": [
          "Inter"
        ],
        "headline-lg": [
          "Plus Jakarta Sans"
        ]
      },
      "fontSize": {
        "headline-xl": [
          "40px",
          {
            "lineHeight": "48px",
            "letterSpacing": "-0.02em",
            "fontWeight": "700"
          }
        ],
        "body-lg": [
          "18px",
          {
            "lineHeight": "28px",
            "fontWeight": "400"
          }
        ],
        "label-md": [
          "14px",
          {
            "lineHeight": "16px",
            "letterSpacing": "0.05em",
            "fontWeight": "600"
          }
        ],
        "body-md": [
          "16px",
          {
            "lineHeight": "24px",
            "fontWeight": "400"
          }
        ],
        "headline-xl-mobile": [
          "32px",
          {
            "lineHeight": "40px",
            "fontWeight": "700"
          }
        ],
        "headline-sm": [
          "20px",
          {
            "lineHeight": "28px",
            "fontWeight": "600"
          }
        ],
        "headline-lg-mobile": [
          "28px",
          {
            "lineHeight": "36px",
            "fontWeight": "700"
          }
        ],
        "headline-md": [
          "24px",
          {
            "lineHeight": "32px",
            "fontWeight": "600"
          }
        ],
        "body-sm": [
          "14px",
          {
            "lineHeight": "20px",
            "fontWeight": "400"
          }
        ],
        "headline-lg": [
          "32px",
          {
            "lineHeight": "40px",
            "letterSpacing": "-0.01em",
            "fontWeight": "700"
          }
        ]
      }
    }
  }
}, {
  content: ["./HTML's/**/*.html", "./Javascript's/**/*.js"],
  safelist: [],
  plugins: [require('@tailwindcss/forms'), require('@tailwindcss/container-queries')],
});
