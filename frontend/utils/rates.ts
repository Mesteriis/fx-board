import type { Currency, RateItem } from '../types/api'

export const SUPPORTED_CURRENCIES: readonly Currency[] = ['USD', 'EUR', 'RUB', 'USDT', 'USDC', 'AR']

export const CURRENCY_META: Record<Currency, { symbol: string; label: string }> = {
  USD: { symbol: '$', label: 'US Dollar' },
  EUR: { symbol: '€', label: 'Euro' },
  RUB: { symbol: '₽', label: 'Russian Ruble' },
  USDT: { symbol: '₮', label: 'Tether USD' },
  USDC: { symbol: 'C', label: 'USD Coin' },
  AR: { symbol: 'AR', label: 'Arweave' }
}

const USD_PEGGED_CURRENCIES = new Set<Currency>(['USD', 'USDT', 'USDC'])
const currencySet = new Set<string>(SUPPORTED_CURRENCIES)

type RateLike = Pick<RateItem, 'pair' | 'rate'>

export function splitRatePair(pair: string): [Currency, Currency] | null {
  const [base, quote] = pair.split('/')
  if (!isSupportedCurrency(base) || !isSupportedCurrency(quote)) {
    return null
  }
  return [base, quote]
}

export function resolveReferenceRate(
  rates: readonly RateLike[],
  baseCurrency: Currency,
  quoteCurrency: Currency
): number | null {
  if (baseCurrency === quoteCurrency) {
    return 1
  }

  const map = buildRateMap(rates)
  const directRate = directOrReverseRate(map, baseCurrency, quoteCurrency)
  if (directRate !== null) {
    return directRate
  }

  const baseToUsd = currencyToUsdRate(map, baseCurrency)
  const quoteToUsd = currencyToUsdRate(map, quoteCurrency)
  if (baseToUsd === null || quoteToUsd === null) {
    return null
  }
  return baseToUsd / quoteToUsd
}

export function convertCurrencyAmount(
  amount: number,
  baseCurrency: Currency,
  quoteCurrency: Currency,
  rates: readonly RateLike[]
): number | null {
  if (!Number.isFinite(amount) || amount < 0) {
    return null
  }
  const rate = resolveReferenceRate(rates, baseCurrency, quoteCurrency)
  return rate === null ? null : amount * rate
}

export function buildDisplayedRates(
  rates: readonly RateLike[],
  quoteCurrency: Currency
): RateItem[] {
  return SUPPORTED_CURRENCIES.map((baseCurrency) => {
    if (baseCurrency === quoteCurrency) {
      return null
    }

    const rate = resolveReferenceRate(rates, baseCurrency, quoteCurrency)
    if (rate === null) {
      return null
    }

    return {
      pair: `${baseCurrency}/${quoteCurrency}`,
      rate: formatDisplayRate(rate)
    }
  }).filter((item): item is RateItem => item !== null)
}

export function formatRateNumber(value: number): string {
  return new Intl.NumberFormat('ru-RU', {
    minimumFractionDigits: 4,
    maximumFractionDigits: 8
  }).format(value)
}

export function formatConvertedAmount(value: number): string {
  return new Intl.NumberFormat('ru-RU', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 4
  }).format(value)
}

function formatDisplayRate(value: number): string {
  return value.toFixed(4)
}

function isSupportedCurrency(value: string | undefined): value is Currency {
  return typeof value === 'string' && currencySet.has(value)
}

function buildRateMap(rates: readonly RateLike[]): Map<string, number> {
  const map = new Map<string, number>()
  for (const item of rates) {
    const rate = Number(item.rate)
    if (Number.isFinite(rate) && rate > 0 && splitRatePair(item.pair)) {
      map.set(item.pair, rate)
    }
  }
  return map
}

function directOrReverseRate(
  rates: Map<string, number>,
  baseCurrency: Currency,
  quoteCurrency: Currency
): number | null {
  const directPair = `${baseCurrency}/${quoteCurrency}`
  const direct = rates.get(directPair)
  if (direct !== undefined) {
    return direct
  }

  const reversePair = `${quoteCurrency}/${baseCurrency}`
  const reverse = rates.get(reversePair)
  if (reverse !== undefined) {
    return 1 / reverse
  }

  return null
}

function currencyToUsdRate(rates: Map<string, number>, currency: Currency): number | null {
  if (USD_PEGGED_CURRENCIES.has(currency)) {
    return 1
  }
  return directOrReverseRate(rates, currency, 'USD')
}
