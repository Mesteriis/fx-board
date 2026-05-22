const apiProxyTarget = (process.env.NUXT_API_PROXY_TARGET || 'http://localhost:18000').replace(/\/+$/, '')

export default defineNuxtConfig({
  compatibilityDate: '2026-05-22',
  css: ['~/assets/css/main.css'],
  routeRules: {
    '/api/**': { proxy: `${apiProxyTarget}/api/**` }
  },
  app: {
    head: {
      script: [
        { src: 'https://telegram.org/js/telegram-web-app.js' },
        {
          innerHTML:
            "try{if(window.Telegram&&window.Telegram.WebApp&&window.Telegram.WebApp.initData){document.documentElement.classList.add('tg-webapp')}}catch(e){}"
        }
      ]
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
