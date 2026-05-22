import { readFileSync } from 'node:fs'

import { describe, expect, it } from 'vitest'

describe('Nuxt API proxy config', () => {
  it('proxies same-origin /api requests to the backend in local and container runs', () => {
    const source = readFileSync(new URL('../nuxt.config.ts', import.meta.url), 'utf8')

    expect(source).toContain('NUXT_API_PROXY_TARGET')
    expect(source).toContain("'/api/**'")
    expect(source).toContain('proxy: `${apiProxyTarget}/api/**`')
    expect(source).toContain('http://localhost:18000')
  })
})
