import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';

@customElement('modern-template')
export class ModernTemplate extends LitElement {
  @property({ type: Object }) resumeData: any = {};
  @property({ type: String }) themeColor: string = '#3b82f6';

  static styles = css`
    :host {
      display: block;
      font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    }

    .print-container {
      background: #f1f5f9;
      display: flex;
      justify-content: center;
      padding: 2rem 0;
    }

    .print-page {
      width: 210mm;
      min-height: 297mm;
      background: white;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
      display: flex;
      font-family: sans-serif;
    }

    /* Sidebar Styles */
    .sidebar {
      width: 33.333333%;
      color: white;
      padding: 1.5rem;
      break-after: avoid;
    }

    .profile-photo {
      margin-bottom: 1.5rem;
      display: flex;
      justify-content: center;
    }

    .profile-photo img {
      width: 8rem;
      height: 8rem;
      border-radius: 9999px;
      object-fit: cover;
      border: 4px solid rgba(255, 255, 255, 0.5);
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }

    .sidebar-section {
      margin-bottom: 1.5rem;
      break-inside: avoid;
    }

    .sidebar-section h3 {
      font-size: 0.875rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: rgba(255, 255, 255, 0.9);
      margin-bottom: 0.5rem;
    }

    .contact-info {
      font-size: 0.875rem;
    }

    .contact-item {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      margin-bottom: 0.5rem;
    }

    .contact-item a {
      color: white;
      text-decoration: none;
    }

    .contact-item a:hover {
      text-decoration: underline;
    }

    .skill-pill {
      display: inline-block;
      background: rgba(255, 255, 255, 0.2);
      border-radius: 0.375rem;
      padding: 0.25rem 0.5rem;
      font-size: 0.75rem;
      font-weight: 500;
      margin: 0.125rem;
    }

    .skills-container {
      display: flex;
      flex-wrap: wrap;
      gap: 0.375rem;
    }

    .language-item {
      font-size: 0.875rem;
      margin-bottom: 0.25rem;
    }

    .language-proficiency {
      color: rgba(255, 255, 255, 0.7);
    }

    /* Main Content Styles */
    .main-content {
      width: 66.666667%;
      padding: 2rem;
      color: #374151;
    }

    .header {
      margin-bottom: 2rem;
      text-align: left;
    }

    .header h1 {
      font-size: 3rem;
      font-weight: 800;
      letter-spacing: -0.025em;
      color: #111827;
      margin: 0;
    }

    .header p {
      font-size: 1.25rem;
      font-weight: 500;
      margin: 0.25rem 0 0 0;
    }

    .main-section {
      margin-bottom: 1.5rem;
      break-inside: avoid;
    }

    .main-section h2 {
      font-size: 1.25rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 0.5rem;
    }

    .experience-entry {
      margin-bottom: 1rem;
      break-inside: avoid;
    }

    .experience-header {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
    }

    .experience-title {
      font-size: 1rem;
      font-weight: 700;
      color: #1f2937;
      margin: 0;
    }

    .experience-date {
      font-size: 0.75rem;
      font-weight: 500;
      color: #6b7280;
      text-align: right;
      white-space: nowrap;
    }

    .experience-company {
      font-size: 0.875rem;
      font-weight: 600;
      color: #4b5563;
      margin: 0.25rem 0 0.25rem 0;
    }

    .experience-description {
      font-size: 0.875rem;
      color: #374151;
    }

    .experience-description ul {
      list-style: disc;
      list-style-position: outside;
      padding-left: 1.25rem;
      margin: 0.25rem 0 0 0;
    }

    .experience-description li {
      margin-bottom: 0.25rem;
    }

    .education-entry {
      margin-bottom: 0.75rem;
      break-inside: avoid;
    }

    .education-header {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
    }

    .education-degree {
      font-size: 1rem;
      font-weight: 700;
      color: #1f2937;
      margin: 0;
    }

    .education-date {
      font-size: 0.75rem;
      font-weight: 500;
      color: #6b7280;
      text-align: right;
      white-space: nowrap;
    }

    .education-institute {
      font-size: 0.875rem;
      font-weight: 600;
      color: #4b5563;
      margin: 0;
    }

    .education-course {
      font-size: 0.875rem;
      font-style: italic;
      color: #6b7280;
      margin: 0;
    }

    .project-entry {
      margin-bottom: 1rem;
      break-inside: avoid;
    }

    .project-title {
      font-size: 1rem;
      font-weight: 700;
      color: #1f2937;
      margin: 0 0 0.25rem 0;
    }

    .project-description {
      font-size: 0.875rem;
      color: #374151;
    }

    .project-description ul {
      list-style: disc;
      list-style-position: outside;
      padding-left: 1.25rem;
      margin: 0.25rem 0 0 0;
    }

    .project-description li {
      margin-bottom: 0.25rem;
    }

    .achievements-list {
      list-style: disc;
      list-style-position: outside;
      padding-left: 1.25rem;
      font-size: 0.875rem;
      color: #374151;
    }

    .achievements-list li {
      margin-bottom: 0.25rem;
    }

    .reference-entry {
      margin-bottom: 1.5rem;
      padding: 1rem;
      background: #f9fafb;
      border-radius: 0.5rem;
      border-left: 4px solid var(--theme-color, #3b82f6);
    }

    .reference-name {
      font-size: 1.1rem;
      font-weight: 600;
      margin: 0 0 0.25rem 0;
      color: #1f2937;
    }

    .reference-relationship {
      font-size: 0.9rem;
      color: #6b7280;
      margin: 0 0 0.25rem 0;
      font-style: italic;
    }

    .reference-contact {
      font-size: 0.9rem;
      color: #374151;
      margin: 0;
    }

    /* Print styles */
    @media print {
      .print-container {
        background: white;
        padding: 0;
      }
      
      .print-page {
        box-shadow: none;
        width: 100%;
        min-height: auto;
      }
    }
  `;

