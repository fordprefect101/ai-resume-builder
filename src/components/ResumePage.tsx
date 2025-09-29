import { LitElement, css, html } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import './index.ts'; // Import all components to ensure they are registered

@customElement('resume-page')
export class ResumePage extends LitElement {
  @state() private resumeData: any = null;
  @state() private schema: any = null;
  @state() private loading = true;
  @state() private extracting = false;
  @state() private saving = false;
  @state() private error = '';
  @state() private successMessage = '';
  @state() private progress = 0;
  @state() private conversationHistory: any[] = [];
  @state() private showPreview = false;
  @state() private selectedTemplate: 'modern' | 'classic' = 'modern';
  @state() private renderKey = 0;
  @state() private dataVersion = 0;
  private formRendererRef: any = null;

  private lastUpdateTime = 0;

  private isArrayDataChange = (oldData: any, newData: any): boolean => {
    // Check if any array fields have changed length
    const arrayFields = ['employment', 'education', 'projects', 'certifications', 'languages', 'references', 'achievements', 'publications', 'hobbies', 'trainings'];
    
    for (const field of arrayFields) {
      const oldArray = oldData[field];
      const newArray = newData[field];
      
      // If both are arrays and have different lengths, it's an array operation
      if (Array.isArray(oldArray) && Array.isArray(newArray) && oldArray.length !== newArray.length) {
        console.log(`📄 ResumePage - Array operation detected on ${field}: ${oldArray.length} -> ${newArray.length}`);
        return true;
      }
    }
    
    return false;
  }

