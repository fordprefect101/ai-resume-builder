import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';

@customElement('form-renderer')
export class FormRenderer extends LitElement {
  @property({ type: Object }) data: any = {};
  @property({ type: Object }) schema: any = {};
  @property({ type: Function }) onDataChange = (data: any) => {};
  @property({ type: Number }) dataVersion = 0;
  private renderCounter = 0;
  private lastDataVersion = 0;
  private currentData: any = {};

  connectedCallback() {
    super.connectedCallback();
    console.log('🎨 FormRenderer - connectedCallback called');
    
    // Notify parent that we're ready
    this.dispatchEvent(new CustomEvent('form-renderer-ready', {
      detail: { element: this },
      bubbles: true,
      composed: true
    }));
  }

  // Public method to directly update data (bypasses property binding)
  public updateDataDirectly(newData: any) {
    console.log('🎨 FormRenderer - updateDataDirectly called');
    console.log('🎨 FormRenderer - New data:', newData);
    console.log('🎨 FormRenderer - Employment in new data:', newData?.employment);
    
    this.currentData = { ...newData };
    console.log('🎨 FormRenderer - CurrentData updated:', this.currentData);
    console.log('🎨 FormRenderer - Employment in currentData:', this.currentData?.employment);
    
    // Force re-render
    this.requestUpdate();
  }

  updated(changedProperties: Map<string, any>) {
    super.updated(changedProperties);
    console.log('🎨 FormRenderer - updated() called');
    console.log('🎨 FormRenderer - Changed properties:', Array.from(changedProperties.keys()));
    
    if (changedProperties.has('data')) {
      console.log('🎨 FormRenderer - Data property changed');
      console.log('🎨 FormRenderer - New data:', this.data);
      console.log('🎨 FormRenderer - Employment data in updated:', this.data?.employment);
      console.log('🎨 FormRenderer - Employment data length:', this.data?.employment?.length);
      console.log('🎨 FormRenderer - Forcing re-render');
      this.currentData = { ...this.data };
      this.renderCounter++;
      this.requestUpdate();
    }
    
    if (changedProperties.has('dataVersion')) {
      console.log('🎨 FormRenderer - DataVersion changed, forcing data update');
      console.log('🎨 FormRenderer - Current dataVersion:', this.dataVersion);
      console.log('🎨 FormRenderer - Last dataVersion:', this.lastDataVersion);
      
      // If dataVersion increased, force a data update
      if (this.dataVersion > this.lastDataVersion) {
        console.log('🎨 FormRenderer - DataVersion increased, forcing data refresh');
        this.lastDataVersion = this.dataVersion;
        
        // Log the current data state
        console.log('🎨 FormRenderer - Current data state:', this.data);
        console.log('🎨 FormRenderer - Current employment data:', this.data?.employment);
        
        // Update currentData with the latest data from parent
        this.currentData = { ...this.data };
        console.log('🎨 FormRenderer - Updated currentData:', this.currentData);
        console.log('🎨 FormRenderer - Updated currentData employment:', this.currentData?.employment);
        
        // Force a re-render when dataVersion changes
        this.requestUpdate();
        
        // Force data property update
        this.forceDataUpdate();
        
        // Force another update after a microtask to ensure data is updated
        queueMicrotask(() => {
          console.log('🎨 FormRenderer - Microtask update - Current data:', this.data);
          console.log('🎨 FormRenderer - Microtask update - Employment data:', this.data?.employment);
          this.requestUpdate();
        });
      }
    }
  }

  willUpdate(changedProperties: Map<string, any>) {
    super.willUpdate(changedProperties);
    console.log('🎨 FormRenderer - willUpdate() called');
    console.log('🎨 FormRenderer - Will update properties:', Array.from(changedProperties.keys()));
    
    if (changedProperties.has('data')) {
      console.log('🎨 FormRenderer - Data will be updated');
      console.log('🎨 FormRenderer - New data:', this.data);
      console.log('🎨 FormRenderer - Employment data in willUpdate:', this.data?.employment);
      console.log('🎨 FormRenderer - Employment data length in willUpdate:', this.data?.employment?.length);
    }
    
    if (changedProperties.has('dataVersion')) {
      console.log('🎨 FormRenderer - DataVersion will be updated');
      console.log('🎨 FormRenderer - New dataVersion:', this.dataVersion);
      console.log('🎨 FormRenderer - Current data in willUpdate:', this.data);
      console.log('🎨 FormRenderer - Employment data in willUpdate:', this.data?.employment);
    }
  }

