<script setup lang="ts">
import type { RequiredChannelResponse } from '~/types/api'

const props = withDefaults(
  defineProps<{
    mode?: 'outside-telegram' | 'missing-channels'
    channels?: RequiredChannelResponse[]
  }>(),
  {
    mode: 'missing-channels',
    channels: () => []
  }
)

const config = useRuntimeConfig()
const telegramUrl = computed(() => {
  const username = config.public.botUsername
  return username ? `https://t.me/${username}?startapp` : 'https://t.me/'
})
</script>

<template>
  <section class="empty-state">
    <h1>
      {{
        props.mode === 'outside-telegram'
          ? 'Откройте сервис через Telegram-бота'
          : 'Нет доступа к доске'
      }}
    </h1>
    <p v-if="props.mode === 'outside-telegram'">
      Авторизация работает только внутри Telegram Mini App.
    </p>
    <p v-else>Для доступа нужно состоять во всех обязательных каналах.</p>

    <div v-if="props.channels.length" class="channel-list">
      <ChannelJoinCard
        v-for="channel in props.channels"
        :key="channel.chat_id"
        :channel="channel"
      />
    </div>

    <a class="primary-button" :href="telegramUrl">Открыть в Telegram</a>
  </section>
</template>
