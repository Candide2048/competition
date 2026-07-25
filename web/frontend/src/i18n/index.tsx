import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'
import zh, { type I18nKeys } from './zh'
import en from './en'

type Locale = 'zh' | 'en'
const STORAGE_KEY = 'wasp-lang'

interface I18nCtx {
  locale: Locale
  t: I18nKeys
  setLocale: (l: Locale) => void
  toggle: () => void
}

const I18nContext = createContext<I18nCtx>({
  locale: 'zh',
  t: zh,
  setLocale: () => {},
  toggle: () => {},
})

const dicts: Record<Locale, I18nKeys> = { zh, en }

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(() => {
    const saved = localStorage.getItem(STORAGE_KEY)
    return saved === 'en' ? 'en' : 'zh'
  })

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l)
    localStorage.setItem(STORAGE_KEY, l)
  }, [])

  const toggle = useCallback(() => {
    setLocaleState((prev) => {
      const next = prev === 'zh' ? 'en' : 'zh'
      localStorage.setItem(STORAGE_KEY, next)
      return next
    })
  }, [])

  return (
    <I18nContext.Provider value={{ locale, t: dicts[locale], setLocale, toggle }}>
      {children}
    </I18nContext.Provider>
  )
}

export function useI18n() {
  return useContext(I18nContext)
}
