import { describe, expect, it } from 'vitest'

describe('auth gate fixture', () => {
  it('keeps frontend tests wired', () => {
    expect('Telegram Mini App').toContain('Telegram')
  })
})
