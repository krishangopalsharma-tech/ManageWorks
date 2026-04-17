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
      fonts: {
        sans: 'Inter:300,400,500,600,700',
      },
    }),
  ],
  theme: {
    colors: {
      light: {
        bg: '#f5f5f7',
        surface: '#ffffff', 
      },
      dark: {
        active: '#1d1d1f'
      },
      brand: {
        primary: '#0071e3'
      }
    }
  },
  shortcuts: {
    'flex-center': 'flex items-center justify-center',
    'flex-between': 'flex items-center justify-between',
    'soft-shadow': 'shadow-[0_4px_14px_rgba(0,0,0,0.06)]',
    'nav-item': 'flex items-center gap-3 px-4 py-3 rounded-xl text-[#86868b] hover:bg-[#f5f5f7] hover:text-[#1d1d1f] transition-all duration-300 font-medium cursor-pointer',
    'nav-item-active': 'flex items-center gap-3 px-4 py-3 rounded-xl bg-[#0071e3]/10 text-[#0071e3] transition-all duration-300 font-medium cursor-pointer',
  }
})