  // Utility functions
  private hasContent(data: any): boolean {
    if (!data) return false;
    if (typeof data === 'boolean') return data;
    if (Array.isArray(data)) return data.length > 0 && data.some(item => this.hasContent(item));
    if (typeof data === 'object') return Object.values(data).some(val => this.hasContent(val));
    return !!data;
  }

  private formatDate(dateStr?: string): string {
    if (!dateStr || dateStr.toLowerCase() === 'present') return 'Present';
    if (isNaN(new Date(dateStr).getTime())) return dateStr;
    const date = new Date(dateStr);
    const utcDate = new Date(date.valueOf() + date.getTimezoneOffset() * 60 * 1000);
    return new Intl.DateTimeFormat('en-US', { month: 'short', year: 'numeric' }).format(utcDate);
  }

  private formatDateWithCheckbox(dateStr?: string, isOngoing?: boolean): string {
    if (isOngoing === true) return 'Present';
    return this.formatDate(dateStr);
  }

  private toBulletPoints(text?: string): string[] {
    if (!text) return [];
    return text.split('\n').map(line => line.trim().replace(/^-|^\*|^\•/,'').trim()).filter(line => line);
  }

  // Icon components
  private renderIconMail() {
    return html`<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg>`;
  }

  private renderIconPhone() {
    return html`<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"></path></svg>`;
  }

  private renderIconLinkedIn() {
    return html`<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"></path><rect x="2" y="9" width="4" height="12"></rect><circle cx="4" cy="4" r="2"></circle></svg>`;
  }

  private renderIconGitHub() {
    return html`<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"></path></svg>`;
  }

  private renderIconAddress() {
    return html`<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>`;
  }

