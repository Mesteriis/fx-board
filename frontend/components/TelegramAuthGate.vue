<script setup lang="ts">
import type { AuthResponse } from '~/types/api'

const route = useRoute()
const { webApp, getStartParam } = useTelegram()
const { apiFetch, csrfToken } = useApi()
const auth = useState<AuthResponse | null>('auth', () => null)
const loading = ref(true)
const outsideTelegram = ref(false)
const error = ref<string | null>(null)

function targetFromStartParam(startParam: string): string | null {
  if (startParam === 'new_sell') return '/app/new'
  if (startParam === 'new_buy') return '/app/new'
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
  const devTelegramId = firstQueryValue(route.query.dev_tg_id)
  const devToken = firstQueryValue(route.query.dev_token)
  if (devTelegramId && devToken) {
    try {
      const params = new URLSearchParams({ tg_id: devTelegramId, dev_token: devToken })
      const response = await apiFetch<AuthResponse>(`/auth/dev?${params.toString()}`, {
        method: 'POST'
      })
      await applyAuthResponse(response)
    } catch (fetchError) {
      if (isForbidden(fetchError)) {
        await navigateTo('/app/access-denied')
        return
      }
      error.value = 'Не удалось авторизоваться в dev-режиме'
    } finally {
      loading.value = false
    }
    return
  }

  if (auth.value) {
    await applyAuthResponse(auth.value)
    loading.value = false
    return
  }

  try {
    const response = await apiFetch<AuthResponse>('/auth/me')
    await applyAuthResponse(response)
    loading.value = false
    return
  } catch (fetchError) {
    if (isForbidden(fetchError)) {
      await navigateTo('/app/access-denied')
      return
    }
    if (!isUnauthorized(fetchError)) {
      error.value = 'Не удалось проверить сессию'
      loading.value = false
      return
    }
  }

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
    await applyAuthResponse(response)
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

async function applyAuthResponse(response: AuthResponse) {
  csrfToken.value = response.csrf_token
  auth.value = response
  if (!response.access.allowed) {
    await navigateTo('/app/access-denied')
    return
  }
  const startTarget = targetFromStartParam(getStartParam())
  if (startTarget && route.fullPath === '/app') {
    await navigateTo(startTarget)
  }
}

function firstQueryValue(value: unknown) {
  return typeof value === 'string' ? value : null
}

function isForbidden(errorValue: unknown) {
  return errorStatusCode(errorValue) === 403
}

function isUnauthorized(errorValue: unknown) {
  return errorStatusCode(errorValue) === 401
}

function errorStatusCode(errorValue: unknown) {
  if (typeof errorValue !== 'object' || errorValue === null || !('statusCode' in errorValue)) {
    return null
  }
  const statusCode = Number((errorValue as { statusCode?: number }).statusCode)
  return Number.isFinite(statusCode) ? statusCode : null
}
</script>

<template>
  <div v-if="loading" class="auth-state">Загрузка...</div>
  <AccessDeniedScreen v-else-if="outsideTelegram" mode="outside-telegram" />
  <div v-else-if="error" class="auth-state auth-state--error">{{ error }}</div>
  <slot v-else />
</template>
