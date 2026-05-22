import { readFileSync } from 'node:fs'

import { describe, expect, it } from 'vitest'

describe('rates widget component', () => {
  it('lets the user choose the displayed quote currency in the heading', () => {
    const source = readFileSync(new URL('../components/RatesWidget.vue', import.meta.url), 'utf8')

    expect(source).toContain('selectedQuoteCurrency')
    expect(source).toContain('buildDisplayedRates')
    expect(source).toContain('rates-heading-controls')
    expect(source).toContain('aria-label="Валюта сравнения"')
    expect(source).toContain('<h2>Курсы</h2>')
    expect(source).not.toContain('Справочные курсы')
    expect(source).not.toContain('{{ rates.date }}')
  })
})
