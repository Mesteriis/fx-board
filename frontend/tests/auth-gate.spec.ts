import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'

describe('auth gate fixture', () => {
  it('keeps frontend tests wired', () => {
    expect('Telegram Mini App').toContain('Telegram')
  })

  it('restores an existing server session before requiring Telegram initData', () => {
    const source = readFileSync(new URL('../components/TelegramAuthGate.vue', import.meta.url), 'utf8')

    expect(source).toContain("apiFetch<AuthResponse>('/auth/me')")
    expect(source.indexOf("apiFetch<AuthResponse>('/auth/me')")).toBeLessThan(
      source.indexOf('const tg = webApp.value')
    )
  })

  it('routes legacy ad creation start params to the simplified create form', () => {
    const source = readFileSync(new URL('../components/TelegramAuthGate.vue', import.meta.url), 'utf8')

    expect(source).toContain("if (startParam === 'new_sell') return '/app/new'")
    expect(source).toContain("if (startParam === 'new_buy') return '/app/new'")
    expect(source).not.toContain('side=SELL')
    expect(source).not.toContain('side=BUY')
  })
})
