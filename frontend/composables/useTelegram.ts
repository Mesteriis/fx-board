declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        initData: string
        startParam?: string
        colorScheme?: 'light' | 'dark'
        themeParams?: Record<string, string>
        initDataUnsafe?: {
          start_param?: string
        }
        ready: () => void
        expand: () => void
        openTelegramLink?: (url: string) => void
        close?: () => void
      }
    }
  }
}

export function useTelegram() {
  const webApp = computed(() => (import.meta.client ? window.Telegram?.WebApp ?? null : null))
  const isTelegramWebApp = computed(() => Boolean(webApp.value?.initData))

  function getStartParam() {
    const tg = window.Telegram?.WebApp
    return tg?.initDataUnsafe?.start_param || tg?.startParam || ''
  }

  function openTelegramLink(url: string) {
    const tg = window.Telegram?.WebApp
    if (tg?.openTelegramLink) {
      tg.openTelegramLink(url)
      return
    }
    window.location.href = url
  }

  function closeWebApp() {
    if (!import.meta.client) return false
    const tg = window.Telegram?.WebApp
    if (!tg?.close) return false
    tg.close()
    return true
  }

  return { webApp, isTelegramWebApp, getStartParam, openTelegramLink, closeWebApp }
}
