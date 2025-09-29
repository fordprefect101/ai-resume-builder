import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';

@customElement('classic-template')
export class ClassicTemplate extends LitElement {
  @property({ type: Object }) resumeData: any = {};

  static styles = css`
    :host {
      display: block;
      font-family: 'Times', serif;
      font-size: 11pt;
      line-height: 1.2;
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
      padding: 0.5in;
      max-width: 8.5in;
      margin: 0 auto;
    }

    .header {
      text-align: center;
      margin-bottom: 20pt;
    }

    .name {
      font-size: 24pt;
      font-weight: bold;
      text-transform: uppercase;
      letter-spacing: 1px;
      margin: 0;
      color: #1f2937;
    }

    .headline {
      font-size: 12pt;
      font-weight: 500;
      margin: 4pt 0;
      color: #374151;
      font-style: italic;
    }

    .contact {
      font-size: 10pt;
      margin-top: 4pt;
      color: #374151;
    }

    .contact a {
      text-decoration: underline;
      color: inherit;
    }

    .section {
      margin-bottom: 15pt;
    }

    .section-title {
      font-size: 12pt;
      font-weight: bold;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      border-bottom: 1pt solid black;
      margin-bottom: 8pt;
      padding-bottom: 2pt;
      color: #1f2937;
    }

    .entry {
      margin-bottom: 12pt;
    }

    .entry-header {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
    }

    .entry-subheader {
      display: flex;
      justify-content: space-between;
      font-size: 10pt;
      font-style: italic;
      color: #6b7280;
    }

    .items {
      margin-top: 4pt;
      padding-left: 15pt;
      font-size: 10pt;
      color: #374151;
    }

    .items li {
      margin-bottom: 2pt;
    }

    .skills {
      font-size: 10pt;
      color: #374151;
    }

    .skill-category {
      margin-bottom: 4pt;
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

  render() {
    const { personalDetails, careerDetails, employment, education, projects, onlineProfiles, achievements, publications, hobbies, trainings, references } = this.resumeData;
    const { basicDetails, moreDetails } = personalDetails || {};
    const onlineProfilesData = basicDetails?.onlineProfiles || {};

    return html`
      <div class="print-container">
        <div class="print-page">
          <div class="header">
            <h1 class="name">${basicDetails?.name || 'Your Name'}</h1>
            <p class="headline">${moreDetails?.resumeHeadline || 'Professional Headline'}</p>
            <div class="contact">
              ${basicDetails?.mobile || ''} ${basicDetails?.mobile && basicDetails?.email ? '|' : ''} 
              ${basicDetails?.email ? html`<a href="mailto:${basicDetails.email}">${basicDetails.email}</a>` : ''}
              ${basicDetails?.email && onlineProfilesData?.linkedIn ? ' | ' : ''}
              ${onlineProfilesData?.linkedIn ? html`<a href="${onlineProfilesData.linkedIn}">LinkedIn</a>` : ''}
              ${onlineProfilesData?.linkedIn && onlineProfilesData?.gitHub ? ' | ' : ''}
              ${onlineProfilesData?.gitHub ? html`<a href="${onlineProfilesData.gitHub}">GitHub</a>` : ''}
            </div>
          </div>

          ${this.hasContent(education) ? html`
            <section class="section">
              <h2 class="section-title">Education</h2>
              ${education.map((edu: any) => html`
                <div class="entry">
                  <div class="entry-header">
                    <strong>${edu.institute || '[Institute]'}</strong>
                    <span>${this.formatDate(edu.fromDate)} - ${this.formatDateWithCheckbox(edu.toDate, edu.isCurrentlyStudying)}</span>
                  </div>
                  <div class="entry-subheader">
                    <span>${edu.degree || '[Degree]'}</span>
                    <span>${edu.course || '[Course]'}</span>
                  </div>
                </div>
              `)}
            </section>
          ` : ''}

          ${this.hasContent(employment) ? html`
            <section class="section">
              <h2 class="section-title">Experience</h2>
              ${employment.map((job: any) => html`
                <div class="entry">
                  <div class="entry-header">
                    <strong>${job.jobTitle || '[Job Title]'}</strong>
                    <span>${this.formatDate(job.joiningDate)} - ${this.formatDateWithCheckbox(job.leavingDate, job.currentlyWorking)}</span>
                  </div>
                  <div class="entry-subheader">
                    <span>${job.companyName || '[Company Name]'}</span>
                    <span>${job.employmentType || ''}</span>
                  </div>
                  <ul class="items">
                    ${this.toBulletPoints(job.jobProfile).map((point: string) => html`<li>${point}</li>`)}
                  </ul>
                </div>
              `)}
            </section>
          ` : ''}

          ${this.hasContent(projects) ? html`
            <section class="section">
              <h2 class="section-title">Projects</h2>
              ${projects.map((project: any) => html`
                <div class="entry">
                  <div class="entry-header">
                    <span><strong>${project.title || '[Project Title]'}</strong></span>
                    <span>${project.duration || ''}</span>
                  </div>
                  <div class="entry-subheader">
                    <span>${project.client || ''}</span>
                    <span>${project.during || ''}</span>
                  </div>
                  <ul class="items">
                    ${this.toBulletPoints(project.details).map((point: string) => html`<li>${point}</li>`)}
                  </ul>
                </div>
              `)}
            </section>
          ` : ''}

          ${this.hasContent(careerDetails?.keySkills) && Array.isArray(careerDetails?.keySkills) ? html`
            <section class="section">
              <h2 class="section-title">Technical Skills</h2>
              <div class="skills">
                <div class="skill-category">
                  <strong>Skills:</strong> ${careerDetails.keySkills.join(', ')}
                </div>
                ${careerDetails?.industry ? html`
                  <div class="skill-category">
                    <strong>Industry:</strong> ${careerDetails.industry}
                  </div>
                ` : ''}
                ${careerDetails?.department ? html`
                  <div class="skill-category">
                    <strong>Department:</strong> ${careerDetails.department}
                  </div>
                ` : ''}
              </div>
            </section>
          ` : ''}

          ${this.hasContent(achievements) ? html`
            <section class="section">
              <h2 class="section-title">Achievements</h2>
              <ul class="items">
                ${achievements.map((achievement: string) => html`<li>${achievement}</li>`)}
              </ul>
            </section>
          ` : ''}

          ${this.hasContent(publications) ? html`
            <section class="section">
              <h2 class="section-title">Publications</h2>
              <ul class="items">
                ${publications.map((publication: string) => html`<li>${publication}</li>`)}
              </ul>
            </section>
          ` : ''}

          ${this.hasContent(hobbies) ? html`
            <section class="section">
              <h2 class="section-title">Hobbies</h2>
              <ul class="items">
                ${hobbies.map((hobby: string) => html`<li>${hobby}</li>`)}
              </ul>
            </section>
          ` : ''}

          ${this.hasContent(trainings) ? html`
            <section class="section">
              <h2 class="section-title">Trainings</h2>
              <ul class="items">
                ${trainings.map((training: string) => html`<li>${training}</li>`)}
              </ul>
            </section>
          ` : ''}

          ${this.hasContent(references) ? html`
            <section class="section">
              <h2 class="section-title">References</h2>
              ${references.map((ref: any) => html`
                <div class="entry">
                  <div class="entry-header">
                    <strong>${ref.name || '[Name]'}</strong>
                  </div>
                  <div class="entry-subheader">
                    <span>${ref.relationship || '[Relationship]'}</span>
                    <span>${ref.contact || '[Contact]'}</span>
                  </div>
                </div>
              `)}
            </section>
          ` : ''}
        </div>
      </div>
    `;
  }
} 