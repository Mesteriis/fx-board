<script setup lang="ts">
import type { AdResponse, ReportCreatePayload, ReportReason, ReportResponse } from '~/types/api'

const props = defineProps<{
  ad: AdResponse
}>()

const { apiFetch } = useApi()
const reason = ref<ReportReason>('SCAM')
const comment = ref('')
const busy = ref(false)
const error = ref<string | null>(null)
const result = ref<ReportResponse | null>(null)

const reasons: Array<{ value: ReportReason; label: string }> = [
  { value: 'SCAM', label: 'Мошенничество' },
  { value: 'SPAM', label: 'Спам' },
  { value: 'WRONG_RATE', label: 'Неверный курс' },
  { value: 'OFFENSIVE', label: 'Оскорбления' },
  { value: 'DUPLICATE', label: 'Дубликат' },
  { value: 'FAKE_CONTACT', label: 'Неверный контакт' },
  { value: 'OTHER', label: 'Другое' }
]

async function submit() {
  if (!props.ad.author) {
    error.value = 'Не удалось определить автора объявления'
    return
  }

  const payload: ReportCreatePayload = {
    ad_id: props.ad.id,
    target_user_id: props.ad.author.id,
    reason: reason.value,
    comment: comment.value || null
  }

  busy.value = true
  error.value = null
  result.value = null
  try {
    result.value = await apiFetch<ReportResponse>('/reports', {
      method: 'POST',
      body: payload
    })
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
  return 'Не удалось отправить жалобу'
}
</script>

<template>
  <form class="form-panel" @submit.prevent="submit">
    <label class="field">
      <span>Причина</span>
      <select v-model="reason">
        <option v-for="item in reasons" :key="item.value" :value="item.value">
          {{ item.label }}
        </option>
      </select>
    </label>
    <label class="field">
      <span>Комментарий</span>
      <textarea v-model="comment" maxlength="500" rows="5" />
    </label>

    <p v-if="error" class="danger-text">{{ error }}</p>
    <p v-if="result" class="success-text">Жалоба #{{ result.id }} отправлена.</p>

    <button type="submit" class="danger-button form-submit" :disabled="busy">
      Отправить жалобу
    </button>
  </form>
</template>
