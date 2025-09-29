import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { map } from 'lit/directives/map.js';

@customElement('array-field')
export class ArrayField extends LitElement {
  @property({ type: String }) fieldName = '';
  @property({ type: Object }) items: any[] = [];
  @property({ type: Object }) itemSchema: any = {};
  @property({ type: Function }) onItemsChange = (items: any[]) => {};

  updated(changedProperties: Map<string, any>) {
    super.updated(changedProperties);
    console.log('🔧 ArrayField - updated() called');
    console.log('🔧 ArrayField - Changed properties:', Array.from(changedProperties.keys()));
    
    if (changedProperties.has('items')) {
      console.log('🔧 ArrayField - Items property changed');
      console.log('🔧 ArrayField - Old items:', changedProperties.get('items'));
      console.log('🔧 ArrayField - New items:', this.items);
      console.log('🔧 ArrayField - New items length:', this.items?.length);
      console.log('🔧 ArrayField - Forcing re-render');
      this.requestUpdate();
    }
  }

  willUpdate(changedProperties: Map<string, any>) {
    super.willUpdate(changedProperties);
    console.log('🔧 ArrayField - willUpdate() called');
    console.log('🔧 ArrayField - Will update properties:', Array.from(changedProperties.keys()));
    
    if (changedProperties.has('items')) {
      console.log('🔧 ArrayField - Items will be updated');
      console.log('🔧 ArrayField - New items:', this.items);
      console.log('🔧 ArrayField - New items length:', this.items?.length);
    }
  }

  static styles = css`
    .array-container {
      margin-bottom: 2rem;
    }
    
    .array-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1rem;
      padding-bottom: 0.5rem;
      border-bottom: 1px solid #e5e7eb;
    }
    
    .array-title {
      font-size: 1.125rem;
      font-weight: 600;
      color: #222;
    }
    
    .item-container {
      background: #f9fafb;
      border: 1px solid #e5e7eb;
      border-radius: 0.75rem;
      padding: 1.5rem;
      margin-bottom: 1rem;
      position: relative;
      box-shadow: 0 1px 4px 0 rgba(0,0,0,0.02);
    }
    
    .item-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1rem;
    }
    
    .item-title {
      font-weight: 600;
      color: #374151;
      font-size: 1rem;
    }
    
    .item-fields {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
      gap: 1rem;
    }
    
    .remove-button {
      background: #ef4444;
      color: white;
      border: none;
      border-radius: 0.375rem;
      padding: 0.5rem 1rem;
      font-size: 0.875rem;
      font-weight: 500;
      cursor: pointer;
      transition: background-color 0.2s;
    }
    
    .remove-button:hover {
      background: #dc2626;
    }
    
    .add-button {
      background: #3b82f6;
      color: white;
      border: none;
      border-radius: 0.375rem;
      padding: 0.75rem 1.5rem;
      font-size: 0.875rem;
      font-weight: 500;
      cursor: pointer;
      margin-top: 1rem;
      transition: background-color 0.2s;
    }
    
    .add-button:hover {
      background: #2563eb;
    }
  `;

  private updateItem(index: number, fieldName: string, value: any) {
    const safeItems = this.getSafeItems();
    const newItems = [...safeItems];
    
    // Handle string arrays (like achievements, publications, hobbies, trainings)
    if (this.itemSchema.type === 'string') {
      newItems[index] = value;
    } else {
      // Handle object arrays (like employment, education, etc.)
      newItems[index] = { ...newItems[index], [fieldName]: value };
    }
    
    this.onItemsChange(newItems);
  }

  render() {
    const safeItems = this.getSafeItems();
    console.log('🔧 ArrayField - Render called');
    console.log('🔧 ArrayField - Field name:', this.fieldName);
    console.log('🔧 ArrayField - Items prop:', this.items);
    console.log('🔧 ArrayField - Items prop type:', typeof this.items);
    console.log('🔧 ArrayField - Items prop is array:', Array.isArray(this.items));
    console.log('🔧 ArrayField - Safe items:', safeItems);
    console.log('🔧 ArrayField - Safe items length:', safeItems.length);
    console.log('🔧 ArrayField - Item schema:', this.itemSchema);
    console.log('🔧 ArrayField - Render key:', this.getAttribute('key'));
    
    // For key array sections, ensure first item is always present and visible
    const isAlwaysVisibleSection = this.isAlwaysVisibleSection();
    
    let itemsToRender = safeItems;
    
    // If this is an always-visible section and no items exist, create a default first item
    if (isAlwaysVisibleSection && safeItems.length === 0) {
      const defaultItem = this.createDefaultItem();
      itemsToRender = [defaultItem];
      // Update parent with the default item
      this.onItemsChange([defaultItem]);
    }
    
    return html`
      <div class="array-container">
        ${map(itemsToRender, (item, index) => html`
          <div class="item-container" data-key="${index}-${itemsToRender.length}-${JSON.stringify(item).length}">
            <div class="item-header">
              <span class="item-title">${this.fieldName} ${index + 1}</span>
              ${!isAlwaysVisibleSection || index > 0 ? html`
                <button 
                  class="remove-button"
                  @click="${() => this.removeItem(index)}"
                  type="button"
                >
                  Remove
                </button>
              ` : html``}
            </div>
            
            <div class="item-fields">
              ${this.renderItemFields(item, index)}
            </div>
          </div>
        `)}
        
        ${isAlwaysVisibleSection && itemsToRender.length > 0 ? html`
          <button 
            class="add-button"
            @click="${this.addItem}"
            type="button"
          >
            Add Another ${this.fieldName}
          </button>
        ` : html``}
      </div>
    `;
  }

