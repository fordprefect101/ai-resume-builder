
import React from 'react';
import { useResume } from '../context/ResumeContext';
import ModernTemplate from './templates/ModernTemplate';
import ClassicTemplate from './templates/ClassicTemplate';
import GeneralTemplate from './templates/GeneralTemplate';

const ResumePreview: React.FC = () => {
    const { templateId } = useResume();

    // Conditionally render the selected template
    switch (templateId) {
        case 'classic':
            return <ClassicTemplate />;
        case 'general':
            return <GeneralTemplate />;
        case 'modern':
        default:
            return <ModernTemplate />;
    }
};

export default ResumePreview;
