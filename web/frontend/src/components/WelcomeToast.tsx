import { useEffect, useState } from 'react'
import { useI18n } from '../i18n'

const STORAGE_KEY = 'wasp-welcome-seen'

/** 首次访问引导 toast，3秒自动消失 */
export default function WelcomeToast() {
  const { t } = useI18n()
  const [show, setShow] = useState(false)

  useEffect(() => {
    if (localStorage.getItem(STORAGE_KEY)) return
    setShow(true)
    localStorage.setItem(STORAGE_KEY, '1')
    const timer = setTimeout(() => setShow(false), 4000)
    return () => clearTimeout(timer)
  }, [])

  if (!show) return null

  return (
    <div className="welcome-toast" onClick={() => setShow(false)}>
      <span className="welcome-icon">💡</span>
      <span>{t.welcome}</span>
    </div>
  )
}