  static styles = css`
    :host {
      display: block;
      width: 100%;
      min-height: 100vh;
      background: #f6f8fa;
      color: #222;
      font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    }
    
    .container {
      padding: 2rem;
      max-width: 900px;
      margin: 0 auto;
      background: #fff;
      border-radius: 1rem;
      box-shadow: 0 4px 24px 0 rgba(0,0,0,0.07);
    }
    
    .header {
      text-align: center;
      margin-bottom: 2rem;
      border-bottom: 1px solid #e5e7eb;
      padding-bottom: 1rem;
    }
    
    .loading, .extracting {
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      height: 50vh;
      font-size: 1.2em;
    }
    
    .progress-container {
      width: 300px;
      margin: 2rem 0;
    }
    
    .progress-bar {
      width: 100%;
      height: 8px;
      background: #e5e7eb;
      border-radius: 4px;
      overflow: hidden;
    }
    
    .progress-fill {
      height: 100%;
      background: linear-gradient(90deg, #3b82f6, #06b6d4);
      border-radius: 4px;
      transition: width 0.3s ease;
    }
    
    .progress-text {
      text-align: center;
      margin-top: 1rem;
      font-size: 0.9em;
      color: #666;
    }
    
    .error {
      color: #ef4444;
      text-align: center;
      padding: 2rem;
      font-size: 1.1em;
      background: #fff1f2;
      border: 1px solid #fecaca;
      border-radius: 0.5rem;
      margin: 1rem 0;
    }
    
    .error-actions {
      margin-top: 2rem;
      display: flex;
      justify-content: center;
      gap: 1rem;
    }
    
    .error-button {
      padding: 0.5rem 1.5rem;
      background: #ef4444;
      color: white;
      border: none;
      border-radius: 4px;
      cursor: pointer;
      font-size: 1em;
      transition: background 0.2s;
    }
    .error-button:hover {
      background: #dc2626;
    }
    
    .resume-content {
      background: #f3f4f6;
      border-radius: 8px;
      padding: 1.5rem;
      overflow: auto;
      max-height: 70vh;
    }
    
    .back-button {
      position: fixed;
      top: 1rem;
      left: 1rem;
      padding: 0.5rem 1.5rem;
      background: #e5e7eb;
      color: #222;
      border: none;
      border-radius: 4px;
      cursor: pointer;
      font-size: 1em;
      box-shadow: 0 2px 8px 0 rgba(0,0,0,0.04);
      transition: background 0.2s;
    }
    .back-button:hover {
      background: #d1d5db;
    }
    
    pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      line-height: 1.4;
    }
    
    .spinner {
      width: 40px;
      height: 40px;
      border: 4px solid #e5e7eb;
      border-top: 4px solid #3b82f6;
      border-radius: 50%;
      animation: spin 1s linear infinite;
      margin-bottom: 1rem;
    }
    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
    
    .header-actions {
      display: flex;
      gap: 1rem;
      margin-top: 1rem;
      justify-content: center;
    }
    .btn {
      padding: 0.75rem 2rem;
      border: none;
      border-radius: 0.5rem;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
      font-size: 1rem;
      box-shadow: 0 2px 8px 0 rgba(0,0,0,0.04);
    }
    .btn-primary {
      background: #3b82f6;
      color: white;
    }
    .btn-primary:hover {
      background: #2563eb;
    }
    .btn-secondary {
      background: #e5e7eb;
      color: #222;
    }
    .btn-secondary:hover {
      background: #d1d5db;
    }
    .btn-success {
      background: #10b981;
      color: white;
    }
    .btn-success:hover {
      background: #059669;
    }
    .success {
      color: #10b981;
      text-align: center;
      padding: 2rem;
      font-size: 1.1em;
      background: #f0fdf4;
      border: 1px solid #6ee7b7;
      border-radius: 0.5rem;
      margin: 1rem 0;
    }

    .template-selection {
      margin: 1rem 0;
      padding: 1rem;
      background: #f8fafc;
      border-radius: 0.5rem;
      border: 1px solid #e2e8f0;
    }

    .template-selection h3 {
      margin: 0 0 1rem 0;
      font-size: 1rem;
      font-weight: 600;
      color: #374151;
    }

    .template-options {
      display: flex;
      gap: 1rem;
      justify-content: center;
    }

    .template-option {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 1rem;
      border: 2px solid #e2e8f0;
      border-radius: 0.5rem;
      background: white;
      cursor: pointer;
      transition: all 0.2s;
      min-width: 120px;
    }

    .template-option:hover {
      border-color: #3b82f6;
      transform: translateY(-2px);
    }

    .template-option.selected {
      border-color: #3b82f6;
      background: #eff6ff;
    }

    .template-option img {
      width: 60px;
      height: 80px;
      object-fit: cover;
      border-radius: 0.25rem;
      margin-bottom: 0.5rem;
      border: 1px solid #e2e8f0;
    }

    .template-option .template-name {
      font-size: 0.875rem;
      font-weight: 600;
      color: #374151;
      text-align: center;
    }

    .template-option .template-description {
      font-size: 0.75rem;
      color: #6b7280;
      text-align: center;
      margin-top: 0.25rem;
    }

    .bottom-actions {
      margin-top: 3rem;
      padding-top: 2rem;
      border-top: 1px solid #e5e7eb;
      display: flex;
      flex-direction: column;
      gap: 2rem;
      align-items: center;
    }

    .preview-section {
      display: flex;
      justify-content: center;
      width: 100%;
    }

    .preview-section .btn {
      padding: 1rem 3rem;
      font-size: 1.1rem;
      font-weight: 700;
    }

    .preview-container {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: #f6f8fa;
      z-index: 1000;
      overflow: auto;
    }
    .preview-header {
      position: sticky;
      top: 0;
      background: #fff;
      padding: 1rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid #e5e7eb;
    }
    .preview-content {
      padding: 2rem;
      color: #222;
    }
  `;

  connectedCallback() {
    super.connectedCallback();
    this.handleRoute();
    window.addEventListener('hashchange', this._onHashChange);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    window.removeEventListener('hashchange', this._onHashChange);
  }

  private _onHashChange = () => {
    this.handleRoute();
  };

  private handleRoute() {
    // Always reset state on route change
    this.loading = false;
    this.extracting = false;
    this.error = '';
    this.successMessage = '';
    this.resumeData = null;
    this.schema = null;
    this.progress = 0;
    this.conversationHistory = [];
    this.showPreview = false;

    const hash = window.location.hash;
    const urlParams = new URLSearchParams(hash.split('?')[1] || '');
    const sessionId = urlParams.get('sessionId');
    const conversation = urlParams.get('conversation');

    console.log('ResumePage: Hash:', hash, 'SessionId:', sessionId, 'Conversation:', !!conversation, 'Conversation length:', conversation?.length);

    if (sessionId && conversation && conversation.trim() !== '') {
      // We have conversation data, need to extract resume
      try {
        const decodedConversation = decodeURIComponent(conversation);
        const parsedConversation = JSON.parse(decodedConversation);
        
        // Validate that it's actually an array
        if (!Array.isArray(parsedConversation)) {
          throw new Error('Conversation data is not an array');
        }
        
        this.extractResume(sessionId, parsedConversation);
      } catch (error) {
        console.error('Error parsing conversation data:', error);
        this.error = 'Invalid conversation data format. Please try again.';
        // If we have a sessionId but conversation is corrupted, try to load existing data
        if (sessionId) {
          console.log('Attempting to load existing resume data for session:', sessionId);
          this.loadResumeData(sessionId);
        }
      }
    } else if (sessionId) {
      // We have session ID, try to load existing resume
      console.log('Calling loadResumeData', sessionId);
      this.loadResumeData(sessionId);
    } else {
      // No valid parameters, go back to main page
      this.goBack();
    }
  }

