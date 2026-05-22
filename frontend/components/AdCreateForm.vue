<script setup lang="ts">
import type { AdCreatePayload, AdResponse, Currency, PaymentMethod } from '~/types/api'

const { apiFetch } = useApi()

const emit = defineEmits<{
  created: [ad: AdResponse]
}>()

const baseCurrency = ref<Currency>('USD')
const quoteCurrency = ref<Currency>('RUB')
const amount = ref('')
const paymentMethods = ref<PaymentMethod[]>(['CASH'])
const location = ref('')
const error = ref<string | null>(null)
const createdAd = ref<AdResponse | null>(null)
const busy = ref(false)

const paymentMethodOptions: Array<{ value: PaymentMethod; label: string }> = [
  { value: 'CASH', label: 'Наличные' },
  { value: 'TRANSFER', label: 'Перевод' },
  { value: 'CRYPTO', label: 'Крипта' }
]

const requiresMeetingPlace = computed(() => paymentMethods.value.includes('CASH'))

async function submit() {
  error.value = null
  createdAd.value = null
  if (baseCurrency.value === quoteCurrency.value) {
    error.value = 'Валюты не должны совпадать'
    return
  }
  if (!paymentMethods.value.length) {
    error.value = 'Выберите вид расчета'
    return
  }
  if (requiresMeetingPlace.value && !location.value.trim()) {
    error.value = 'Укажите место встречи'
    return
  }

  const payload: AdCreatePayload = {
    base_currency: baseCurrency.value,
    quote_currency: quoteCurrency.value,
    amount: amount.value,
    payment_method: [...paymentMethods.value],
    location: requiresMeetingPlace.value ? location.value.trim() : null
  }

  busy.value = true
  try {
    const ad = await apiFetch<AdResponse>('/ads', {
      method: 'POST',
      body: payload
    })
    createdAd.value = ad
    emit('created', ad)
  } catch (errorValue) {
    error.value = messageFromError(errorValue)
  } finally {
    busy.value = false
  }
}

function messageFromError(errorValue: unknown) {
  if (
    typeof errorValue === 'object' &&
    errorValue !== null &&
    'data' in errorValue &&
    typeof (errorValue as { data?: { message?: string } }).data?.message === 'string'
  ) {
    return (errorValue as { data: { message: string } }).data.message
  }
  return 'Не удалось создать объявление'
}
</script>

<template>
  <form class="form-panel" @submit.prevent="submit">
    <div class="form-grid form-grid--simple-ad">
      <CurrencySelector v-model="baseCurrency" label="Продаю" />
      <AmountInput v-model="amount" label="Сумма" />
      <CurrencySelector v-model="quoteCurrency" label="Хочу" />

      <label class="field">
        <span>Вид расчета</span>
        <span class="payment-methods">
          <label
            v-for="option in paymentMethodOptions"
            :key="option.value"
            class="payment-option"
          >
            <input v-model="paymentMethods" type="checkbox" :value="option.value" />
            <span>{{ option.label }}</span>
          </label>
        </span>
      </label>
    </div>

    <label v-if="requiresMeetingPlace" class="field">
      <span>Место встречи</span>
      <input v-model="location" maxlength="120" placeholder="Город / район / место" />
    </label>

    <p v-if="error" class="danger-text">{{ error }}</p>
    <p v-if="createdAd" class="success-text">Объявление #{{ createdAd.id }} опубликовано.</p>

    <button type="submit" class="primary-button form-submit" :disabled="busy">
      Опубликовать
    </button>
  </form>
</template>
