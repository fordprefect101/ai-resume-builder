
import React from 'react';
import { useResume } from '../../context/ResumeContext';
import { Employment, Education, Project } from '../../types';

// --- UTILITIES (can be shared in a helpers file) ---
const hasContent = (data: any): boolean => {
    if (!data) return false;
    if (typeof data === 'boolean') return data;
    if (Array.isArray(data)) return data.length > 0 && data.some(item => hasContent(item));
    if (typeof data === 'object') return Object.values(data).some(val => hasContent(val));
    return !!data;
};

const formatDateRange = (from?: string, to?: string, isOngoing?: boolean) => {
  const fromDate = from ? new Date(from).getFullYear() : '';
  const toDate = isOngoing ? 'Present' : (to ? (to.toLowerCase() === 'present' ? 'Present' : new Date(to).getFullYear()) : '');
  if (fromDate && toDate) return `${fromDate} – ${toDate}`;
  return fromDate || toDate;
};

const toBulletPoints = (text?: string): string[] => {
    if (!text) return [];
    return text.split('\n').map(line => line.trim().replace(/^-|^\*|^\•/,'').trim()).filter(line => line);
};

const GeneralTemplate: React.FC = () => {
  const { resumeData } = useResume();
  const { personalDetails, careerDetails, employment, education, projects, onlineProfiles, achievements, publications, hobbies, trainings } = resumeData;

  const Section: React.FC<{title: string; children: React.ReactNode; visible?: boolean}> = ({title, children, visible = true}) => {
    if (!visible) return null;
    return (
        <section className="mb-6 break-inside-avoid">
            <h2 className="font-inter text-xs font-bold uppercase tracking-wider text-slate-600 border-b border-slate-300 pb-1 mb-3">
                {title}
            </h2>
            <div className="text-sm">
                {children}
            </div>
        </section>
    )
  }

  return (
    <div className="print-container bg-slate-100 flex justify-center p-8 font-lora">
      <div className="print-page w-[210mm] min-h-[297mm] bg-white shadow-2xl p-10 text-slate-800">
        <header className="text-center mb-8 border-b-2 border-black pb-4">
          <h1 className="font-inter text-3xl font-bold tracking-normal text-black">
            {personalDetails.basicDetails.name || 'Your Name'}
          </h1>
          <div className="text-sm mt-2 text-slate-700">
            <span>{personalDetails.basicDetails.address}</span>
            {personalDetails.basicDetails.address && (personalDetails.basicDetails.mobile || personalDetails.basicDetails.email) && ' | '}
            <span>{personalDetails.basicDetails.mobile}</span>
            {personalDetails.basicDetails.mobile && personalDetails.basicDetails.email && ' | '}
            <a href={`mailto:${personalDetails.basicDetails.email}`} className="text-sky-700 hover:underline">{personalDetails.basicDetails.email}</a>
          </div>
        </header>

        <main>
          <Section title="Education" visible={hasContent(education)}>
             {education.map((edu, i) => (
              <div key={i} className="mb-3">
                <div className="flex justify-between items-baseline">
                  <h3 className="font-inter text-base font-bold">{edu.institute || '[Institute]'}</h3>
                   <div className="text-sm text-slate-500 font-medium">{formatDateRange(edu.fromDate, edu.toDate, edu.isCurrentlyStudying)}</div>
                </div>
                <h4 className="font-inter text-sm font-semibold text-slate-700">{edu.degree || '[Degree]'}, {edu.course || '[Course]'}</h4>
              </div>
            ))}
          </Section>

          <Section title="Experience" visible={hasContent(employment)}>
            {employment.map((job, i) => (
              <div key={i} className="mb-4">
                <div className="flex justify-between items-baseline">
                  <h3 className="font-inter text-base font-bold">{job.companyName || '[Company Name]'}</h3>
                  <div className="text-sm text-slate-500 font-medium">{formatDateRange(job.joiningDate, job.leavingDate, job.currentlyWorking)}</div>
                </div>
                <h4 className="font-inter text-sm font-semibold text-slate-700 mb-1 italic">{job.jobTitle || '[Job Title]'}</h4>
                <ul className="list-disc pl-5 space-y-1 text-sm text-slate-700">
                  {toBulletPoints(job.jobProfile).map((point, i) => <li key={i}>{point}</li>)}
                </ul>
              </div>
            ))}
          </Section>

          <Section title="Projects" visible={hasContent(projects)}>
             {projects.map((proj, i) => (
                <div key={i} className="mb-4">
                    <div className="flex justify-between items-baseline">
                        <h3 className="font-inter text-base font-bold">{proj.title || '[Project Title]'}</h3>
                         <div className="text-sm text-slate-500 font-medium">{proj.duration}</div>
                    </div>
                    <ul className="list-disc pl-5 space-y-1 text-sm text-slate-700">
                     {toBulletPoints(proj.details).map((point, i) => <li key={i}>{point}</li>)}
                    </ul>
                </div>
             ))}
          </Section>

          <Section title="Skills" visible={hasContent(careerDetails.keySkills)}>
            <p className="text-sm leading-relaxed text-slate-700">
              <span className="font-inter font-semibold">Technical Skills:</span> {careerDetails.keySkills.join(', ')}
            </p>
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

export default GeneralTemplate;
