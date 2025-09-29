
import React from 'react';
import { useResume } from '../../context/ResumeContext';
import { Employment, Education, Project } from '../../types';

// --- UTILITIES ---
const hasContent = (data: any): boolean => {
    if (!data) return false;
    if (typeof data === 'boolean') return data;
    if (Array.isArray(data)) return data.length > 0 && data.some(item => hasContent(item));
    if (typeof data === 'object') return Object.values(data).some(val => hasContent(val));
    return !!data;
};

const formatDateRange = (from?: string, to?: string) => {
  const fromDate = from ? new Date(from).getFullYear() : '';
  const toDate = to ? (to.toLowerCase() === 'present' ? 'Present' : new Date(to).getFullYear()) : '';
  if (fromDate && toDate) return `${fromDate} – ${toDate}`;
  return fromDate || toDate;
};

const toBulletPoints = (text?: string): string[] => {
    if (!text) return [];
    return text.split('\n').map(line => line.trim().replace(/^-|^\*|^\•/,'').trim()).filter(line => line);
};

// --- ICONS ---
const IconMail = () => <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg>;
const IconPhone = () => <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"></path></svg>;
const IconLinkedIn = () => <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"></path><rect x="2" y="9" width="4" height="12"></rect><circle cx="4" cy="4" r="2"></circle></svg>;
const IconGitHub = () => <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"></path></svg>;


const ClassicTemplate: React.FC = () => {
  const { resumeData } = useResume();
  const { personalDetails, careerDetails, employment, education, projects, onlineProfiles, achievements, publications, hobbies, trainings } = resumeData;

  const Section: React.FC<{title: string; children: React.ReactNode; visible?: boolean}> = ({title, children, visible = true}) => {
    if (!visible) return null;
    return (
        <section className="mb-5 break-inside-avoid">
            <h2 className="font-inter text-sm font-bold uppercase tracking-widest text-slate-700 border-b-2 border-slate-400 pb-1 mb-3">
                {title}
            </h2>
            {children}
        </section>
    )
  }

  return (
    <div className="print-container bg-slate-100 flex justify-center p-8 font-lora">
      <div className="print-page w-[210mm] min-h-[297mm] bg-white shadow-2xl p-12 text-slate-800">
        <header className="text-center mb-10">
          <h1 className="font-inter text-4xl font-extrabold tracking-tight text-slate-900">
            {personalDetails.basicDetails.name || 'Your Name'}
          </h1>
           <p className="font-inter text-md font-medium mt-2 text-slate-600">
            {personalDetails.moreDetails.resumeHeadline || 'Professional Headline'}
          </p>
          <div className="flex justify-center items-center gap-x-5 gap-y-1 text-xs mt-4 text-slate-600 flex-wrap">
            {personalDetails.basicDetails.email && <div className="flex items-center gap-1.5"><IconMail/>{personalDetails.basicDetails.email}</div>}
            {personalDetails.basicDetails.mobile && <div className="flex items-center gap-1.5"><IconPhone/>{personalDetails.basicDetails.mobile}</div>}
            {onlineProfiles.linkedIn && <div className="flex items-center gap-1.5"><IconLinkedIn/><a href={onlineProfiles.linkedIn} className="hover:text-sky-600">LinkedIn</a></div>}
            {onlineProfiles.gitHub && <div className="flex items-center gap-1.5"><IconGitHub/><a href={onlineProfiles.gitHub} className="hover:text-sky-600">GitHub</a></div>}
          </div>
        </header>

        <main>
          <Section title="Professional Experience" visible={hasContent(employment)}>
            {employment.map((job, i) => (
              <div key={i} className="mb-4 break-inside-avoid">
                <div className="flex justify-between items-baseline mb-1">
                  <h3 className="font-inter text-base font-bold">{job.jobTitle || '[Job Title]'}</h3>
                  <div className="text-sm text-slate-500 font-medium">{formatDateRange(job.joiningDate, job.leavingDate)}</div>
                </div>
                <h4 className="font-inter text-sm font-semibold text-slate-600 mb-1">{job.companyName || '[Company Name]'}</h4>
                <ul className="list-disc pl-5 space-y-1 text-sm text-slate-700">
                  {toBulletPoints(job.jobProfile).map((point, i) => <li key={i}>{point}</li>)}
                </ul>
              </div>
            ))}
          </Section>

          <Section title="Education" visible={hasContent(education)}>
             {education.map((edu, i) => (
              <div key={i} className="mb-3 break-inside-avoid">
                <div className="flex justify-between items-baseline mb-1">
                  <h3 className="font-inter text-base font-bold">{edu.institute || '[Institute]'}</h3>
                   <div className="text-sm text-slate-500 font-medium">{formatDateRange(edu.fromDate, edu.toDate)}</div>
                </div>
                <h4 className="font-inter text-sm font-semibold text-slate-600">{edu.degree || '[Degree]'}</h4>
                {edu.course && <p className="text-sm italic text-slate-500">{edu.course}</p>}
              </div>
            ))}
          </Section>

          <Section title="Projects" visible={hasContent(projects)}>
             {projects.map((proj, i) => (
                <div key={i} className="mb-4 break-inside-avoid">
                    <h3 className="font-inter text-base font-bold">{proj.title || '[Project Title]'}</h3>
                    <ul className="list-disc pl-5 space-y-1 text-sm text-slate-700">
                     {toBulletPoints(proj.details).map((point, i) => <li key={i}>{point}</li>)}
                    </ul>
                </div>
             ))}
          </Section>

          <Section title="Skills" visible={hasContent(careerDetails.keySkills)}>
            <div className="text-sm leading-relaxed">
              {careerDetails.keySkills.join(' · ')}
            </div>
          </Section>

          <Section title="Achievements" visible={hasContent(achievements)}>
            <ul className="list-disc pl-5 space-y-1 text-sm text-slate-700">
              {achievements.map((ach, i) => <li key={i}>{ach}</li>)}
            </ul>
          </Section>

          <Section title="Publications" visible={hasContent(publications)}>
            <ul className="list-disc pl-5 space-y-1 text-sm text-slate-700">
              {publications.map((pub, i) => <li key={i}>{pub}</li>)}
            </ul>
          </Section>

          <Section title="Hobbies" visible={hasContent(hobbies)}>
            <ul className="list-disc pl-5 space-y-1 text-sm text-slate-700">
              {hobbies.map((hobby, i) => <li key={i}>{hobby}</li>)}
            </ul>
          </Section>

          <Section title="Trainings" visible={hasContent(trainings)}>
            <ul className="list-disc pl-5 space-y-1 text-sm text-slate-700">
              {trainings.map((training, i) => <li key={i}>{training}</li>)}
            </ul>
          </Section>
        </main>
      </div>
    </div>
  );
};

export default ClassicTemplate;
