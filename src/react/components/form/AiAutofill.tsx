import React, { useState } from 'react';
import { useResume } from '../../context/ResumeContext';
import { autofillFromText } from '../../services/AIService';

const AiAutofill: React.FC = () => {
    const { loadResumeData } = useResume();
    const [inputText, setInputText] = useState('');
    const [loadingMessage, setLoadingMessage] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    
    const handleAutofill = async () => {
        if (!inputText.trim()) {
            setError("Please paste your resume text into the box first.");
            return;
        }

        setError(null);
        setLoadingMessage("Translating and parsing resume...");

        try {
            const parsedData = await autofillFromText(inputText);
            loadResumeData(parsedData);
            setInputText(''); // Clear the textarea on success

        } catch (e: any) {
            console.error("AI autofill failed:", e);
            setError(`An error occurred while processing the resume. Please check the console for details. (Error: ${e.message})`);
        } finally {
            setLoadingMessage(null);
        }
    };
    
    const isLoading = loadingMessage !== null;

    return (
        <section className="bg-sky-50 border-2 border-sky-200 p-6 rounded-xl space-y-4">
            <div className="flex items-center gap-3">
                 <span className="text-2xl">✨</span>
                 <div>
                    <h2 className="text-lg font-bold text-sky-900">Autofill with AI</h2>
                    <p className="text-sm text-sky-700">Paste your existing resume below and let AI fill out the form for you.</p>
                 </div>
            </div>

            <textarea
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder="Paste your entire resume here..."
                className="w-full h-32 p-3 border border-slate-300 rounded-md shadow-sm focus:outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500"
                disabled={isLoading}
            />

            {error && <p className="text-sm text-red-600 bg-red-100 p-3 rounded-md">{error}</p>}
            
            <button
                type="button"
                onClick={handleAutofill}
                disabled={isLoading}
                className="w-full flex justify-center items-center px-6 py-3 bg-sky-800 text-white text-md font-semibold rounded-lg shadow-md hover:bg-sky-900 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-sky-500 transition-all disabled:bg-slate-400 disabled:cursor-not-allowed"
            >
                {isLoading ? (
                    <>
                        <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        {loadingMessage}...
                    </>
                ) : (
                    'Fill Form with AI'
                )}
            </button>
        </section>
    );
};

export default AiAutofill;