<script setup lang="ts">
import type { RequiredChannelResponse } from '~/types/api'

defineProps<{
  channel: RequiredChannelResponse
}>()
</script>

<template>
  <article class="channel-card">
    <div>
      <strong>{{ channel.title || channel.chat_id }}</strong>
      <span>{{ channel.is_member ? 'Доступ подтвержден' : 'Нужно вступить' }}</span>
    </div>
    <a v-if="channel.chat_id.startsWith('@')" :href="`https://t.me/${channel.chat_id.slice(1)}`">
      Открыть
    </a>
  </article>
</template>
