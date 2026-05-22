import { readFileSync } from 'node:fs'

import { describe, expect, it } from 'vitest'

describe('/app/rates page', () => {
  it('shows one thin freshness line above the rates cards', () => {
    const source = readFileSync(new URL('../pages/app/rates.vue', import.meta.url), 'utf8')

    expect(source).toContain('rates-freshness-line')
    expect(source).toContain('Курсы актуальны на')
    expect(source).toContain('{{ rates.date }}')
  })
})