  private renderItemFields(item: any, index: number) {
    console.log('🔧 ArrayField - renderItemFields called for item:', item, 'index:', index);
    console.log('🔧 ArrayField - Item schema properties:', this.itemSchema.properties);
    console.log('🔧 ArrayField - Item schema type:', this.itemSchema.type);
    console.log('🔧 ArrayField - Item keys:', Object.keys(item || {}));
    console.log('🔧 ArrayField - Item values:', Object.values(item || {}));
    
    // Handle string arrays (like achievements, publications, hobbies, trainings)
    if (this.itemSchema.type === 'string') {
      console.log('🔧 ArrayField - Rendering string array item');
      return html`
        <form-field
          .fieldName="value"
          .fieldType="text"
          .value="${item || ''}"
          .label="${this.itemSchema.title || ''}"
          .placeholder="${this.itemSchema.description || 'Enter value'}"
          .onValueChange="${(newValue: any) => this.updateItem(index, 'value', newValue)}"
        ></form-field>
      `;
    }
    
    // Handle object arrays (like employment, education, etc.)
    if (!this.itemSchema.properties) {
      console.log('🔧 ArrayField - No item schema properties found');
      return html``;
    }
    
    const fields = Object.entries(this.itemSchema.properties).map(([key, schema]: [string, any]) => {
      const value = item[key] || '';
      console.log('🔧 ArrayField - Rendering field:', key, 'with value:', value);
      return html`
        <form-field
          .fieldName="${key}"
          .fieldType="${this.getFieldType(schema)}"
          .value="${value}"
          .label="${schema.title || key}"
          .placeholder="${schema.description || ''}"
          .options="${schema.enum || []}"
          .required="${this.itemSchema.required?.includes(key) || false}"
          .onValueChange="${(newValue: any) => this.updateItem(index, key, newValue)}"
        ></form-field>
      `;
    });
    
    console.log('🔧 ArrayField - Fields to render:', fields);
    return fields;
  }

  private getFieldType(schema: any): string {
    console.log('🔧 ArrayField - getFieldType called with schema:', schema);
    
    if (schema.format === 'date') {
      console.log('🔧 ArrayField - Field type: date');
      return 'date';
    }
    if (schema.format === 'textarea') {
      console.log('🔧 ArrayField - Field type: textarea');
      return 'textarea';
    }
    if (schema.enum) {
      console.log('🔧 ArrayField - Field type: select');
      return 'select';
    }
    if (schema.type === 'boolean') {
      console.log('🔧 ArrayField - Field type: checkbox');
      return 'checkbox';
    }
    console.log('🔧 ArrayField - Field type: text (default)');
    return 'text';
  }

  private getSafeItems(): any[] {
    console.log('🔧 ArrayField - getSafeItems called');
    console.log('🔧 ArrayField - this.items:', this.items);
    console.log('🔧 ArrayField - this.items type:', typeof this.items);
    console.log('🔧 ArrayField - this.items is array:', Array.isArray(this.items));
    
    if (Array.isArray(this.items)) {
      console.log('🔧 ArrayField - Returning items array:', this.items);
      return this.items;
    }
    
    console.log('🔧 ArrayField - Items is not an array, returning empty array');
    return [];
  }

  private isAlwaysVisibleSection(): boolean {
    const fieldName = this.fieldName.toLowerCase();
    return fieldName.includes('work') || 
           fieldName.includes('experience') ||
           fieldName.includes('employment') ||
           fieldName.includes('education') ||
           fieldName.includes('project') ||
           fieldName.includes('certification') ||
           fieldName.includes('language') ||
           fieldName.includes('reference') ||
           fieldName.includes('achievement') ||
           fieldName.includes('publication') ||
           fieldName.includes('training') ||
           fieldName.includes('hobbies');
  }

  private createDefaultItem(): any {
    if (this.itemSchema.type === 'string') {
      return '';
    }
    
    // Create a default object with empty values for all properties
    const defaultItem: any = {};
    if (this.itemSchema.properties) {
      Object.keys(this.itemSchema.properties).forEach(key => {
        const fieldSchema = this.itemSchema.properties[key];
        if (fieldSchema.type === 'boolean') {
          defaultItem[key] = false;
        } else if (fieldSchema.type === 'array') {
          defaultItem[key] = [];
        } else {
          defaultItem[key] = '';
        }
      });
    }
    
    return defaultItem;
  }

  private removeItem(index: number) {
    const safeItems = this.getSafeItems();
    const newItems = safeItems.filter((_, i) => i !== index);
    this.onItemsChange(newItems);
  }

  private addItem = () => {
    console.log('🔧 ArrayField - addItem clicked for:', this.fieldName);
    const safeItems = this.getSafeItems();
    console.log('🔧 ArrayField - Current safe items:', safeItems);
    const newItem = this.createDefaultItem();
    console.log('🔧 ArrayField - New item created:', newItem);
    const newItems = [...safeItems, newItem];
    console.log('🔧 ArrayField - New items array:', newItems);
    this.onItemsChange(newItems);
  }
} 