<script setup lang="ts">
import type { AdCreatePayload, AdResponse, AdSide, Currency } from '~/types/api'

const route = useRoute()
const { apiFetch } = useApi()

const emit = defineEmits<{
  created: [ad: AdResponse]
}>()

const side = ref<AdSide>(route.query.side === 'BUY' ? 'BUY' : 'SELL')
const baseCurrency = ref<Currency>('USD')
const quoteCurrency = ref<Currency>('RUB')
const amount = ref('')
const minAmount = ref('')
const maxAmount = ref('')
const rate = ref('')
const paymentMethod = ref('')
const location = ref('')
const comment = ref('')
const error = ref<string | null>(null)
const createdAd = ref<AdResponse | null>(null)
const busy = ref(false)

async function submit() {
  error.value = null
  createdAd.value = null
  if (baseCurrency.value === quoteCurrency.value) {
    error.value = 'Валюты не должны совпадать'
    return
  }

  const payload: AdCreatePayload = {
    side: side.value,
    base_currency: baseCurrency.value,
    quote_currency: quoteCurrency.value,
    amount: amount.value,
    min_amount: minAmount.value || null,
    max_amount: maxAmount.value || null,
    rate: rate.value,
    payment_method: paymentMethod.value || null,
    location: location.value || null,
    comment: comment.value || null
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
    <div class="segmented-control" aria-label="Тип объявления">
      <button type="button" :class="{ active: side === 'SELL' }" @click="side = 'SELL'">
        Продам
      </button>
      <button type="button" :class="{ active: side === 'BUY' }" @click="side = 'BUY'">
        Куплю
      </button>
    </div>

    <div class="form-grid">
      <CurrencySelector v-model="baseCurrency" label="Валюта" />
      <CurrencySelector v-model="quoteCurrency" label="Расчет" />
      <AmountInput v-model="amount" label="Сумма" />
      <RateInput v-model="rate" />
      <AmountInput v-model="minAmount" label="Минимум" />
      <AmountInput v-model="maxAmount" label="Максимум" />
    </div>

    <label class="field">
      <span>Способ расчета</span>
      <input v-model="paymentMethod" maxlength="120" placeholder="cash, bank, online" />
    </label>
    <label class="field">
      <span>Локация</span>
      <input v-model="location" maxlength="120" placeholder="Moscow / online" />
    </label>
    <label class="field">
      <span>Комментарий</span>
      <textarea v-model="comment" maxlength="500" rows="4" />
    </label>

    <p v-if="error" class="danger-text">{{ error }}</p>
    <p v-if="createdAd" class="success-text">Объявление #{{ createdAd.id }} опубликовано.</p>

    <button type="submit" class="primary-button form-submit" :disabled="busy">
      Опубликовать
    </button>
  </form>
</template>
