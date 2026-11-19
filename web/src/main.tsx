import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles/base.css'
import App from './App.tsx'
import OwnKeyBox from './components/workspace/OwnKeyBox.tsx'
import { installOwnKeyFetch } from './api/ownKey.ts'

installOwnKeyFetch()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
    <OwnKeyBox />
  </StrictMode>,
)
