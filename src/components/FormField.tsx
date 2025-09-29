import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';

@customElement('form-field')
export class FormField extends LitElement {
  @property({ type: String }) fieldName = '';
  @property({ type: String }) fieldType = 'text';
  @property({ type: String }) value: any = '';
  @property({ type: String }) label = '';
  @property({ type: String }) placeholder = '';
  @property({ type: Array }) options: string[] = [];
  @property({ type: Boolean }) required = false;
  @property({ type: Function }) onValueChange = (value: any) => {};

  static styles = css`
    .field-container {
      margin-bottom: 1rem;
    }
    
    .field-label {
      display: block;
      margin-bottom: 0.5rem;
      font-weight: 700;
      color: #222;
    }
    
    .field-input {
      width: 100%;
      padding: 0.75rem;
      border: 1px solid #374151;
      border-radius: 0.375rem;
      background: #1f2937;
      color: #f9fafb;
      font-size: 0.875rem;
    }
    
    .field-input:focus {
      outline: none;
      border-color: #3b82f6;
      box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
    }
    
    .field-textarea {
      min-height: 100px;
      resize: vertical;
    }
    
    .field-select {
      cursor: pointer;
    }
    
    .field-checkbox {
      width: auto;
      margin-right: 0.5rem;
    }
    
    .checkbox-container {
      display: flex;
      align-items: center;
    }
    
    .error-message {
      color: #ef4444;
      font-size: 0.75rem;
      margin-top: 0.25rem;
    }
    input[type='date']::-webkit-calendar-picker-indicator {
      filter: invert(0.6) grayscale(1);
      opacity: 0.8;
    }
    input[type='date']::-moz-calendar-picker-indicator {
      filter: invert(0.6) grayscale(1);
      opacity: 0.8;
    }
    input[type='date']::-ms-input-placeholder {
      color: #888;
    }
    input[type='date']::placeholder {
      color: #888;
    }
  `;

  private handleInputChange(e: Event) {
    const target = e.target as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement;
    let value: any = target.value;
    
    if (this.fieldType === 'checkbox') {
      value = (target as HTMLInputElement).checked;
    }
    
    this.onValueChange(value);
  }

  render() {
    const inputId = `field-${this.fieldName}`;
    
    switch (this.fieldType) {
      case 'textarea':
        return html`
          <div class="field-container">
            <label for="${inputId}" class="field-label">
              ${this.label}${this.required ? ' *' : ''}
            </label>
            <textarea
              id="${inputId}"
              class="field-input field-textarea"
              .value="${this.value}"
              placeholder="${this.placeholder}"
              @input="${this.handleInputChange}"
            ></textarea>
          </div>
        `;
        
      case 'select':
        return html`
          <div class="field-container">
            <label for="${inputId}" class="field-label">
              ${this.label}${this.required ? ' *' : ''}
            </label>
            <select
              id="${inputId}"
              class="field-input field-select"
              .value="${this.value}"
              @change="${this.handleInputChange}"
            >
              <option value="">Select ${this.label}</option>
              ${this.options.map(option => html`
                <option value="${option}" ?selected="${this.value === option}">
                  ${option}
                </option>
              `)}
            </select>
          </div>
        `;
        
      case 'checkbox':
        return html`
          <div class="field-container">
            <div class="checkbox-container">
              <input
                id="${inputId}"
                type="checkbox"
                class="field-input field-checkbox"
                .checked="${this.value === true}"
                @change="${this.handleInputChange}"
              />
              <label for="${inputId}" class="field-label">
                ${this.label}
              </label>
            </div>
          </div>
        `;
        
      case 'date':
        return html`
          <div class="field-container">
            <label for="${inputId}" class="field-label">
              ${this.label}${this.required ? ' *' : ''}
            </label>
            <input
              id="${inputId}"
              type="date"
              class="field-input"
              .value="${this.value}"
              @input="${this.handleInputChange}"
            />
          </div>
        `;
        
      case 'year':
        return html`
          <div class="field-container">
            <label for="${inputId}" class="field-label">
              ${this.label}${this.required ? ' *' : ''}
            </label>
            <input
              id="${inputId}"
              type="number"
              class="field-input"
              .value="${this.value}"
              min="1900"
              max="2100"
              placeholder="YYYY"
              @input="${this.handleInputChange}"
            />
          </div>
        `;
        
      case 'photo':
        console.log('📸 FormField - Rendering photo field with value:', this.value);
        return html`
          <div class="field-container">
            <photo-upload-field
              .value="${this.value}"
              .label="${this.label}"
              .placeholder="${this.placeholder}"
              .onValueChange="${(value: string) => {
                console.log('📸 FormField - Photo value changed to:', value);
                this.onValueChange(value);
              }}"
            ></photo-upload-field>
          </div>
        `;
        
      default:
        return html`
          <div class="field-container">
            <label for="${inputId}" class="field-label">
              ${this.label}${this.required ? ' *' : ''}
            </label>
            <input
              id="${inputId}"
              type="text"
              class="field-input"
              .value="${this.value}"
              placeholder="${this.placeholder}"
              @input="${this.handleInputChange}"
            />
          </div>
        `;
    }
  }
} 