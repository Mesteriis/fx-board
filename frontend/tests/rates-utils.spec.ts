import { describe, expect, it } from 'vitest'

import {
  CURRENCY_META,
  SUPPORTED_CURRENCIES,
  buildDisplayedRates,
  convertCurrencyAmount,
  resolveReferenceRate,
  splitRatePair
} from '../utils/rates'

const referenceRates = [
  { pair: 'EUR/RUB', rate: '82.5445' },
  { pair: 'EUR/USD', rate: '1.1592' },
  { pair: 'AR/USD', rate: '2.5000' },
  { pair: 'USD/EUR', rate: '0.8627' },
  { pair: 'USD/RUB', rate: '71.2090' },
  { pair: 'USDT/USD', rate: '1.0000' }
]

describe('rates utilities', () => {
  it('resolves direct, reverse, and USD-cross rates', () => {
    expect(resolveReferenceRate(referenceRates, 'USD', 'RUB')).toBeCloseTo(71.209)
    expect(resolveReferenceRate(referenceRates, 'RUB', 'USD')).toBeCloseTo(1 / 71.209)
    expect(resolveReferenceRate(referenceRates, 'EUR', 'USDT')).toBeCloseTo(1.1592)
    expect(resolveReferenceRate(referenceRates, 'AR', 'RUB')).toBeCloseTo(178.0225)
    expect(resolveReferenceRate(referenceRates, 'USD', 'AR')).toBeCloseTo(0.4)
  })

  it('converts amounts using resolved reference rates', () => {
    expect(convertCurrencyAmount(100, 'USD', 'RUB', referenceRates)).toBeCloseTo(7120.9)
    expect(convertCurrencyAmount(10, 'EUR', 'USDT', referenceRates)).toBeCloseTo(11.592)
    expect(convertCurrencyAmount(2, 'AR', 'USD', referenceRates)).toBeCloseTo(5)
  })

  it('exposes currency metadata and pair parsing for the UI', () => {
    expect(SUPPORTED_CURRENCIES).toContain('AR')
    expect(CURRENCY_META.AR.symbol).toBe('AR')
    expect(CURRENCY_META.USDT.symbol).toBe('₮')
    expect(splitRatePair('USD/RUB')).toEqual(['USD', 'RUB'])
    expect(splitRatePair('BAD/RUB')).toBeNull()
  })

  it('builds a display list relative to the selected quote currency', () => {
    expect(buildDisplayedRates(referenceRates, 'RUB')).toEqual([
      { pair: 'USD/RUB', rate: '71.2090' },
      { pair: 'EUR/RUB', rate: '82.5445' },
      { pair: 'USDT/RUB', rate: '71.2090' },
      { pair: 'USDC/RUB', rate: '71.2090' },
      { pair: 'AR/RUB', rate: '178.0225' }
    ])

    expect(buildDisplayedRates(referenceRates, 'USD')).toEqual([
      { pair: 'EUR/USD', rate: '1.1592' },
      { pair: 'RUB/USD', rate: '0.0140' },
      { pair: 'USDT/USD', rate: '1.0000' },
      { pair: 'USDC/USD', rate: '1.0000' },
      { pair: 'AR/USD', rate: '2.5000' }
    ])
  })

  it('does not show misleading inverse crypto rows when RUB is selected', () => {
    const displayedRates = buildDisplayedRates(referenceRates, 'RUB')

    expect(displayedRates).toContainEqual({ pair: 'AR/RUB', rate: '178.0225' })
    expect(displayedRates).not.toContainEqual({ pair: 'RUB/AR', rate: '0.0056' })
  })
})
