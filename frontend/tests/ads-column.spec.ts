import { readFileSync } from 'node:fs'

import { describe, expect, it } from 'vitest'

describe('ads column', () => {
  it('renders the board as a plain list without a visible heading counter', () => {
    const source = readFileSync(new URL('../components/AdsColumn.vue', import.meta.url), 'utf8')
    const boardSource = readFileSync(new URL('../components/AdsBoard.vue', import.meta.url), 'utf8')

    expect(source).not.toContain('column-title')
    expect(source).not.toContain('{{ title }}')
    expect(source).not.toContain('<span>{{ ads.length }}</span>')
    expect(boardSource).not.toContain('title="Объявления"')
  })
})
