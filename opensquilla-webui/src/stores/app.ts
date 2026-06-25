import { ref, computed, watch } from 'vue'
import { defineStore } from 'pinia'
import { getPlatform } from '@/platform'
import i18n, {
  resolveInitialLocale,
  loadLocaleMessages,
  isSupportedLocale,
  type LocaleCode,
} from '@/i18n'

export type ThemeMode = 'light' | 'dark' | 'system'

type FeatureWindow = Window & {
  OPENSQUILLA_FEATURES?: Record<string, boolean>
}

export const useAppStore = defineStore('app', () => {
  const theme = ref<ThemeMode>('system')
  // Active UI locale. Mirrors the theme pattern: localStorage is the source of
  // truth, set instantly with no save, applied to <html lang>/dir and the
  // vue-i18n instance. The sidebar/topbar switcher and the Settings Appearance
  // Language row both write through setLocale, so they can never drift.
  const locale = ref<LocaleCode>('en')
  const sidebarOpen = ref(true)
  const sidebarHovered = ref(false)
  const approvalCount = ref(0)
  const settingsOpen = ref(false)
  // Section the settings dialog should land on: a section id, 'auto'
  // (first not-ready section), or null for the default first section.
  const settingsSection = ref<string | null>(null)

  const systemDark = ref<boolean>(
    window.matchMedia('(prefers-color-scheme: dark)').matches
  )

  const resolvedTheme = computed<'light' | 'dark'>(() => {
    if (theme.value !== 'system') return theme.value
    return systemDark.value ? 'dark' : 'light'
  })

  let mq: MediaQueryList | null = null
  let mqHandler: ((e: MediaQueryListEvent) => void) | null = null
  let themeWatchStop: (() => void) | null = null

  function applyTheme() {
    document.documentElement.setAttribute('data-theme', resolvedTheme.value)
  }

  function initTheme() {
    try {
      const saved = localStorage.getItem('opensquilla-theme') as ThemeMode | null
      if (saved && ['light', 'dark', 'system'].includes(saved)) {
        theme.value = saved
      }
    } catch {
      // ignore
    }

    if (!themeWatchStop) {
      themeWatchStop = watch(resolvedTheme, applyTheme, { immediate: true })
    } else {
      applyTheme()
    }

    if (mq) return // idempotent
    mq = window.matchMedia('(prefers-color-scheme: dark)')
    mqHandler = (e: MediaQueryListEvent) => {
      systemDark.value = e.matches
    }
    if (mq.addEventListener) mq.addEventListener('change', mqHandler)
    else if (mq.addListener) mq.addListener(mqHandler)
  }

  function destroyTheme() {
    if (mq && mqHandler) {
      if (mq.removeEventListener) mq.removeEventListener('change', mqHandler)
      else if (mq.removeListener) mq.removeListener(mqHandler)
    }
    mq = null
    mqHandler = null
    if (themeWatchStop) {
      themeWatchStop()
      themeWatchStop = null
    }
  }

  function setTheme(mode: ThemeMode) {
    theme.value = mode
    try { localStorage.setItem('opensquilla-theme', mode) } catch {}
  }

  function cycleTheme() {
    const order: ThemeMode[] = ['light', 'dark', 'system']
    const next = order[(order.indexOf(theme.value) + 1) % order.length]
    setTheme(next)
  }

  function applyLocale(code: LocaleCode) {
    i18n.global.locale.value = code
    document.documentElement.setAttribute('lang', code)
    document.documentElement.setAttribute('dir', 'ltr')
  }

  // Resolve and apply the startup locale (saved → OS locale → data-locale →
  // <html lang> → navigator → en). Loads the locale chunk before applying so the
  // first paint is never half-translated; a failed chunk load falls back to en.
  // Does NOT write localStorage — it only reflects what is already chosen.
  async function initLocale() {
    let osLocale: string | undefined
    try {
      osLocale = await getPlatform().getOsLocale()
    } catch {
      osLocale = undefined
    }
    const resolved = resolveInitialLocale(osLocale)
    try {
      await loadLocaleMessages(resolved)
      locale.value = resolved
      applyLocale(resolved)
    } catch {
      locale.value = 'en'
      applyLocale('en')
    }
  }

  async function setLocale(code: LocaleCode) {
    if (!isSupportedLocale(code)) return
    let target = code
    try {
      await loadLocaleMessages(target)
    } catch {
      target = 'en'
    }
    locale.value = target
    try { localStorage.setItem('opensquilla-locale', target) } catch {}
    applyLocale(target)
  }

  function setSidebarOpen(open: boolean) {
    sidebarOpen.value = open
    if (!open) sidebarHovered.value = false
  }

  function toggleSidebar() {
    sidebarOpen.value = !sidebarOpen.value
    sidebarHovered.value = false
  }

  function setSidebarHovered(hovered: boolean) {
    sidebarHovered.value = hovered
  }

  function setApprovalCount(count: number) {
    approvalCount.value = count
  }

  function setSettingsOpen(open: boolean, section: string | null = null) {
    settingsOpen.value = open
    settingsSection.value = open ? section : null
  }

  const features = ref<Record<string, boolean>>({
    tokenViz: false,
    contractDebug: false,
    // MetaSkill run-history drawer + toolbar button: on by default so the run
    // history is reachable out of the box. Operators can disable it via
    // window.OPENSQUILLA_FEATURES. The preflight + ribbon cards are always-on
    // (driven by stream events) regardless of this flag.
    metaRuns: true,
    ...((window as FeatureWindow).OPENSQUILLA_FEATURES || {}),
  })

  return {
    theme,
    locale,
    resolvedTheme,
    sidebarOpen,
    sidebarHovered,
    approvalCount,
    settingsOpen,
    settingsSection,
    features,
    initTheme,
    destroyTheme,
    setTheme,
    cycleTheme,
    initLocale,
    setLocale,
    setSidebarOpen,
    toggleSidebar,
    setSidebarHovered,
    setApprovalCount,
    setSettingsOpen,
  }
})
