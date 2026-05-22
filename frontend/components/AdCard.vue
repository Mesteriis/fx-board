<script setup lang="ts">
import type { AdResponse, ContactAttemptResponse } from '~/types/api'

const props = withDefaults(
  defineProps<{
    ad: AdResponse
    showRevoke?: boolean
  }>(),
  {
    showRevoke: false
  }
)

const emit = defineEmits<{
  revoked: [ad: AdResponse]
}>()

const { apiFetch } = useApi()
const contactError = ref<string | null>(null)
const contactNotice = ref<string | null>(null)
const busy = ref(false)

const paymentMethodLabel = computed(() => {
  if (!props.ad.payment_method) return 'Не указан'
  return props.ad.payment_method
    .split(',')
    .map((method) => paymentMethodText(method))
    .join(', ')
})
const quotePrice = computed(() => {
  const amount = Number(props.ad.amount)
  const rate = Number(props.ad.rate)
  if (!Number.isFinite(amount) || !Number.isFinite(rate)) return null
  return amount * rate
})

async function contactAuthor() {
  contactError.value = null
  contactNotice.value = null
  busy.value = true
  try {
    const response = await apiFetch<ContactAttemptResponse>(`/ads/${props.ad.id}/contact`, {
      method: 'POST'
    })
    contactNotice.value = response.message
  } catch (errorValue) {
    if (isStatus(errorValue, 403)) {
      contactError.value = 'Контакт недоступен'
    } else {
      contactError.value = 'Не удалось отправить сообщение'
    }
  } finally {
    busy.value = false
  }
}

async function revokeAd() {
  busy.value = true
  try {
    const ad = await apiFetch<AdResponse>(`/ads/${props.ad.id}/revoke`, {
      method: 'POST'
    })
    emit('revoked', ad)
  } finally {
    busy.value = false
  }
}

function isStatus(errorValue: unknown, statusCode: number) {
  return (
    typeof errorValue === 'object' &&
    errorValue !== null &&
    'statusCode' in errorValue &&
    Number((errorValue as { statusCode?: number }).statusCode) === statusCode
  )
}

function money(value: string | number | null) {
  if (!value) return null
  return Number(value).toLocaleString('ru-RU', { maximumFractionDigits: 8 })
}

function paymentMethodText(method: string) {
  const normalized = method.trim().toUpperCase()
  if (normalized === 'CASH') return 'Наличные'
  if (normalized === 'TRANSFER') return 'Перевод'
  if (normalized === 'CRYPTO') return 'Крипта'
  return method
}
</script>

<template>
  <article class="ad-card">
    <div class="ad-offer-line">
      {{ money(ad.amount) }} {{ ad.base_currency }} -&gt; {{ ad.quote_currency }}
    </div>

    <details class="ad-details">
      <summary>Цена и условия</summary>
      <dl class="ad-meta">
        <div v-if="quotePrice !== null">
          <dt>Цена</dt>
          <dd>{{ money(quotePrice) }} {{ ad.quote_currency }}</dd>
        </div>
        <div>
          <dt>Расчет</dt>
          <dd>{{ paymentMethodLabel }}</dd>
        </div>
        <div v-if="ad.location">
          <dt>Место встречи</dt>
          <dd>{{ ad.location }}</dd>
        </div>
      </dl>
    </details>

    <p v-if="contactError" class="danger-text">{{ contactError }}</p>
    <p v-if="contactNotice" class="success-text">{{ contactNotice }}</p>

    <div class="ad-actions">
      <button
        type="button"
        class="ad-action-button ad-action-button--contact"
        :disabled="busy"
        aria-label="Отправить контакт продавцу"
        title="Отправить контакт продавцу"
        @click="contactAuthor"
      >
        <span aria-hidden="true" class="ad-action-icon">✉</span>
      </button>
      <NuxtLink
        class="ad-action-button ad-action-button--report"
        :to="`/app/report/${ad.id}`"
        aria-label="Пожаловаться"
        title="Пожаловаться"
      >
        <span aria-hidden="true" class="ad-action-icon">!</span>
      </NuxtLink>
      <button
        v-if="showRevoke && ad.status === 'ACTIVE'"
        type="button"
        class="ad-action-button ad-action-button--revoke"
        :disabled="busy"
        @click="revokeAd"
      >
        Отозвать
      </button>
    </div>
  </article>
</template>