  render() {
    const { personalDetails, careerDetails, employment, education, projects, languages, achievements, publications, hobbies, trainings, references } = this.resumeData;
    const { basicDetails, moreDetails } = personalDetails || {};
    const onlineProfiles = basicDetails?.onlineProfiles || {};
    
    // Debug photo data
    console.log('📸 ModernTemplate - Photo debugging:');
    console.log('📸 ModernTemplate - personalDetails:', personalDetails);
    console.log('📸 ModernTemplate - basicDetails:', basicDetails);
    console.log('📸 ModernTemplate - photoUrl:', basicDetails?.photoUrl);
    console.log('📸 ModernTemplate - photoUrl type:', typeof basicDetails?.photoUrl);
    console.log('📸 ModernTemplate - photoUrl length:', basicDetails?.photoUrl?.length);

    return html`
      <div class="print-container">
        <div class="print-page">
          <!-- Sidebar -->
          <aside class="sidebar" style="background-color: ${this.themeColor}">
            ${basicDetails?.photoUrl && basicDetails.photoUrl.trim() ? html`
              <div class="profile-photo">
                <img 
                  src="${basicDetails.photoUrl}" 
                  alt="Profile" 
                  @error="${(e: Event) => {
                    console.log('📸 ModernTemplate - Image failed to load:', basicDetails.photoUrl);
                    const target = e.target as HTMLImageElement;
                    target.style.display = 'none';
                  }}"
                  @load="${() => console.log('📸 ModernTemplate - Image loaded successfully')}"
                />
              </div>
            ` : ''}

            <!-- Contact Section -->
            <div class="sidebar-section">
              <h3>Contact</h3>
              <div class="contact-info">
                ${basicDetails?.email ? html`
                  <div class="contact-item">
                    ${this.renderIconMail()}
                    <a href="mailto:${basicDetails.email}">${basicDetails.email}</a>
                  </div>
                ` : ''}
                ${basicDetails?.mobile ? html`
                  <div class="contact-item">
                    ${this.renderIconPhone()}
                    <span>${basicDetails.mobile}</span>
                  </div>
                ` : ''}
                ${basicDetails?.address ? html`
                  <div class="contact-item">
                    ${this.renderIconAddress()}
                    <span>${basicDetails.address}</span>
                  </div>
                ` : ''}
              </div>
            </div>

            <!-- Links Section -->
            ${this.hasContent(onlineProfiles) ? html`
              <div class="sidebar-section">
                <h3>Links</h3>
                <div class="contact-info">
                  ${onlineProfiles?.linkedIn ? html`
                    <div class="contact-item">
                      ${this.renderIconLinkedIn()}
                      <a href="${onlineProfiles.linkedIn}" target="_blank" rel="noopener noreferrer">LinkedIn</a>
                    </div>
                  ` : ''}
                  ${onlineProfiles?.gitHub ? html`
                    <div class="contact-item">
                      ${this.renderIconGitHub()}
                      <a href="${onlineProfiles.gitHub}" target="_blank" rel="noopener noreferrer">GitHub</a>
                    </div>
                  ` : ''}
                </div>
              </div>
            ` : ''}

            <!-- Skills Section -->
            ${this.hasContent(careerDetails?.keySkills) && Array.isArray(careerDetails?.keySkills) ? html`
              <div class="sidebar-section">
                <h3>Skills</h3>
                <div class="skills-container">
                  ${careerDetails.keySkills.map((skill: string) => html`
                    <span class="skill-pill">${skill}</span>
                  `)}
                </div>
              </div>
            ` : ''}

            <!-- Languages Section -->
            ${this.hasContent(languages) ? html`
              <div class="sidebar-section">
                <h3>Languages</h3>
                <div class="contact-info">
                  ${languages.map((lang: any) => html`
                    <div class="language-item">
                      ${lang.language}
                    </div>
                  `)}
                </div>
              </div>
            ` : ''}
          </aside>

          <!-- Main Content -->
          <main class="main-content">
            <!-- Header -->
            <header class="header">
              <h1>${basicDetails?.name || 'Your Name'}</h1>
              <p style="color: ${this.themeColor}">${moreDetails?.resumeHeadline || 'Professional Headline'}</p>
            </header>

            <!-- Experience Section -->
            ${this.hasContent(employment) ? html`
              <section class="main-section">
                <h2 style="color: ${this.themeColor}">Experience</h2>
                ${employment.map((item: any) => html`
                  <div class="experience-entry">
                    <div class="experience-header">
                      <h3 class="experience-title">${item.jobTitle || '[Job Title]'}</h3>
                      <div class="experience-date">
                        <span>${this.formatDate(item.joiningDate)} &ndash; ${this.formatDateWithCheckbox(item.leavingDate, item.currentlyWorking)}</span>
                      </div>
                    </div>
                    <p class="experience-company">${item.companyName || '[Company Name]'}</p>
                    <div class="experience-description">
                      <ul>
                        ${this.toBulletPoints(item.jobProfile).map((point: string) => html`
                          <li>${point}</li>
                        `)}
                      </ul>
                    </div>
                  </div>
                `)}
              </section>
            ` : ''}

            <!-- Education Section -->
            ${this.hasContent(education) ? html`
              <section class="main-section">
                <h2 style="color: ${this.themeColor}">Education</h2>
                ${education.map((item: any) => html`
                  <div class="education-entry">
                    <div class="education-header">
                      <h3 class="education-degree">${item.degree || '[Degree]'}</h3>
                                          <div class="education-date">
                      <span>${this.formatDate(item.fromDate)} &ndash; ${this.formatDateWithCheckbox(item.toDate, item.isCurrentlyStudying)}</span>
                    </div>
                    </div>
                    <p class="education-institute">${item.institute || '[Institute]'}</p>
                    <p class="education-course">${item.course || '[Course]'}</p>
                  </div>
                `)}
              </section>
            ` : ''}

            <!-- Projects Section -->
            ${this.hasContent(projects) ? html`
              <section class="main-section">
                <h2 style="color: ${this.themeColor}">Projects</h2>
                ${projects.map((item: any) => html`
                  <div class="project-entry">
                    <h3 class="project-title">${item.title || '[Project Title]'}</h3>
                    <div class="project-description">
                      <ul>
                        ${this.toBulletPoints(item.details).map((point: string) => html`
                          <li>${point}</li>
                        `)}
                      </ul>
                    </div>
                  </div>
                `)}
              </section>
            ` : ''}

            <!-- Achievements Section -->
            ${this.hasContent(achievements) ? html`
              <section class="main-section">
                <h2 style="color: ${this.themeColor}">Achievements</h2>
                <ul class="achievements-list">
                  ${achievements.map((item: string, index: number) => item ? html`
                    <li>${item}</li>
                  ` : '')}
                </ul>
              </section>
            ` : ''}

            <!-- Publications Section -->
            ${this.hasContent(publications) ? html`
              <section class="main-section">
                <h2 style="color: ${this.themeColor}">Publications</h2>
                <ul class="achievements-list">
                  ${publications.map((item: string, index: number) => item ? html`
                    <li>${item}</li>
                  ` : '')}
                </ul>
              </section>
            ` : ''}

            <!-- Hobbies Section -->
            ${this.hasContent(hobbies) ? html`
              <section class="main-section">
                <h2 style="color: ${this.themeColor}">Hobbies</h2>
                <ul class="achievements-list">
                  ${hobbies.map((item: string, index: number) => item ? html`
                    <li>${item}</li>
                  ` : '')}
                </ul>
              </section>
            ` : ''}

            <!-- Trainings Section -->
            ${this.hasContent(trainings) ? html`
              <section class="main-section">
                <h2 style="color: ${this.themeColor}">Trainings</h2>
                <ul class="achievements-list">
                  ${trainings.map((item: string, index: number) => item ? html`
                    <li>${item}</li>
                  ` : '')}
                </ul>
              </section>
            ` : ''}

            <!-- References Section -->
            ${this.hasContent(references) ? html`
              <section class="main-section">
                <h2 style="color: ${this.themeColor}">References</h2>
                ${references.map((ref: any) => html`
                  <div class="reference-entry">
                    <h3 class="reference-name">${ref.name || '[Name]'}</h3>
                    <p class="reference-relationship">${ref.relationship || '[Relationship]'}</p>
                    <p class="reference-contact">${ref.contact || '[Contact]'}</p>
                  </div>
                `)}
              </section>
            ` : ''}
          </main>
        </div>
      </div>
    `;
  }
} 