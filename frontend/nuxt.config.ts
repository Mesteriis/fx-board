export default defineNuxtConfig({
  compatibilityDate: '2026-05-22',
  css: ['~/assets/css/main.css'],
  app: {
    head: {
      script: [{ src: 'https://telegram.org/js/telegram-web-app.js' }]
    }
  },
  runtimeConfig: {
    public: {
      apiBase: '/api',
      botUsername: ''
    }
  },
  typescript: {
    strict: true
  }
})
