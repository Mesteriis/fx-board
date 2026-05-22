import { readFileSync } from 'node:fs'

import { describe, expect, it } from 'vitest'

describe('ad create form', () => {
  it('uses the simplified sell-offer payload and only keeps payment plus cash meeting place', () => {
    const source = readFileSync(new URL('../components/AdCreateForm.vue', import.meta.url), 'utf8')

    expect(source).not.toContain('AdSide')
    expect(source).not.toContain('side:')
    expect(source).not.toContain('segmented-control')
    expect(source).not.toContain('min_amount')
    expect(source).not.toContain('max_amount')
    expect(source).not.toContain('comment')
    expect(source).toContain('paymentMethods')
    expect(source).toContain('paymentMethodOptions')
    expect(source).toContain('Место встречи')
    expect(source).toContain("paymentMethods.value.includes('CASH')")
    expect(source).toContain("'CRYPTO'")
    expect(source).not.toContain('ONLINE')
    expect(source).not.toContain('<select')
  })
})
