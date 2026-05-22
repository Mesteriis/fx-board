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
const { openTelegramLink } = useTelegram()
const contactError = ref<string | null>(null)
const busy = ref(false)

const sideLabel = computed(() => (props.ad.side === 'SELL' ? 'Продажа' : 'Покупка'))
const authorLabel = computed(() => {
  if (props.ad.author?.username) return `@${props.ad.author.username}`
  return 'Автор через Telegram'
})

async function contactAuthor() {
  contactError.value = null
  busy.value = true
  try {
    const response = await apiFetch<ContactAttemptResponse>(`/ads/${props.ad.id}/contact`, {
      method: 'POST'
    })
    openTelegramLink(response.telegram_url)
  } catch (errorValue) {
    if (isStatus(errorValue, 403)) {
      contactError.value = 'Контакт недоступен'
    } else {
      contactError.value = 'Не удалось открыть контакт'
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

function money(value: string | null) {
  if (!value) return null
  return Number(value).toLocaleString('ru-RU', { maximumFractionDigits: 8 })
}
</script>

<template>
  <article class="ad-card">
    <div class="ad-card__top">
      <span :class="['side-pill', ad.side === 'SELL' ? 'side-pill--sell' : 'side-pill--buy']">
        {{ sideLabel }}
      </span>
      <NuxtLink :to="`/app/ad/${ad.id}`" class="ad-id">#{{ ad.id }}</NuxtLink>
    </div>

    <div class="ad-pair">{{ ad.base_currency }}/{{ ad.quote_currency }}</div>
    <div class="ad-amount">{{ money(ad.amount) }} {{ ad.base_currency }}</div>

    <dl class="ad-meta">
      <div>
        <dt>Курс</dt>
        <dd>{{ money(ad.rate) }}</dd>
      </div>
      <div v-if="ad.min_amount || ad.max_amount">
        <dt>Лимиты</dt>
        <dd>{{ money(ad.min_amount) || '0' }} - {{ money(ad.max_amount) || money(ad.amount) }}</dd>
      </div>
      <div v-if="ad.payment_method">
        <dt>Расчет</dt>
        <dd>{{ ad.payment_method }}</dd>
      </div>
      <div v-if="ad.location">
        <dt>Локация</dt>
        <dd>{{ ad.location }}</dd>
      </div>
      <div>
        <dt>Автор</dt>
        <dd>{{ authorLabel }}</dd>
      </div>
    </dl>

    <p v-if="ad.comment" class="ad-comment">{{ ad.comment }}</p>
    <p v-if="contactError" class="danger-text">{{ contactError }}</p>

    <div class="ad-actions">
      <button type="button" class="primary-button" :disabled="busy" @click="contactAuthor">
        Написать
      </button>
      <NuxtLink class="ghost-button" :to="`/app/report/${ad.id}`">Пожаловаться</NuxtLink>
      <button
        v-if="showRevoke && ad.status === 'ACTIVE'"
        type="button"
        class="danger-button"
        :disabled="busy"
        @click="revokeAd"
      >
        Отозвать
      </button>
    </div>
  </article>
</template>
