import { LitElement, css, html } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import './GdmLiveAudio';
import './ResumePage';

@customElement('app-router')
export class AppRouter extends LitElement {
  @state() private currentRoute = '';

  static styles = css`
    :host {
      display: block;
      width: 100%;
      height: 100vh;
    }
  `;

  connectedCallback() {
    super.connectedCallback();
    this.updateRoute();
    window.addEventListener('hashchange', () => this.updateRoute());
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    window.removeEventListener('hashchange', () => this.updateRoute());
  }

  private updateRoute() {
    const hash = window.location.hash.slice(1); // Remove the #
    this.currentRoute = hash;
  }

  render() {
    // If hash contains 'resume', show resume page
    if (this.currentRoute.includes('resume')) {
      return html`<resume-page></resume-page>`;
    }
    
    // Otherwise show the main app (GdmLiveAudio)
    return html`<gdm-live-audio></gdm-live-audio>`;
  }
} 