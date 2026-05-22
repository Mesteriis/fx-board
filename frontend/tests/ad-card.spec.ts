import { readFileSync } from 'node:fs'

import { describe, expect, it } from 'vitest'

describe('ad card', () => {
  it('shows a simple sell offer without old limit/comment fields', () => {
    const source = readFileSync(new URL('../components/AdCard.vue', import.meta.url), 'utf8')

    expect(source).toContain('ad-offer-line')
    expect(source).toContain('Цена и условия')
    expect(source).toContain('Цена')
    expect(source).toContain('quotePrice')
    expect(source).toContain('paymentMethodText')
    expect(source).toContain('Крипта')
    expect(source).toContain('Расчет')
    expect(source).toContain('Не указан')
    expect(source).toContain('contactNotice')
    expect(source).toContain('response.message')
    expect(source).toContain('Не удалось отправить сообщение')
    expect(source).toContain('Отправить контакт продавцу')
    expect(source).toContain('ad-action-button--contact')
    expect(source).toContain('ad-action-button--report')
    expect(source).not.toContain('openTelegramLink')
    expect(source).not.toContain('telegram_url')
    expect(source).not.toContain('Продам')
    expect(source).not.toContain('Хочу')
    expect(source).not.toContain('Автор')
    expect(source).not.toContain('Курс')
    expect(source).not.toContain('authorLabel')
    expect(source).not.toContain('#{{ ad.id }}')
    expect(source).not.toContain('ad-id')
    expect(source).not.toContain('sideLabel')
    expect(source).not.toContain('side-pill')
    expect(source).not.toContain('Лимиты')
    expect(source).not.toContain('ad.min_amount')
    expect(source).not.toContain('ad.max_amount')
    expect(source).not.toContain('ad.comment')
  })
})
