import { readFileSync } from 'node:fs'

import { describe, expect, it } from 'vitest'

describe('/app page shell', () => {
  it('does not render non-board widgets on the board page', () => {
    const pageSource = readFileSync(new URL('../pages/app/index.vue', import.meta.url), 'utf8')

    expect(pageSource).not.toContain('hero-panel')
    expect(pageSource).not.toContain('Покупка и продажа валюты')
    expect(pageSource).not.toContain('Объявления без платежей и эскроу')
    expect(pageSource).not.toContain('RatesWidget')
    expect(pageSource).not.toContain('/rates')
  })
})