  static styles = css`
    .form-container {
      max-width: 900px;
      margin: 0 auto;
      padding: 2rem;
      background: #f9fafb;
      border-radius: 1rem;
      box-shadow: 0 4px 24px 0 rgba(0,0,0,0.07);
    }
    
    .section {
      background: #fff;
      border: 1px solid #e5e7eb;
      border-radius: 1rem;
      padding: 2rem 1.5rem;
      margin-bottom: 2rem;
      box-shadow: 0 2px 8px 0 rgba(0,0,0,0.03);
    }
    
    .section-title {
      font-size: 1.5rem;
      font-weight: 700;
      color: #222;
      margin-bottom: 1.5rem;
      padding-bottom: 0.5rem;
      border-bottom: 1px solid #e5e7eb;
      letter-spacing: 0.01em;
    }
    
    .fields-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 2rem 2rem;
      margin-bottom: 0.5rem;
    }
    
    .full-width {
      grid-column: 1 / -1;
    }
    
    label {
      display: block;
      font-size: 1rem;
      font-weight: 600;
      color: #222;
      margin-bottom: 0.5rem;
      letter-spacing: 0.01em;
    }
    
    input, select, textarea {
      width: 100%;
      padding: 0.75rem 1rem;
      border: 1px solid #d1d5db;
      border-radius: 0.5rem;
      background: #fff;
      color: #222;
      font-size: 1rem;
      margin-bottom: 0.5rem;
      box-sizing: border-box;
      transition: border-color 0.2s, box-shadow 0.2s;
      box-shadow: 0 1px 2px 0 rgba(0,0,0,0.02);
    }
    
    input:focus, select:focus, textarea:focus {
      border-color: #3b82f6;
      outline: none;
      box-shadow: 0 0 0 2px #3b82f633;
    }
    
    .nested-section {
      background: #f3f4f6;
      border: 1px solid #e5e7eb;
      border-radius: 0.75rem;
      padding: 1.25rem;
      margin-top: 0.5rem;
      box-shadow: 0 1px 4px 0 rgba(0,0,0,0.02);
    }
    
    .nested-title {
      font-size: 1.1rem;
      font-weight: 600;
      color: #374151;
      margin-bottom: 1rem;
      padding-bottom: 0.5rem;
      border-bottom: 1px solid #e5e7eb;
    }
  `;

  private updateField(path: string, value: any) {
    const keys = path.split('.');
    const newData = { ...this.data };
    let current = newData;
    
    for (let i = 0; i < keys.length - 1; i++) {
      if (!current[keys[i]]) {
        current[keys[i]] = {};
      }
      current = current[keys[i]];
    }
    
    current[keys[keys.length - 1]] = value;
    this.onDataChange(newData);
  }

  private updateArrayField(path: string, items: any[]) {
    console.log('🎨 FormRenderer - updateArrayField called');
    console.log('🎨 FormRenderer - Path:', path);
    console.log('🎨 FormRenderer - Items:', items);
    console.log('🎨 FormRenderer - Current data:', this.data);
    console.log('🎨 FormRenderer - CurrentData:', this.currentData);
    
    // Use currentData if available, otherwise fall back to data property
    const sourceData = Object.keys(this.currentData).length > 0 ? this.currentData : this.data;
    
    const keys = path.split('.');
    const newData = { ...sourceData }; // Shallow clone to ensure reference change
    let current = newData;
    
    for (let i = 0; i < keys.length - 1; i++) {
      if (!current[keys[i]]) {
        current[keys[i]] = {};
      }
      current = current[keys[i]];
    }
    
    current[keys[keys.length - 1]] = items;
    console.log('🎨 FormRenderer - Updated data:', newData);
    
    // Ensure onDataChange is a function
    if (typeof this.onDataChange === 'function') {
      this.onDataChange(newData);
      console.log('🎨 FormRenderer - onDataChange called successfully');
    } else {
      console.error('🎨 FormRenderer - onDataChange is not a function:', this.onDataChange);
    }
  }

