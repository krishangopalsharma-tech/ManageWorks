import { ref, watchEffect } from 'vue'

const isDark = ref(localStorage.getItem('mw-theme') === 'dark')

function apply(dark) {
  const html = document.documentElement
  if (dark) {
    html.setAttribute('data-theme', 'dark')
    html.classList.add('dark')
  } else {
    html.removeAttribute('data-theme')
    html.classList.remove('dark')
  }
  localStorage.setItem('mw-theme', dark ? 'dark' : 'light')
}

watchEffect(() => apply(isDark.value))

export function useTheme() {
  return {
    isDark,
    toggle() { isDark.value = !isDark.value },
  }
}
