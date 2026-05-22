import { readFileSync } from 'node:fs'

import { describe, expect, it } from 'vitest'

describe('app shell telegram layout', () => {
  it('hides the web header and exposes a Telegram close button only in WebApp mode', () => {
    const source = readFileSync(new URL('../components/AppShell.vue', import.meta.url), 'utf8')
    const css = readFileSync(new URL('../assets/css/main.css', import.meta.url), 'utf8')
    const config = readFileSync(new URL('../nuxt.config.ts', import.meta.url), 'utf8')

    expect(source).toContain('isTelegramWebApp')
    expect(source).toContain('v-if="isTelegramWebApp"')
    expect(source).toContain('v-if="!isTelegramWebApp"')
    expect(source).toContain('closeWebApp')
    expect(source).toContain('Закрыть приложение')
    expect(source).toContain('telegram-close-button')
    expect(css).toContain('.tg-webapp .app-header')
    expect(css).toContain('.app-shell--telegram .app-main')
    expect(config).toContain("document.documentElement.classList.add('tg-webapp')")
  })
})