  private async extractResume(sessionId: string, conversation: any[]): Promise<void> {
    try {
      this.extracting = true;
      this.loading = false;
      this.error = '';
      this.conversationHistory = conversation;
      
      // Simulate progress updates
      this.progress = 10;
      await this.delay(500);
      this.progress = 30;
      await this.delay(500);
      this.progress = 60;
      
      console.log('Extracting resume for session:', sessionId);
      const response = await fetch('http://localhost:8081/extract-resume', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          conversation: conversation,
          sessionId: sessionId
        })
      });
      
      this.progress = 90;
      await this.delay(300);
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Resume extraction failed: ${response.status} - ${errorText}`);
      }
      
      const result = await response.json();
      this.progress = 100;
      await this.delay(200);
      
      console.log('Resume extraction successful, session ID:', result.sessionId);
      
      // Navigate to the resume page with the session ID
      window.location.hash = `#resume?sessionId=${result.sessionId}`;
      
    } catch (err: any) {
      console.error('Resume extraction error:', err);
      this.error = err.message || 'Failed to extract resume';
      this.extracting = false;
    }
  }

  private async loadResumeData(sessionId: string): Promise<void> {
    try {
      this.loading = true;
      this.error = '';
      

      
      // Load resume data
      const resumeResponse = await fetch(`http://localhost:8081/resume/${sessionId}`);
      if (!resumeResponse.ok) {
        throw new Error('Failed to load resume data');
      }
      const rawData = await resumeResponse.json();
      let resumeData = rawData.properties ? rawData.properties : rawData;
      resumeData = extractValues(resumeData);
      this.resumeData = resumeData;
      console.log('📊 Resume Data Loaded:', this.resumeData);
      
      // Load schema
      const schemaResponse = await fetch('/resume-schema.json');
      if (!schemaResponse.ok) {
        throw new Error('Failed to load schema');
      }
      this.schema = await schemaResponse.json();
      console.log('📋 Schema Loaded:', this.schema);
      
      this.loading = false;
    } catch (err: any) {
      console.error('Load resume error:', err);
      this.error = err.message || 'Failed to load resume';
      this.loading = false;
    }
  }



  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  private goBack() {
    // Navigate back to the main page
    window.location.hash = '';
  }

  private retryExtraction() {
    if (this.conversationHistory.length > 0) {
      const sessionId = crypto.randomUUID();
      this.extractResume(sessionId, this.conversationHistory);
    } else {
      this.goBack();
    }
  }

  private async saveResume(): Promise<void> {
    try {
      this.saving = true;
      this.error = '';
      this.successMessage = '';
      
      const urlParams = new URLSearchParams(window.location.hash.split('?')[1] || '');
      const sessionId = urlParams.get('sessionId');
      
      if (!sessionId) {
        throw new Error('No session ID found');
      }
      
      const response = await fetch(`http://localhost:8081/resume/${sessionId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(this.resumeData)
      });
      
      if (!response.ok) {
        throw new Error('Failed to save resume');
      }
      
      this.successMessage = 'Resume saved successfully!';
      this.saving = false;
      
      // Clear success message after 3 seconds
      setTimeout(() => {
        this.successMessage = '';
      }, 3000);
      
    } catch (err: any) {
      console.error('Save resume error:', err);
      this.error = err.message || 'Failed to save resume';
      this.saving = false;
    }
  }

  private handleDataChange = (newData: any) => {
    console.log('📄 ResumePage - handleDataChange called');
    console.log('📄 ResumePage - New data type:', typeof newData);
    console.log('📄 ResumePage - New data keys:', Object.keys(newData || {}));
    
    // Throttle updates to prevent too many rapid changes, but allow array operations
    const now = Date.now();
    const timeSinceLastUpdate = now - this.lastUpdateTime;
    
    // Check if this is an array operation by comparing with current data
    const isArrayOperation = this.resumeData && this.isArrayDataChange(this.resumeData, newData);
    
    if (!isArrayOperation && timeSinceLastUpdate < 100) { // 100ms throttle for non-array operations
      console.log('📄 ResumePage - Update throttled, skipping');
      return;
    }
    this.lastUpdateTime = now;
    
    console.log('📄 ResumePage - New data:', newData);
    // Create a new object reference for Lit reactivity (without JSON serialization)
    this.resumeData = { ...newData };
    // Safely increment renderKey
    console.log('📄 ResumePage - Current renderKey before increment:', this.renderKey, 'type:', typeof this.renderKey);
    if (typeof this.renderKey === 'number' && !isNaN(this.renderKey)) {
      this.renderKey = this.renderKey + 1;
    } else {
      console.warn('📄 ResumePage - Render key was invalid, resetting to 1');
      this.renderKey = 1;
    }
    
    console.log('📄 ResumePage - Resume data updated:', this.resumeData);
    console.log('📄 ResumePage - Photo URL in updated data:', this.resumeData?.personalDetails?.basicDetails?.photoUrl);
    console.log('📄 ResumePage - Render key updated:', this.renderKey);
    // Log array sections to verify they're being updated
    console.log('📄 ResumePage - Achievements:', this.resumeData?.achievements);
    console.log('📄 ResumePage - Publications:', this.resumeData?.publications);
    console.log('📄 ResumePage - Hobbies:', this.resumeData?.hobbies);
    console.log('📄 ResumePage - Trainings:', this.resumeData?.trainings);
    console.log('📄 ResumePage - Employment:', this.resumeData?.employment);
    console.log('📄 ResumePage - Education:', this.resumeData?.education);
    
    // Increment data version to force FormRenderer update
    if (typeof this.dataVersion === 'number' && !isNaN(this.dataVersion)) {
      this.dataVersion++;
    } else {
      console.warn('📄 ResumePage - Data version was invalid, resetting to 1');
      this.dataVersion = 1;
    }
    console.log('📄 ResumePage - Data version updated to:', this.dataVersion);
    
    // Call FormRenderer's direct update method if available
    console.log('📄 ResumePage - FormRenderer ref available:', !!this.formRendererRef);
    console.log('📄 ResumePage - FormRenderer ref type:', typeof this.formRendererRef);
    if (this.formRendererRef) {
      console.log('📄 ResumePage - FormRenderer has updateDataDirectly method:', typeof this.formRendererRef.updateDataDirectly);
    }
    
    // Try to get FormRenderer from DOM if ref is not available
    if (!this.formRendererRef) {
      const formRendererElement = this.shadowRoot?.querySelector('#form-renderer') as any;
      if (formRendererElement) {
        console.log('📄 ResumePage - Found FormRenderer in DOM by ID');
        this.formRendererRef = formRendererElement;
      }
    }
    
    if (this.formRendererRef && typeof this.formRendererRef.updateDataDirectly === 'function') {
      console.log('📄 ResumePage - Calling FormRenderer updateDataDirectly');
      this.formRendererRef.updateDataDirectly(this.resumeData);
    } else {
      console.log('📄 ResumePage - FormRenderer ref not available, falling back to property binding');
      // Force immediate re-render to ensure FormRenderer gets updated data
      this.requestUpdate();
      
      // Force another update after a microtask to ensure data is propagated
      queueMicrotask(() => {
        console.log('📄 ResumePage - Microtask update - Resume data:', this.resumeData);
        console.log('📄 ResumePage - Microtask update - Employment:', this.resumeData?.employment);
        this.requestUpdate();
      });
    }
  }

  private togglePreview() {
    this.showPreview = !this.showPreview;
  }

  private selectTemplate(template: 'modern' | 'classic') {
    this.selectedTemplate = template;
  }

  private resetRenderKey() {
    console.log('📄 ResumePage - Resetting renderKey to 0');
    this.renderKey = 0;
  }

  render() {
    if (this.loading) {
      return html`
        <div class="loading">
          <div class="spinner"></div>
          <p>Loading resume data...</p>
        </div>
      `;
    }

    if (this.extracting) {
      return html`
        <div class="extracting">
          <div class="spinner"></div>
          <p>Extracting resume from conversation...</p>
          <div class="progress-container">
            <div class="progress-bar">
              <div class="progress-fill" style="width: ${this.progress}%"></div>
            </div>
            <div class="progress-text">${this.progress}% complete</div>
          </div>
        </div>
      `;
    }

    if (this.error) {
      return html`
        <div class="container">
          <div class="error">
            <h3>Error</h3>
            <p>${this.error}</p>
            <div class="error-actions">
              <button class="error-button" @click="${this.retryExtraction}">
                Retry
              </button>
              <button class="error-button" @click="${this.goBack}">
                Go Back
              </button>
            </div>
          </div>
        </div>
      `;
    }

    if (this.showPreview) {
      return html`
        <div class="preview-container">
          <div class="preview-header">
            <h2>Resume Preview</h2>
            <div class="header-actions">
              <button class="btn btn-secondary" @click="${this.togglePreview}">
                Back to Edit
              </button>
              <button class="btn btn-primary" @click="${() => window.print()}">
                Print/PDF
              </button>
            </div>
          </div>
          <div class="preview-content">
            ${this.selectedTemplate === 'modern' 
              ? html`<modern-template .resumeData="${this.resumeData}"></modern-template>`
              : html`<classic-template .resumeData="${this.resumeData}"></classic-template>`
            }
          </div>
        </div>
      `;
    }

    return html`
      <button class="back-button" @click="${this.goBack}">
        ← Back
      </button>
      
      <div class="container">
        <div class="header">
          <h1>Edit Your Resume</h1>
        </div>
        
        ${this.successMessage ? html`
          <div class="success">
            ${this.successMessage}
          </div>
        ` : ''}
        
        ${this.resumeData && this.schema ? html`
          <form-renderer
            .data="${this.resumeData}"
            .schema="${this.schema}"
            .onDataChange="${this.handleDataChange}"
            .dataVersion="${this.dataVersion}"
            data-key="${this.renderKey || 0}-${this.dataVersion}"
            key="${this.renderKey || 0}-${this.dataVersion}"
            id="form-renderer"
            @form-renderer-ready="${(e: any) => {
              this.formRendererRef = e.detail.element;
              console.log('📄 ResumePage - FormRenderer ready event received, ref set:', !!e.detail.element);
              if (e.detail.element) {
                console.log('📄 ResumePage - FormRenderer element has updateDataDirectly:', typeof e.detail.element.updateDataDirectly);
              }
            }}"
          ></form-renderer>
          <!-- Debug info -->
          <div style="display: none;">
            RenderKey: ${this.renderKey}, DataVersion: ${this.dataVersion}, Key: ${this.renderKey || 0}-${this.dataVersion}
          </div>
        ` : html`
          <p>No resume data available</p>
        `}

        <!-- Template Selection and Preview Button at Bottom -->
        <div class="bottom-actions">
          <!-- Template Selection -->
          <div class="template-selection">
            <h3>Choose Your Template</h3>
            <div class="template-options">
              <div 
                class="template-option ${this.selectedTemplate === 'modern' ? 'selected' : ''}"
                @click="${() => this.selectTemplate('modern')}"
              >
                <div style="width: 60px; height: 80px; background: linear-gradient(135deg, #3b82f6, #1d4ed8); border-radius: 0.25rem; display: flex; align-items: center; justify-content: center; color: white; font-size: 0.5rem; text-align: center; line-height: 1.2;">
                  Modern<br/>Template
                </div>
                <div class="template-name">Modern</div>
                <div class="template-description">Professional with sidebar</div>
              </div>
              <div 
                class="template-option ${this.selectedTemplate === 'classic' ? 'selected' : ''}"
                @click="${() => this.selectTemplate('classic')}"
              >
                <div style="width: 60px; height: 80px; background: #1f2937; border-radius: 0.25rem; display: flex; align-items: center; justify-content: center; color: white; font-size: 0.5rem; text-align: center; line-height: 1.2;">
                  Classic<br/>Template
                </div>
                <div class="template-name">Classic</div>
                <div class="template-description">Traditional academic style</div>
              </div>
            </div>
          </div>

          <!-- Preview Button -->
          <div class="preview-section">
            <button class="btn btn-primary" @click="${this.togglePreview}">
              Preview Resume
            </button>
          </div>
        </div>
        
      </div>
    `;
  }
} 

// Utility to recursively extract only value fields from schema-like objects
function extractValues(obj: any): any {
  if (Array.isArray(obj)) {
    return obj.map(extractValues);
  } else if (obj && typeof obj === 'object') {
    if ('properties' in obj) {
      return extractValues(obj.properties);
    } else {
      const result: any = {};
      for (const key in obj) {
        if ([
          'type', 'required', 'additionalProperties', 'title', 'format', 'enum', 'items', '$schema'
        ].includes(key)) continue;
        result[key] = extractValues(obj[key]);
      }
      return result;
    }
  }
  return obj;
} 