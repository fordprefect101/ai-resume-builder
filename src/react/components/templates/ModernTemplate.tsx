
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

const formatDate = (dateStr?: string) => {
    if (!dateStr || dateStr.toLowerCase() === 'present') return 'Present';
    if (isNaN(new Date(dateStr).getTime())) return dateStr;
    const date = new Date(dateStr);
    const utcDate = new Date(date.valueOf() + date.getTimezoneOffset() * 60 * 1000);
    return new Intl.DateTimeFormat('en-US', { month: 'short', year: 'numeric' }).format(utcDate);
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
const IconAddress = () => <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>

// --- MODERN TEMPLATE COMPONENTS ---

const SidebarSection: React.FC<{ title: string; children: React.ReactNode; visible?: boolean }> = ({ title, children, visible = true }) => {
    if (!visible) return null;
    return (
        <div className="mb-6 break-inside-avoid">
            <h3 className="text-sm font-bold uppercase tracking-widest text-white/90 mb-2">{title}</h3>
            {children}
        </div>
    );
};

const MainContentSection: React.FC<{ title: string; children: React.ReactNode; visible?: boolean, themeColor: string }> = ({ title, children, visible = true, themeColor }) => {
    if (!visible) return null;
    return (
        <section className="mb-6 break-inside-avoid">
            <h2 className="text-xl font-bold uppercase tracking-wider mb-2" style={{ color: themeColor }}>{title}</h2>
            {children}
        </section>
    );
};

const ExperienceEntry: React.FC<{ item: Employment }> = ({ item }) => (
    <div className="mb-4 break-inside-avoid">
        <div className="flex justify-between items-baseline">
            <h3 className="text-base font-bold text-slate-800">
                {item.jobTitle || '[Job Title]'}
            </h3>
            <div className="text-xs font-medium text-slate-500 text-right whitespace-nowrap">
                <span>{formatDate(item.joiningDate)} &ndash; {formatDate(item.leavingDate)}</span>
            </div>
        </div>
        <p className="text-sm font-semibold text-slate-600 mb-1">{item.companyName || '[Company Name]'}</p>
        <ul className="list-disc list-outside pl-5 mt-1 space-y-1 text-sm text-slate-700">
            {toBulletPoints(item.jobProfile).map((point, i) => <li key={i}>{point}</li>)}
        </ul>
    </div>
);

const EducationEntry: React.FC<{ item: Education }> = ({ item }) => (
     <div className="mb-3 break-inside-avoid">
        <div className="flex justify-between items-baseline">
            <h3 className="text-base font-bold text-slate-800">{item.degree || '[Degree]'}</h3>
            <div className="text-xs font-medium text-slate-500 text-right whitespace-nowrap">
                <span>{formatDate(item.fromDate)} &ndash; {formatDate(item.toDate)}</span>
            </div>
        </div>
        <p className="text-sm font-semibold text-slate-600">{item.institute || '[Institute]'}</p>
        <p className="text-sm italic text-slate-500">{item.course || '[Course]'}</p>
    </div>
);

// --- MAIN PREVIEW COMPONENT ---

const ModernTemplate: React.FC = () => {
  const { resumeData, themeColor } = useResume();
  const { personalDetails, careerDetails, employment, education, projects, onlineProfiles, languages, achievements, publications, hobbies, trainings } = resumeData;
  const { basicDetails, moreDetails } = personalDetails;

  const SkillPill: React.FC<{skill: string}> = ({skill}) => (
      <span className="inline-block bg-white/20 rounded-md px-2 py-1 text-xs font-medium">{skill}</span>
  )

  return (
    <div className="print-container bg-slate-100 flex justify-center py-8">
        <div className="print-page w-[210mm] min-h-[297mm] bg-white shadow-2xl flex font-sans">
            {/* === SIDEBAR === */}
            <aside className="w-1/3 text-white p-6 break-after-avoid" style={{ backgroundColor: themeColor }}>
                {basicDetails.photoUrl && (
                    <div className="mb-6 flex justify-center">
                        <img src={basicDetails.photoUrl} alt="Profile" className="w-32 h-32 rounded-full object-cover border-4 border-white/50 shadow-md" />
                    </div>
                )}

                <SidebarSection title="Contact">
                    <div className="space-y-2 text-sm">
                        {basicDetails.email && <div className="flex items-center gap-2"><IconMail /><a href={`mailto:${basicDetails.email}`} className="hover:underline">{basicDetails.email}</a></div>}
                        {basicDetails.mobile && <div className="flex items-center gap-2"><IconPhone /><span>{basicDetails.mobile}</span></div>}
                        {basicDetails.address && <div className="flex items-start gap-2"><IconAddress /><span className="leading-snug">{basicDetails.address}</span></div>}
                    </div>
                </SidebarSection>
                
                <SidebarSection title="Links" visible={hasContent(onlineProfiles)}>
                     <div className="space-y-2 text-sm">
                        {onlineProfiles.linkedIn && <div className="flex items-center gap-2"><IconLinkedIn /><a href={onlineProfiles.linkedIn} className="hover:underline" target="_blank" rel="noopener noreferrer">LinkedIn</a></div>}
                        {onlineProfiles.gitHub && <div className="flex items-center gap-2"><IconGitHub /><a href={onlineProfiles.gitHub} className="hover:underline" target="_blank" rel="noopener noreferrer">GitHub</a></div>}
                    </div>
                </SidebarSection>
                
                <SidebarSection title="Skills" visible={hasContent(careerDetails.keySkills)}>
                    <div className="flex flex-wrap gap-1.5">
                        {careerDetails.keySkills.map(skill => <SkillPill key={skill} skill={skill}/>)}
                    </div>
                </SidebarSection>

                <SidebarSection title="Languages" visible={hasContent(languages)}>
                     <div className="space-y-1 text-sm">
                        {languages.map(lang => (
                             <div key={lang.language}>{lang.language}</div>
                        ))}
                    </div>
                </SidebarSection>
            </aside>

            {/* === MAIN CONTENT === */}
            <main className="w-2/3 p-8 text-slate-700">
                <header className="mb-8 text-left">
                    <h1 className="text-5xl font-extrabold tracking-tight text-slate-900">{basicDetails.name || 'Your Name'}</h1>
                    <p className="text-xl font-medium mt-1" style={{color: themeColor}}>{moreDetails.resumeHeadline || 'Professional Headline'}</p>
                </header>
                
                <MainContentSection title="Experience" visible={hasContent(employment)} themeColor={themeColor}>
                    {employment.map((item, index) => <ExperienceEntry key={index} item={item} />)}
                </MainContentSection>

                <MainContentSection title="Education" visible={hasContent(education)} themeColor={themeColor}>
                    {education.map((item, index) => <EducationEntry key={index} item={item} />)}
                </MainContentSection>

                <MainContentSection title="Projects" visible={hasContent(projects)} themeColor={themeColor}>
                     {projects.map((item, index) => (
                        <div key={index} className="mb-4 break-inside-avoid">
                            <h3 className="text-base font-bold text-slate-800">{item.title || '[Project Title]'}</h3>
                            <ul className="list-disc list-outside pl-5 mt-1 space-y-1 text-sm text-slate-700">
                               {toBulletPoints(item.details).map((point, i) => <li key={i}>{point}</li>)}
                            </ul>
                        </div>
                    ))}
                </MainContentSection>
                
                 <MainContentSection title="Achievements" visible={hasContent(achievements)} themeColor={themeColor}>
                    <ul className="list-disc list-outside pl-5 space-y-1 text-sm text-slate-700">
                        {achievements.map((item, index) => item && <li key={index}>{item}</li>)}
                    </ul>
                </MainContentSection>

                <MainContentSection title="Publications" visible={hasContent(publications)} themeColor={themeColor}>
                    <ul className="list-disc list-outside pl-5 space-y-1 text-sm text-slate-700">
                        {publications.map((item, index) => item && <li key={index}>{item}</li>)}
                    </ul>
                </MainContentSection>

                <MainContentSection title="Hobbies" visible={hasContent(hobbies)} themeColor={themeColor}>
                    <ul className="list-disc list-outside pl-5 space-y-1 text-sm text-slate-700">
                        {hobbies.map((item, index) => item && <li key={index}>{item}</li>)}
                    </ul>
                </MainContentSection>

                <MainContentSection title="Trainings" visible={hasContent(trainings)} themeColor={themeColor}>
                    <ul className="list-disc list-outside pl-5 space-y-1 text-sm text-slate-700">
                        {trainings.map((item, index) => item && <li key={index}>{item}</li>)}
                    </ul>
                </MainContentSection>

            </main>
        </div>
    </div>
  );
};

export default ModernTemplate;
