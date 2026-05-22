import { readFileSync } from 'node:fs'

import { describe, expect, it } from 'vitest'

describe('rates converter component', () => {
  it('uses immediate conversion from a single input row without a manual button', () => {
    const source = readFileSync(new URL('../components/RatesConverter.vue', import.meta.url), 'utf8')

    expect(source).not.toContain('CONVERSION_DEBOUNCE_MS')
    expect(source).not.toContain('setTimeout')
    expect(source).toContain('converter-row--single')
    expect(source).toContain('@input="updateAmount"')
    expect(source).toContain('@keyup="updateAmount"')
    expect(source).toContain('@change="updateBaseCurrency"')
    expect(source).toContain('@change="updateQuoteCurrency"')
    expect(source).not.toContain('swap-button')
    expect(source).not.toContain('swapCurrencies')
    expect(source).not.toContain('⇄')
  })

  it('does not render the rates date inside the converter card header', () => {
    const source = readFileSync(new URL('../components/RatesConverter.vue', import.meta.url), 'utf8')

    expect(source).not.toContain('{{ rates.date }}')
  })
})
