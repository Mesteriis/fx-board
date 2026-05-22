<script setup lang="ts">
import type { AuthResponse } from '~/types/api'

const { webApp, getStartParam } = useTelegram()
const { apiFetch, csrfToken } = useApi()
const auth = useState<AuthResponse | null>('auth', () => null)
const loading = ref(true)
const outsideTelegram = ref(false)
const error = ref<string | null>(null)

function targetFromStartParam(startParam: string): string | null {
  if (startParam === 'new_sell') return '/app/new?side=SELL'
  if (startParam === 'new_buy') return '/app/new?side=BUY'
  if (startParam === 'new') return '/app/new'
  if (startParam === 'rates') return '/app/rates'
  if (startParam === 'rules') return '/app/rules'
  if (startParam === 'my_ads') return '/app/my'
  if (startParam === 'admin') return '/app/admin'
  if (startParam.startsWith('ad_')) return `/app/ad/${startParam.slice(3)}`
  if (startParam.startsWith('report_')) return `/app/report/${startParam.slice(7)}`
  return null
}

onMounted(async () => {
  const tg = webApp.value
  if (!tg?.initData) {
    outsideTelegram.value = true
    loading.value = false
    return
  }

  tg.ready()
  tg.expand()

  try {
    const response = await apiFetch<AuthResponse>('/auth/telegram-webapp', {
      method: 'POST',
      body: { init_data: tg.initData }
    })
    csrfToken.value = response.csrf_token
    auth.value = response
    if (!response.access.allowed) {
      await navigateTo('/app/access-denied')
      return
    }
    const startTarget = targetFromStartParam(getStartParam())
    if (startTarget && useRoute().fullPath === '/app') {
      await navigateTo(startTarget)
    }
  } catch (fetchError) {
    if (isForbidden(fetchError)) {
      await navigateTo('/app/access-denied')
      return
    }
    error.value = 'Не удалось авторизоваться через Telegram'
  } finally {
    loading.value = false
  }
})

function isForbidden(errorValue: unknown) {
  return (
    typeof errorValue === 'object' &&
    errorValue !== null &&
    'statusCode' in errorValue &&
    Number((errorValue as { statusCode?: number }).statusCode) === 403
  )
}
</script>

<template>
  <div v-if="loading" class="auth-state">Загрузка...</div>
  <AccessDeniedScreen v-else-if="outsideTelegram" mode="outside-telegram" />
  <div v-else-if="error" class="auth-state auth-state--error">{{ error }}</div>
  <slot v-else />
</template>
