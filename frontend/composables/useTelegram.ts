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

  return { webApp, getStartParam, openTelegramLink }
}