  render() {
    if (!this.schema.properties) return html`<p>No schema provided</p>`;
    
    // Use currentData if available, otherwise fall back to data property
    const renderData = Object.keys(this.currentData).length > 0 ? this.currentData : this.data;
    
    console.log('🎨 FormRenderer - RENDER METHOD CALLED');
    console.log('🎨 FormRenderer - Data property:', this.data);
    console.log('🎨 FormRenderer - CurrentData:', this.currentData);
    console.log('🎨 FormRenderer - RenderData:', renderData);
    console.log('🎨 FormRenderer - Schema:', this.schema);
    console.log('🎨 FormRenderer - Employment data in render:', renderData?.employment);
    console.log('🎨 FormRenderer - Employment data length in render:', renderData?.employment?.length);
    console.log('🎨 FormRenderer - Data version:', this.dataVersion);
    console.log('🎨 FormRenderer - Render key:', this.getAttribute('key'));
    
    return html`
      <div class="form-container">
        ${Object.entries(this.schema.properties).map(([key, schema]: [string, any]) => {
          const sectionData = renderData[key] || {};
          console.log('🎨 FormRenderer - Rendering section:', key, 'with data:', sectionData);
          if (key === 'employment') {
            console.log('🎨 FormRenderer - EMPLOYMENT SECTION - Data:', sectionData);
            console.log('🎨 FormRenderer - EMPLOYMENT SECTION - Data type:', typeof sectionData);
            console.log('🎨 FormRenderer - EMPLOYMENT SECTION - Is array:', Array.isArray(sectionData));
            console.log('🎨 FormRenderer - EMPLOYMENT SECTION - Length:', Array.isArray(sectionData) ? sectionData.length : 'not array');
          }
          return html`
            <div class="section">
              <h2 class="section-title">${schema.title || key}</h2>
              ${this.renderSection(key, schema, sectionData)}
            </div>
          `;
        })}
      </div>
    `;
  }

