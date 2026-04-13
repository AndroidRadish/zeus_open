import { createI18n } from 'vue-i18n'
import zh from './locales/zh.json'
import en from './locales/en.json'

const savedLang = typeof localStorage !== 'undefined' ? localStorage.getItem('zeus-lang') : null
const fallbackLang = 'zh'

const i18n = createI18n({
  legacy: false,
  locale: savedLang || fallbackLang,
  fallbackLocale: fallbackLang,
  messages: {
    zh,
    en,
  },
})

export default i18n
