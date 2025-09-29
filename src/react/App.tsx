
import React, { useState } from 'react';
import { ResumeProvider, useResume } from './context/ResumeContext';
import ResumeForm from './components/ResumeForm';
import ResumePreview from './components/ResumePreview';

const THEME_COLORS = [
  '#2c3e50', // Default Slate
  '#27ae60', // Emerald
  '#2980b9', // Belize Hole
  '#c0392b', // Pomegranate
  '#8e44ad', // Wisteria
  '#d35400', // Pumpkin
];

const TEMPLATES = [
    { id: 'modern', name: 'Modern' },
    { id: 'classic', name: 'Classic' },
    { id: 'general', name: 'General' },
];

const ThemePicker: React.FC = () => {
    const { themeColor, updateThemeColor } = useResume();
    return (
        <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-slate-600">Theme:</span>
            {THEME_COLORS.map(color => (
                <button
                    key={color}
                    type="button"
                    onClick={() => updateThemeColor(color)}
                    className={`w-6 h-6 rounded-full border-2 transition-transform duration-150 ${themeColor === color ? 'border-sky-500 scale-110' : 'border-white hover:scale-110'}`}
                    style={{ backgroundColor: color }}
                    aria-label={`Select ${color} theme`}
                />
            ))}
        </div>
    );
}

const TemplatePicker: React.FC = () => {
    const { templateId, updateTemplate } = useResume();
    return (
        <div className="flex items-center gap-1 bg-slate-200 p-1 rounded-md">
             <span className="text-sm font-medium text-slate-600 px-2">Template:</span>
            {TEMPLATES.map(template => (
                <button
                    key={template.id}
                    onClick={() => updateTemplate(template.id)}
                    className={`px-3 py-1 text-sm font-semibold rounded-md transition-colors ${templateId === template.id ? 'bg-white text-sky-600 shadow-sm' : 'bg-transparent text-slate-700 hover:bg-slate-300/50'}`}
                >
                    {template.name}
                </button>
            ))}
        </div>
    );
}


const AppContent: React.FC = () => {
  const [view, setView] = useState<'form' | 'preview'>('form');

  if (view === 'form') {
    return (
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <header className="mb-8 text-center">
            <h1 className="text-4xl font-extrabold text-slate-900 tracking-tight">Resume Builder</h1>
            <p className="text-slate-500 mt-2 text-lg">Fill out the form below to generate your professional resume.</p>
        </header>
        <div className="bg-white p-6 sm:p-8 rounded-2xl shadow-lg border border-slate-200">
          <ResumeForm onPreview={() => setView('preview')} />
        </div>
      </div>
    );
  }

  return (
    <div className="bg-slate-50">
      <header className="sticky top-0 z-50 bg-white/80 backdrop-blur-lg shadow-sm no-print">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between h-16">
                <h1 className="text-xl font-bold text-slate-800">Resume Preview</h1>
                <div className="flex items-center gap-4">
                  <TemplatePicker />
                  <ThemePicker />
                  <button
                    onClick={() => setView('form')}
                    className="px-4 py-2 bg-slate-200 text-slate-800 text-sm font-semibold rounded-md hover:bg-slate-300 transition-colors"
                  >
                    Back to Editor
                  </button>
                   <button
                    onClick={() => window.print()}
                    className="px-4 py-2 bg-sky-600 text-white text-sm font-semibold rounded-md hover:bg-sky-700 transition-colors"
                  >
                    Print / Download PDF
                  </button>
                </div>
            </div>
          </div>
      </header>
      <main>
        <ResumePreview />
      </main>
    </div>
  );
}

const App: React.FC = () => {
  return (
    <ResumeProvider>
      <AppContent />
    </ResumeProvider>
  );
};

export default App;
