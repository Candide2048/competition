import React from 'react'
import ReactDOM from 'react-dom/client'
import './styles/theme.css'
import './styles/app.css'
import App from './App'
import { I18nProvider } from './i18n'
import { ThemeProvider } from './hooks/useTheme'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider>
      <I18nProvider>
        <App />
      </I18nProvider>
    </ThemeProvider>
  </React.StrictMode>,
)