  private renderSection(key: string, schema: any, data: any): any {
    if (schema.type === 'array') {
      console.log('🎨 FormRenderer - Rendering array field for:', key);
      console.log('🎨 FormRenderer - Schema title:', schema.title);
      console.log('🎨 FormRenderer - Data for array field:', data);
      console.log('🎨 FormRenderer - Data type:', typeof data);
      console.log('🎨 FormRenderer - Data length:', Array.isArray(data) ? data.length : 'not array');
      console.log('🎨 FormRenderer - Item schema:', schema.items);
      console.log('🎨 FormRenderer - Data JSON length for key:', JSON.stringify(data).length);
      return html`
        <array-field
          .fieldName="${schema.title || key}"
          .items="${data || []}"
          .itemSchema="${schema.items}"
          .onItemsChange="${(items: any[]) => this.updateArrayField(key, items)}"
          data-key="${this.dataVersion}-${key}-${JSON.stringify(data).length}-${Array.isArray(data) ? data.length : 0}"
          key="${this.dataVersion}-${key}-${JSON.stringify(data).length}-${Array.isArray(data) ? data.length : 0}"
        ></array-field>
      `;
    }
    
    if (schema.type === 'object' && schema.properties) {
      return html`
        <div class="fields-grid">
          ${Object.entries(schema.properties).map(([fieldKey, fieldSchema]: [string, any]) => {
            const fieldData = data[fieldKey];
            const isFullWidth = fieldSchema.format === 'textarea';
            
            // Check for conditional rendering logic
            const shouldShow = this.shouldShowField(key, fieldKey, fieldSchema, data);
            
            // If this is a nested object, render it recursively
            if (fieldSchema.type === 'object' && fieldSchema.properties) {
              return html`
                <div class="${isFullWidth ? 'full-width' : ''}">
                  <div class="nested-section">
                    <h3 class="nested-title">${fieldSchema.title || fieldKey}</h3>
                    ${this.renderSection(`${key}.${fieldKey}`, fieldSchema, fieldData || {})}
                  </div>
                </div>
              `;
            }
            
            // Add photo upload field for basicDetails section (ModernTemplate only)
            if (key === 'personalDetails.basicDetails' && fieldKey === 'onlineProfiles') {
              return html`
                ${this.renderPhotoUploadField('personalDetails.basicDetails', data)}
                <div class="${isFullWidth ? 'full-width' : ''}">
                  <div class="nested-section">
                    <h3 class="nested-title">${fieldSchema.title || fieldKey}</h3>
                    ${this.renderSection(`${key}.${fieldKey}`, fieldSchema, fieldData || {})}
                  </div>
                </div>
              `;
            }
            
            // Otherwise render as a regular field (only if shouldShow is true)
            if (!shouldShow) {
              return html``; // Don't render the field
            }
            
            const value = (fieldData === undefined || fieldData === null) ? '' : fieldData;
            const fieldType = this.getFieldType(fieldSchema);
            console.log('🎨 FormRenderer - Rendering field:', fieldKey, 'with type:', fieldType, 'and value:', value);
            return html`
              <div class="${isFullWidth ? 'full-width' : ''}">
                <form-field
                  .fieldName="${fieldKey}"
                  .fieldType="${fieldType}"
                  .value="${value}"
                  .label="${fieldSchema.title || fieldKey}"
                  .placeholder="${fieldSchema.description || ''}"
                  .options="${fieldSchema.enum || []}"
                  .required="${schema.required?.includes(fieldKey) || false}"
                  .onValueChange="${(newValue: any) => {
                    console.log('🎨 FormRenderer - Field value changed:', fieldKey, 'to:', newValue);
                    this.updateField(`${key}.${fieldKey}`, newValue);
                  }}"
                ></form-field>
              </div>
            `;
          })}
        </div>
      `;
    }
    
    return html`
      <div class="fields-grid">
        <form-field
          .fieldName="${key}"
          .fieldType="${this.getFieldType(schema)}"
          .value="${data || ''}"
          .label="${schema.title || key}"
          .placeholder="${schema.description || ''}"
          .options="${schema.enum || []}"
          .required="${schema.required?.includes(key) || false}"
          .onValueChange="${(newValue: any) => this.updateField(key, newValue)}"
        ></form-field>
      </div>
    `;
  }

  private getFieldType(schema: any): string {
    // Special case for year-only fields
    if (schema.format === 'date' && schema.pattern === '^(\\d{4})$') return 'year';
    if (schema.format === 'date') return 'date';
    if (schema.format === 'textarea') return 'textarea';
    if (schema.format === 'photo') return 'photo';
    if (schema.enum) return 'select';
    if (schema.type === 'boolean') return 'checkbox';
    return 'text';
  }

  private shouldShowField(sectionKey: string, fieldKey: string, fieldSchema: any, data: any): boolean {
    // Handle differently abled conditional fields
    if (sectionKey === 'personalDetails.moreDetails') {
      // Check if this is a disability-related field that should be conditionally shown
      if (fieldKey === 'disabilityType' || fieldKey === 'disabilityAssistance') {
        // Only show these fields if differentlyAbled checkbox is checked
        return data.differentlyAbled === true;
      }
    }
    
    // Handle career break conditional fields
    if (sectionKey === 'personalDetails.moreDetails') {
      // Check if this is a career break-related field that should be conditionally shown
      if (fieldKey === 'reasonOfBreak' || fieldKey === 'breakStartedFrom' || fieldKey === 'breakEndedIn') {
        // Only show these fields if careerBreak checkbox is checked
        return data.careerBreak === true;
      }
    }
    
    // Handle "Currently Doing" date field logic
    if (sectionKey === 'personalDetails.moreDetails' && fieldKey === 'breakEndedIn') {
      // Hide break ended in field if currently on break
      return data.isBreakOngoing !== true;
    }
    
    if (sectionKey === 'employment' && fieldKey === 'leavingDate') {
      // Hide leaving date field if currently working
      return data.currentlyWorking !== true;
    }
    
    if (sectionKey === 'certifications' && fieldKey === 'validityTo') {
      // Hide validity to field if currently valid
      return data.isValidOngoing !== true;
    }
    
    // Handle "Currently Doing" date field logic for education
    if (sectionKey === 'education' && fieldKey === 'toDate') {
      // Hide to date field if currently studying
      return data.isCurrentlyStudying !== true;
    }
    
    // By default, show all fields
    return true;
  }

  private renderPhotoUploadField(key: string, data: any): any {
    // Only show photo upload for ModernTemplate
    // This will be handled by the template selection logic
    return html`
      <div class="full-width">
        <photo-upload-field
          .value="${data.photoUrl || ''}"
          .label="Profile Photo"
          .placeholder="Upload a profile photo"
          .onValueChange="${(value: string) => {
            console.log('📸 FormRenderer - Photo value changed to:', value);
            this.updateField(`${key}.photoUrl`, value);
          }}"
        ></photo-upload-field>
      </div>
    `;
  }

  // Method to force update data property
  private forceDataUpdate() {
    console.log('🎨 FormRenderer - Force data update called');
    console.log('🎨 FormRenderer - Current data employment:', this.data?.employment);
    
    // Force a re-render
    this.requestUpdate();
  }
} 