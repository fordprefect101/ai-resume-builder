// Interactive Document Widget
// This file bundles the entire Interactive Document application into a pluggable widget

// Import map for dependencies
const importMap = {
  imports: {
    "lit": "https://esm.sh/lit@^3.3.0",
    "lit/": "https://esm.sh/lit@^3.3.0/",
    "@lit/context": "https://esm.sh/@lit/context@^1.1.5",
    "three": "https://esm.sh/three@^0.176.0",
    "three/": "https://esm.sh/three@^0.176.0/"
  }
};

// Add import map to document
const importMapScript = document.createElement('script');
importMapScript.type = 'importmap';
importMapScript.textContent = JSON.stringify(importMap);
document.head.appendChild(importMapScript);

// Import dependencies
import { LitElement, css, html } from 'lit';
import { customElement, state, property } from 'lit/decorators.js';
import * as THREE from 'three';
import { GdmLiveAudio } from './src/components/GdmLiveAudio.tsx';

// Set Lit to production mode
window.lit = { devMode: false };

// Default widget styles
const WIDGET_STYLES = `
  .interactive-document-widget {
    width: 100%;
    height: 100%;
    position: relative;
    background: transparent;
    border-radius: 125px;
    overflow: hidden;
    display: block;
  }

  .widget-popup {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, 50%);
    background: transparent;
    border-radius: 125px;
    z-index: 1000;
    width: 250px;
    height: 250px;
  }

  .widget-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 999;
  }

  gdm-live-audio {
    display: block;
    width: 100%;
    height: 100%;
    position: relative;
  }

  gdm-live-audio-visuals-3d {
    display: block;
    width: 100%;
    height: 100%;
    position: absolute;
    top: 0;
    left: 0;
  }

  canvas {
    width: 250px !important;
    height: 250px !important;
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
  }
`;

export class InteractiveDocumentWidget {

  constructor(config = {}) {
    this.config = {
      ...config,
      apiKey: '',
      systemInstruction: '',
      model: config.model || 'models/gemini-live-2.5-flash-preview',
      width: config.width || '250px',
      height: config.height || '250px',
      tools: [{
        functionDeclarations: []
      }]
    };

    this.init();
  }

  async init() {
    try {
      // Create overlay
      this.overlay = document.createElement('div');
      this.overlay.className = 'widget-overlay';
      
      // Create popup container
      this.widgetContainer = document.createElement('div');
      this.widgetContainer.className = 'widget-popup';
      this.widgetContainer.style.width = this.config.width;
      this.widgetContainer.style.height = this.config.height;
      
      // Create widget content container
      const contentContainer = document.createElement('div');
      contentContainer.className = 'interactive-document-widget';
      
      // Add styles
      const style = document.createElement('style');
      style.textContent = WIDGET_STYLES;
      document.head.appendChild(style);

      // Initialize GdmLiveAudio
      this.mainElement = new GdmLiveAudio(this.config);
      
      // Listen for the custom close event from GdmLiveAudio
      this.mainElement.addEventListener('close-widget', () => {
        console.log('InteractiveDocumentWidget: close-widget event received, destroying widget.');
        this.destroy();
      });

      // Append GdmLiveAudio to contentContainer
      contentContainer.appendChild(this.mainElement);
      
      // Add to document - Append content to widgetContainer
      this.widgetContainer.appendChild(contentContainer);
      
      // Add to document - Append overlay and widgetContainer to body
      document.body.appendChild(this.overlay);
      document.body.appendChild(this.widgetContainer);

      // Directly trigger startStreaming
      if (this.mainElement && typeof this.mainElement.startStreaming === 'function') {
        await this.mainElement.startStreaming();
        console.log('[Widget] Called startStreaming() on child');
      }

      console.log('Widget initialized with API key:', !!this.config.apiKey);

    } catch (error) {
      console.error('Failed to initialize widget:', error);
      this.handleError(error);
    }
  }

  // Public methods for widget control
  async start() {
    if (this.mainElement && typeof this.mainElement.startStreaming === 'function') {
      await this.mainElement.startStreaming();
    }
  }

  async stop() {
    if (this.mainElement && typeof this.mainElement.stopStreaming === 'function') {
      await this.mainElement.stopStreaming();
    }
  }

  async reset() {
    if (this.mainElement && typeof this.mainElement.reset === 'function') {
      await this.mainElement.reset();
    }
  }

  // Error handling
  handleError(error) {
    console.error('Interactive Document Widget Error:', error);
    if (this.widgetContainer) {
      const errorDiv = document.createElement('div');
      errorDiv.className = 'error-message';
      errorDiv.textContent = `Widget Error: ${error.message}`;
      this.widgetContainer.appendChild(errorDiv);
    }
  }

  // Cleanup method
  destroy() {
    console.log('InteractiveDocumentWidget destroy called.');
    if (this.mainElement) {
      console.log('InteractiveDocumentWidget: mainElement exists.');
      if (typeof this.mainElement.stopStreaming === 'function') {
        this.mainElement.stopStreaming();
        console.log('InteractiveDocumentWidget: stopStreaming called.');
      }
      // Call the reset method on the GdmLiveAudio component to close the session
      if (typeof this.mainElement.reset === 'function') {
          console.log('InteractiveDocumentWidget: calling mainElement.reset().');
          this.mainElement.reset();
      } else {
          console.log('InteractiveDocumentWidget: mainElement.reset is not a function.');
      }
    } else {
        console.log('InteractiveDocumentWidget: mainElement does not exist.');
    }

    if (this.overlay) {
      this.overlay.remove();
      console.log('InteractiveDocumentWidget: overlay removed.');
    }
    if (this.widgetContainer) {
      this.widgetContainer.remove();
      console.log('InteractiveDocumentWidget: widgetContainer removed.');
    }
    
    // Dispatch widget-closed event to reset the main page UI
    window.dispatchEvent(new CustomEvent('widget-closed'));
    console.log('InteractiveDocumentWidget: widget-closed event dispatched.');
  }
}