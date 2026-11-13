import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App.tsx';
import { LanguageProvider } from './context/LanguageContext';
import { AuthProvider } from './context/AuthContext';
import { PWAProvider } from './context/PWAContext';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <LanguageProvider>
      <AuthProvider>
        <PWAProvider>
          <App />
        </PWAProvider>
      </AuthProvider>
    </LanguageProvider>
  </StrictMode>,
);

