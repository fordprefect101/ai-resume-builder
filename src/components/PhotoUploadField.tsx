import { LitElement, css, html } from 'lit';
import { customElement, property } from 'lit/decorators.js';

@customElement('photo-upload-field')
export class PhotoUploadField extends LitElement {
  @property({ type: String }) value = '';
  @property({ type: Function }) onValueChange = (value: string) => {};
  @property({ type: String }) label = 'Profile Photo';
  @property({ type: String }) placeholder = 'Upload a profile photo';

  @property({ type: Boolean }) private showUpload = true;
  @property({ type: String }) private uploadStatus = '';
  @property({ type: Boolean }) private isUploading = false;

  static styles = css`
    :host {
      display: block;
    }

    .field-container {
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }

    .input-group {
      display: flex;
      gap: 0.5rem;
      align-items: flex-end;
    }



    .upload-button {
      padding: 0.75rem 1.5rem;
      background: #3b82f6;
      color: white;
      border: none;
      border-radius: 0.375rem;
      font-size: 0.875rem;
      font-weight: 500;
      cursor: pointer;
      transition: background 0.2s;
      white-space: nowrap;
    }

    .upload-button:hover {
      background: #2563eb;
    }

    .upload-button:disabled {
      background: #9ca3af;
      cursor: not-allowed;
    }

    .file-input {
      display: none;
    }

    .preview-container {
      display: flex;
      align-items: center;
      gap: 1rem;
      padding: 1rem;
      background: #f9fafb;
      border-radius: 0.5rem;
      border: 1px solid #e5e7eb;
    }

    .preview-image {
      width: 80px;
      height: 80px;
      border-radius: 50%;
      object-fit: cover;
      border: 2px solid #e5e7eb;
    }

    .preview-info {
      flex: 1;
    }

    .preview-name {
      font-weight: 500;
      color: #1f2937;
      margin-bottom: 0.25rem;
    }

    .preview-size {
      font-size: 0.75rem;
      color: #6b7280;
    }

    .remove-button {
      padding: 0.5rem;
      background: #ef4444;
      color: white;
      border: none;
      border-radius: 0.25rem;
      cursor: pointer;
      font-size: 0.75rem;
    }

    .remove-button:hover {
      background: #dc2626;
    }

    .preview-actions {
      display: flex;
      gap: 0.5rem;
    }

    .edit-button {
      padding: 0.5rem;
      background: #3b82f6;
      color: white;
      border: none;
      border-radius: 0.25rem;
      cursor: pointer;
      font-size: 0.75rem;
    }

    .edit-button:hover {
      background: #2563eb;
    }

    .status-message {
      font-size: 0.875rem;
      margin-top: 0.5rem;
    }

    .status-success {
      color: #059669;
    }

    .status-error {
      color: #dc2626;
    }

    .status-info {
      color: #3b82f6;
    }


  `;

  private handleFileSelect(e: Event) {
    const target = e.target as HTMLInputElement;
    const file = target.files?.[0];
    
    if (file) {
      this.uploadFile(file);
    }
  }

  private async uploadFile(file: File) {
    this.isUploading = true;
    this.uploadStatus = 'Uploading...';

    try {
      // Check file type - only allow specific formats
      const allowedTypes = ['image/png', 'image/gif', 'image/jpeg', 'image/jpg', 'image/tiff'];
      if (!allowedTypes.includes(file.type.toLowerCase())) {
        throw new Error('Please select a valid image file (PNG, GIF, JPEG, JPG, TIFF)');
      }

      // Check file size (max 5MB)
      if (file.size > 5 * 1024 * 1024) {
        throw new Error('File size must be less than 5MB');
      }

      // Convert to base64 for preview and storage
      const base64 = await this.fileToBase64(file);
      this.value = base64;
      console.log('📸 PhotoUploadField - File uploaded, base64 length:', base64.length);
      this.onValueChange(this.value);
      this.uploadStatus = 'File uploaded successfully!';
      
      // Clear the file input
      const fileInput = this.shadowRoot?.querySelector('.file-input') as HTMLInputElement;
      if (fileInput) {
        fileInput.value = '';
      }

    } catch (error: any) {
      this.uploadStatus = error.message || 'Upload failed';
    } finally {
      this.isUploading = false;
    }
  }

  private fileToBase64(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onload = () => resolve(reader.result as string);
      reader.onerror = error => reject(error);
    });
  }

  private removePhoto() {
    this.value = '';
    this.onValueChange('');
    this.uploadStatus = '';
  }

  private getFileSize(bytes: number): string {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  render() {
    const isBase64 = this.value && this.value.startsWith('data:image');

    return html`
      <div class="field-container">
        <label>${this.label}</label>
        
        <div class="input-group">
          <input
            type="file"
            class="file-input"
            accept=".png,.gif,.jpeg,.jpg,.tiff"
            @change="${this.handleFileSelect}"
          />
          <button 
            class="upload-button"
            @click="${() => (this.shadowRoot?.querySelector('.file-input') as HTMLInputElement)?.click()}"
            ?disabled="${this.isUploading}"
          >
            ${this.isUploading ? 'Uploading...' : 'Choose File'}
          </button>
        </div>

        ${isBase64 ? html`
          <div class="preview-container">
            <img 
              src="${this.value}" 
              alt="Profile preview" 
              class="preview-image"
              @error="${() => this.removePhoto()}"
            />
            <div class="preview-info">
              <div class="preview-name">
                Uploaded Image
              </div>
              <div class="preview-size">
                ${this.getFileSize(this.value.length * 0.75)} (estimated)
              </div>
            </div>
            <div class="preview-actions">
              <button class="edit-button" @click="${() => (this.shadowRoot?.querySelector('.file-input') as HTMLInputElement)?.click()}">
                Edit
              </button>
              <button class="remove-button" @click="${this.removePhoto}">
                Remove
              </button>
            </div>
          </div>
        ` : ''}

        ${this.uploadStatus ? html`
          <div class="status-message ${this.uploadStatus.includes('success') ? 'status-success' : this.uploadStatus.includes('failed') || this.uploadStatus.includes('Error') ? 'status-error' : 'status-info'}">
            ${this.uploadStatus}
          </div>
        ` : ''}
      </div>
    `;
  }
} 