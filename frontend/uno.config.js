import { defineConfig, presetUno, presetAttributify, presetIcons } from 'unocss'
import presetWebFonts from '@unocss/preset-web-fonts'

export default defineConfig({
  presets: [
    presetUno(),
    presetAttributify(),
    presetIcons({
      scale: 1.2,
      warn: true,
    }),
    presetWebFonts({
      provider: 'google',
      // Inter as the web-font fallback — SF Pro renders natively on Apple devices
      // via the system font stack defined in style.css
      fonts: {
        sans: 'Inter:300,400,500,600,700',
      },
    }),
  ],

  // ── Theme tokens — mirrors CSS custom properties in style.css ──────────────
  theme: {
    colors: {
      // Page & surface
      bg:      '#f5f5f7',           // Apple light page background
      surface: '#ffffff',
      'surface-secondary': '#f5f5f7',

      // Text scale
      text: {
        primary:   '#1d1d1f',
        secondary: '#6e6e73',
        tertiary:  '#86868b',
        disabled:  '#c7c7cc',
      },

      // Apple accent blue family
      accent: {
        DEFAULT: '#0071e3',
        hover:   '#0077ed',
        active:  '#006ecd',
        subtle:  'rgba(0,113,227,0.10)',
      },

      // Semantic
      success: '#34c759',
      warning: '#ff9500',
      danger:  '#ff3b30',
      purple:  '#5856d6',

      // Borders
      border:    'rgba(0,0,0,0.08)',
      separator: '#e5e5ea',

      // Dark mode surfaces (use with .dark class)
      dark: {
        bg:        '#000000',
        surface:   '#1c1c1e',
        elevated:  '#2c2c2e',
        active:    '#1d1d1f',        // kept for existing usage
        accent:    '#2997ff',        // Apple blue shifts on dark bg
      },

      // Legacy aliases (kept so existing templates don't break)
      light: {
        bg:      '#f5f5f7',
        surface: '#ffffff',
      },
      brand: {
        primary: '#0071e3',
      },
    },

    // Border radii matching CSS custom props
    borderRadius: {
      sm:   '8px',
      md:   '12px',
      lg:   '16px',
      xl:   '20px',
      '2xl':'24px',
      pill: '9999px',
      full: '9999px',
    },

    // Box shadows matching CSS custom props
    boxShadow: {
      xs:     '0 1px 3px rgba(0,0,0,0.06)',
      sm:     '0 4px 14px rgba(0,0,0,0.06)',
      md:     '0 8px 24px rgba(0,0,0,0.08)',
      lg:     '0 16px 40px rgba(0,0,0,0.10)',
      accent: '0 8px 20px rgba(0,113,227,0.22)',
      danger: '0 8px 20px rgba(255,59,48,0.22)',
    },

    // Transition timing
    transitionDuration: {
      fast: '150ms',
      base: '200ms',
      slow: '300ms',
    },

    // Font family — system stack first so SF Pro is used on Apple devices
    fontFamily: {
      sans:    ['-apple-system', 'BlinkMacSystemFont', 'SF Pro Text', 'Segoe UI', 'Inter', 'system-ui', 'sans-serif'],
      display: ['-apple-system', 'BlinkMacSystemFont', 'SF Pro Display', 'Segoe UI', 'Inter', 'system-ui', 'sans-serif'],
    },
  },

  // ── Shortcuts — component-level aliases for multi-utility patterns ──────────
  shortcuts: {
    // Layout helpers
    'flex-center':  'flex items-center justify-center',
    'flex-between': 'flex items-center justify-between',
    'flex-start':   'flex items-center justify-start',

    // Apple-style shadows
    'soft-shadow':  'shadow-[0_4px_14px_rgba(0,0,0,0.06)]',
    'med-shadow':   'shadow-[0_8px_24px_rgba(0,0,0,0.08)]',
    'lift-shadow':  'shadow-[0_16px_40px_rgba(0,0,0,0.10)]',

    // Sidebar navigation items
    'nav-item':        'flex items-center gap-3 px-4 py-3 rounded-xl text-[#86868b] hover:bg-[#f5f5f7] hover:text-[#1d1d1f] transition-all duration-300 font-medium cursor-pointer select-none',
    'nav-item-active': 'flex items-center gap-3 px-4 py-3 rounded-xl bg-[#0071e3]/10 text-[#0071e3] transition-all duration-300 font-medium cursor-pointer select-none',

    // Page card wrapper (the white rounded card that fills each page)
    'page-card': 'bg-white rounded-2xl soft-shadow min-h-full w-full flex flex-col overflow-hidden',

    // Page header block inside a page-card
    'page-header': 'px-8 pt-7 pb-5 border-b border-gray-100',

    // Apple-style pill button — primary blue
    'btn-apple': 'inline-flex items-center justify-center gap-1.5 rounded-full bg-[#0071e3] text-white font-semibold text-sm px-5 py-2.5 transition-all hover:bg-[#0077ed] hover:-translate-y-px hover:shadow-[0_8px_20px_rgba(0,113,227,0.22)] active:bg-[#006ecd] active:translate-y-0 disabled:opacity-40 disabled:cursor-not-allowed disabled:transform-none',

    // Dark pill button (used on Add New Work upload button)
    'btn-apple-dark': 'inline-flex items-center justify-center gap-1.5 rounded-full bg-[#1d1d1f] text-white font-semibold text-sm px-5 py-2.5 transition-all hover:bg-[#2d2d2f] hover:-translate-y-px hover:shadow-[0_8px_20px_rgba(0,0,0,0.25)] active:bg-[#1d1d1f] active:translate-y-0 disabled:opacity-40 disabled:cursor-not-allowed',

    // Ghost pill button — blue text, no border
    'btn-apple-ghost': 'inline-flex items-center justify-center gap-1.5 rounded-full text-[#0071e3] font-semibold text-sm px-4 py-2 transition-all hover:bg-[#0071e3]/10 active:opacity-70',

    // Apple-style search / input wrap
    'input-apple': 'flex items-center bg-gray-50 border border-gray-200 rounded-2xl px-5 py-3 focus-within:ring-2 focus-within:ring-[#0071e3]/20 focus-within:border-[#0071e3] focus-within:bg-white transition-all',

    // Card (white surface, soft shadow, rounded-2xl)
    'card-apple':          'bg-white rounded-2xl soft-shadow border border-gray-100 overflow-hidden',
    'card-apple-hover':    'bg-white rounded-2xl soft-shadow border border-gray-100 overflow-hidden transition-all hover:-translate-y-1 hover:med-shadow cursor-pointer',

    // Stat / pill badge
    'badge-blue':   'flex items-center gap-2 bg-blue-50 border border-blue-100 rounded-xl px-4 py-2 text-xs font-semibold text-blue-700',
    'badge-green':  'flex items-center gap-2 bg-green-50 border border-green-100 rounded-xl px-4 py-2 text-xs font-semibold text-green-700',
    'badge-orange': 'flex items-center gap-2 bg-orange-50 border border-orange-100 rounded-xl px-4 py-2 text-xs font-semibold text-orange-700',
    'badge-gray':   'flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-xl px-4 py-2 text-xs font-semibold text-gray-600',

    // Glass surface (frosted, for modals / overlays)
    'glass-surface': 'bg-white/80 backdrop-blur-xl border border-white/60',

    // Section label (tiny uppercase, Apple style)
    'section-label': 'text-[10px] font-bold text-gray-400 uppercase tracking-widest',

    // LOA number pill tag
    'loa-tag': 'text-[11px] font-semibold text-[#0071e3] bg-[#0071e3]/10 px-2 py-0.5 rounded-full whitespace-nowrap',
  },

  // Safelist utility classes that are generated dynamically and might be purged
  safelist: [
    // Progress bar widths (0–100 in steps of 5)
    ...Array.from({ length: 21 }, (_, i) => `w-[${i * 5}%]`),
    // Icon animation
    'animate-spin',
    // Dark mode class on <html>
    'dark',
  ],
})
