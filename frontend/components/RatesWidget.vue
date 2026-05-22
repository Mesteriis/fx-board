<script setup lang="ts">
import type { Currency, RatesResponse } from '~/types/api'
import { SUPPORTED_CURRENCIES, buildDisplayedRates, splitRatePair } from '~/utils/rates'

const props = defineProps<{
  rates: RatesResponse | null
  loading?: boolean
}>()

const selectedQuoteCurrency = ref<Currency>('RUB')

const decoratedRates = computed(() =>
  (props.rates ? buildDisplayedRates(props.rates.rates, selectedQuoteCurrency.value) : []).map((rate) => ({
    ...rate,
    currencies: splitRatePair(rate.pair)
  }))
)
</script>

<template>
  <section class="rates-widget">
    <div class="section-heading rates-heading">
      <h2>Курсы</h2>
      <div v-if="rates" class="rates-heading-controls">
        <select v-model="selectedQuoteCurrency" class="compact-select" aria-label="Валюта сравнения">
          <option v-for="currency in SUPPORTED_CURRENCIES" :key="currency" :value="currency">
            {{ currency }}
          </option>
        </select>
      </div>
    </div>
    <div v-if="loading" class="muted">Обновляем курсы...</div>
    <div v-else-if="rates" class="rates-grid">
      <div v-for="rate in decoratedRates" :key="rate.pair" class="rate-row">
        <div class="rate-pair">
          <span v-if="rate.currencies" class="currency-pair-icons">
            <CurrencyIcon :currency="rate.currencies[0]" />
            <CurrencyIcon :currency="rate.currencies[1]" />
          </span>
          <span class="rate-pair-code">{{ rate.pair }}</span>
        </div>
        <strong>{{ rate.rate }}</strong>
      </div>
    </div>
    <div v-else class="muted">Курсы пока недоступны.</div>
    <p v-if="rates?.is_stale" class="warning-text">
      Источник курсов недоступен, показаны последние сохраненные значения.
    </p>
  </section>
</template>
