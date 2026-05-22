<script setup lang="ts">
import type { Currency, RatesResponse } from '~/types/api'
import {
  SUPPORTED_CURRENCIES,
  convertCurrencyAmount,
  formatConvertedAmount,
  formatRateNumber,
  resolveReferenceRate
} from '~/utils/rates'

const props = defineProps<{
  rates: RatesResponse | null
  loading?: boolean
}>()

const amount = ref('100')
const baseCurrency = ref<Currency>('USD')
const quoteCurrency = ref<Currency>('RUB')

const numericAmount = computed(() => Number(amount.value.replace(',', '.')))
const currentRate = computed(() => {
  if (!props.rates) {
    return null
  }
  return resolveReferenceRate(props.rates.rates, baseCurrency.value, quoteCurrency.value)
})
const convertedAmount = computed(() => {
  if (!props.rates) {
    return null
  }
  return convertCurrencyAmount(
    numericAmount.value,
    baseCurrency.value,
    quoteCurrency.value,
    props.rates.rates
  )
})
const resultText = computed(() => {
  if (props.loading) {
    return 'Загружаем курсы'
  }
  if (!props.rates) {
    return 'Курсы пока недоступны'
  }
  if (convertedAmount.value === null) {
    return 'Нет курса для выбранной пары'
  }
  return `${formatConvertedAmount(convertedAmount.value)} ${quoteCurrency.value}`
})

function updateAmount(event: Event) {
  amount.value = (event.target as HTMLInputElement).value
}

function updateBaseCurrency(event: Event) {
  baseCurrency.value = (event.target as HTMLSelectElement).value as Currency
}

function updateQuoteCurrency(event: Event) {
  quoteCurrency.value = (event.target as HTMLSelectElement).value as Currency
}
</script>

<template>
  <section class="rates-converter">
    <div class="section-heading">
      <h2>Конвертер</h2>
    </div>

    <div class="converter-form">
      <div class="converter-row converter-row--single">
        <label class="field">
          Сумма
          <input
            :value="amount"
            type="number"
            min="0"
            step="0.01"
            inputmode="decimal"
            @input="updateAmount"
            @keyup="updateAmount"
          />
        </label>

        <label class="field">
          Из
          <select :value="baseCurrency" @change="updateBaseCurrency">
            <option v-for="currency in SUPPORTED_CURRENCIES" :key="currency" :value="currency">
              {{ currency }}
            </option>
          </select>
        </label>

        <label class="field">
          В
          <select :value="quoteCurrency" @change="updateQuoteCurrency">
            <option v-for="currency in SUPPORTED_CURRENCIES" :key="currency" :value="currency">
              {{ currency }}
            </option>
          </select>
        </label>
      </div>
    </div>

    <div class="conversion-result">
      <span class="muted">Итого</span>
      <strong>{{ resultText }}</strong>
      <small v-if="currentRate !== null">
        1 {{ baseCurrency }} = {{ formatRateNumber(currentRate) }} {{ quoteCurrency }}
      </small>
    </div>
  </section>
</template>
