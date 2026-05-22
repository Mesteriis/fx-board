import type { FetchOptions } from 'ofetch'

export function useApi() {
  const config = useRuntimeConfig()
  const csrfToken = useState<string | null>('csrf-token', () => null)

  async function apiFetch<T>(path: string, options: FetchOptions<'json'> = {}) {
    const headers = new Headers(options.headers as HeadersInit | undefined)
    if (csrfToken.value) {
      headers.set('X-CSRF-Token', csrfToken.value)
    }

    return await $fetch<T>(`${config.public.apiBase}${path}`, {
      credentials: 'include',
      ...options,
      headers
    })
  }

  return { apiFetch, csrfToken }
}
