import '@fontsource/roboto/300.css';
import '@fontsource/roboto/400.css';
import '@fontsource/roboto/500.css';
import '@fontsource/roboto-mono/400.css';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { App } from './App';
import './styles/tokens.css';
import './styles/base.css';
import './styles/layout.css';
import './styles/components.css';
import './styles/tables.css';
import './styles/explore.css';
import './styles/instrument.css';
import './styles/charts.css';
import './styles/derivatives.css';
import './styles/knowledge.css';
import './styles/screener.css';
import './styles/chat.css';
import './styles/login.css';
import { motionController } from './utilities/motionController';
import { themeController } from './utilities/themeController';

themeController.applyStoredChoice();
motionController.applyStoredChoice();

const rootElement = document.getElementById('root');
if (rootElement === null) {
  throw new Error('The page has no #root element.');
}
createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
