import { defineConfig, presetUno, presetAttributify, presetIcons } from 'unocss'
import presetWebFonts from '@unocss/preset-web-fonts'
import { icons as carbonIcons } from '@iconify-json/carbon'

export default defineConfig({
  presets: [
    presetUno(),
    presetAttributify(),
    presetIcons({
      scale: 1.2,
      warn: true,
      collections: {
        carbon: () => carbonIcons,
      },
    }),
    presetWebFonts({
      provider: 'google',
      fonts: {
        sans:    'Manrope:300,400,500,600,700,800',
        display: 'Manrope:300,400,500,600,700,800',
        mono:    'JetBrains Mono:400,500,600',
      },
    }),
  ],

  // ── Theme tokens — Premium Enterprise Data aesthetic ───────────────────────
  theme: {
    colors: {
      // Warm Backgrounds & Surfaces
      bg:            '#F5F3EE',   // Warm off-white (paper)
      surface:       '#FFFFFF',   // Pure white card background
      'surface-soft':'#FBFAF6',   // Slight warm tint for hover states

      // Text (Warm Inks)
      text: {
        primary:   '#141414',   // Deep ink
        secondary: '#5B5A52',   // Soft ink
        tertiary:  '#8F8C81',   // Faint ink
        disabled:  '#CFC9B8',   // Disabled/border-strong
      },

      // Domain Accents — Schedule A / Supply / Primary Data
      accent: {
        DEFAULT: '#1D5F5E',
        hover:   '#174E4D',
        soft:    '#D4E4E2',
      },

      // Domain Accents — Schedule B / Execution / Primary Action
      'accent-b': {
        DEFAULT: '#C17841',
        hover:   '#A9653A',
        soft:    '#F2DFCC',
      },

      // Semantic (muted, professional)
      success: '#5E8858',
      warning: '#D89B3C',
      danger:  '#B63A2E',
      neutral: '#9B958A',

      // Borders
      border:         '#E6E2D7',
      'border-strong':'#CFC9B8',

      // Dark mode surfaces
      dark: {
        bg:            '#141414',
        surface:       '#1E1E1E',
        elevated:      '#2A2A2A',
        'surface-soft':'#252525',
        accent:        '#2A9D8F',  // Lighter teal for dark bg
        'accent-b':    '#D4915A',  // Lighter orange for dark bg
      },

      // Legacy aliases (kept for compatibility)
      light: { bg: '#F5F3EE', surface: '#FFFFFF' },
      brand: { primary: '#1D5F5E' },
    },

    // Sharper radii for data-dense UI
    borderRadius: {
      sm:   '2px',
      md:   '4px',
      lg:   '6px',
      xl:   '8px',
      '2xl':'12px',
      pill: '9999px',
      full: '9999px',
    },

    // Subdued, warmer shadows
    boxShadow: {
      xs:         '0 1px 2px rgba(20,20,20,0.04)',
      sm:         '0 2px 4px rgba(20,20,20,0.06)',
      md:         '0 4px 8px rgba(20,20,20,0.06)',
      lg:         '0 8px 16px rgba(20,20,20,0.08)',
      accent:     '0 4px 14px rgba(29,95,94,0.15)',
      'accent-b': '0 4px 14px rgba(193,120,65,0.15)',
    },

    // Transition timing
    transitionDuration: {
      fast: '150ms',
      base: '200ms',
      slow: '300ms',
    },

    // Typography
    fontFamily: {
      sans:    ['Manrope', 'Inter', 'system-ui', 'sans-serif'],
      display: ['Manrope', 'Inter', 'system-ui', 'sans-serif'],
      mono:    ['JetBrains Mono', 'Menlo', 'monospace'],
    },
  },

  // ── Shortcuts — data-UI focused component aliases ──────────────────────────
  shortcuts: {
    // Layout
    'flex-center':  'flex items-center justify-center',
    'flex-between': 'flex items-center justify-between',
    'flex-start':   'flex items-center justify-start',

    // Navigation
    'nav-item':        'flex items-center gap-3 px-3 py-2 rounded-md text-text-tertiary hover:bg-surface-soft hover:text-text-primary dark:text-[#8F8C81] dark:hover:bg-[#252525] dark:hover:text-[#F5F3EE] transition-all duration-fast font-medium cursor-pointer select-none',
    'nav-item-active': 'flex items-center gap-3 px-3 py-2 rounded-md bg-accent-soft text-accent dark:bg-[#2A9D8F]/20 dark:text-[#2A9D8F] transition-all duration-fast font-medium cursor-pointer select-none',

    // Surfaces
    'page-card':  'bg-surface dark:bg-[#1E1E1E] border border-border dark:border-[#2A2A2A] rounded-lg shadow-sm min-h-full w-full flex flex-col overflow-hidden',
    'page-header':'px-8 pt-7 pb-5 border-b border-border dark:border-[#2A2A2A]',
    'card-data':  'bg-surface dark:bg-[#1E1E1E] border border-border dark:border-[#2A2A2A] rounded-lg shadow-xs p-4 flex flex-col',

    // Buttons
    'btn-primary':   'inline-flex items-center justify-center gap-1.5 rounded-md bg-accent-b text-white font-semibold text-sm px-4 py-2 transition-all hover:bg-accent-b-hover hover:-translate-y-px hover:shadow-accent-b active:translate-y-0 disabled:opacity-40 disabled:cursor-not-allowed disabled:transform-none',
    'btn-secondary': 'inline-flex items-center justify-center gap-1.5 rounded-md bg-surface dark:bg-[#1E1E1E] border border-border-strong dark:border-[#2A2A2A] text-text-primary dark:text-[#F5F3EE] font-semibold text-sm px-4 py-2 transition-all hover:bg-surface-soft dark:hover:bg-[#252525] active:bg-border disabled:opacity-40 disabled:cursor-not-allowed',
    'btn-ghost':     'inline-flex items-center justify-center gap-1.5 rounded-md text-accent font-semibold text-sm px-3 py-2 transition-all hover:bg-accent-soft active:opacity-70',
    'btn-danger':    'inline-flex items-center justify-center gap-1.5 rounded-md bg-danger text-white font-semibold text-sm px-4 py-2 transition-all hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed',

    // Form Inputs
    'input-data': 'w-full bg-surface dark:bg-[#1E1E1E] border border-border-strong dark:border-[#2A2A2A] rounded-md px-3 py-2 text-sm text-text-primary dark:text-[#F5F3EE] placeholder-text-disabled focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent transition-all',

    // Badges
    'badge-teal':    'inline-flex items-center gap-1.5 bg-accent-soft border border-accent/20 rounded-sm px-2.5 py-1 text-xs font-bold text-accent',
    'badge-orange':  'inline-flex items-center gap-1.5 bg-accent-b-soft border border-accent-b/20 rounded-sm px-2.5 py-1 text-xs font-bold text-accent-b',
    'badge-neutral': 'inline-flex items-center gap-1.5 bg-border/40 border border-border-strong rounded-sm px-2.5 py-1 text-xs font-bold text-text-tertiary',
    'badge-success': 'inline-flex items-center gap-1.5 bg-success/10 border border-success/20 rounded-sm px-2.5 py-1 text-xs font-bold text-success',
    'badge-danger':  'inline-flex items-center gap-1.5 bg-danger/10 border border-danger/20 rounded-sm px-2.5 py-1 text-xs font-bold text-danger',

    // Data-specific utilities
    'section-label': 'text-[10px] font-bold text-text-tertiary uppercase tracking-widest',
    'kpi-value':     'text-2xl font-bold text-text-primary tracking-tight font-mono tabular-nums',
    'tnum':          'tabular-nums',
    'loa-tag':       'text-[11px] font-semibold text-accent bg-accent-soft px-2 py-0.5 rounded-sm whitespace-nowrap',
    'glass-surface': 'bg-surface/80 dark:bg-[#1E1E1E]/80 backdrop-blur-xl border border-border dark:border-[#2A2A2A]',

    // Legacy Apple shortcuts — aliases so existing templates keep working
    'btn-apple':       'btn-primary',
    'btn-apple-dark':  'btn-secondary',
    'btn-apple-ghost': 'btn-ghost',
    'input-apple':     'input-data',
    'card-apple':      'card-data',
    'card-apple-hover':'card-data transition-all hover:-translate-y-0.5 cursor-pointer',
    'soft-shadow':     'shadow-sm',
    'med-shadow':      'shadow-md',
    'lift-shadow':     'shadow-lg',
    'badge-blue':      'badge-teal',
    'badge-green':     'badge-success',
    'badge-gray':      'badge-neutral',
  },

  // Safelist utility classes that are generated dynamically and might be purged
  safelist: [
    // Progress bar widths (0–100 in steps of 5)
    ...Array.from({ length: 21 }, (_, i) => `w-[${i * 5}%]`),
    // Icon animation
    'animate-spin',
    // Dark mode class on <html>
    'dark',
    // Dark button background (used in dynamic :class bindings — must be safelisted)
    'bg-dark-active',
    // Carbon icons used dynamically (e.g. :class="item.icon" in Sidebar)
    'i-carbon-dashboard',
    'i-carbon-catalog',
    'i-carbon-chart-bar',
    'i-carbon-edit',
    'i-carbon-receipt',
    'i-carbon-document',
    'i-carbon-document-pdf',
    'i-carbon-document-unknown',
    'i-carbon-add-alt',
    'i-carbon-add',
    'i-carbon-add-filled',
    'i-carbon-settings',
    'i-carbon-flash',
    'i-carbon-moon',
    'i-carbon-sun',
    'i-carbon-user',
    'i-carbon-overflow-menu-vertical',
    'i-carbon-chevron-down',
    'i-carbon-chevron-right',
    'i-carbon-chevron-up',
    'i-carbon-arrow-left',
    'i-carbon-arrow-down',
    'i-carbon-arrows-vertical',
    'i-carbon-search',
    'i-carbon-filter',
    'i-carbon-close',
    'i-carbon-trash-can',
    'i-carbon-checkmark',
    'i-carbon-checkmark-filled',
    'i-carbon-checkmark-outline',
    'i-carbon-warning-alt',
    'i-carbon-warning-filled',
    'i-carbon-circle-dash',
    'i-carbon-upload',
    'i-carbon-tag',
    'i-carbon-link',
    'i-carbon-list',
    'i-carbon-location',
    'i-carbon-package',
    'i-carbon-calendar',
    'i-carbon-construction',
    'i-carbon-chart-evaluation',
    'i-carbon-chat',
  ],
})
