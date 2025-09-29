import React from 'react';
import { resumeSchema } from '../constants/resumeSchema';
import { useResume } from '../context/ResumeContext';
import { ResumeData, SchemaProperty } from '../types';
import FormField from './form/FormField';
import ArrayField from './form/ArrayField';
import AiAutofill from './form/AiAutofill';

// A recursive component to render form elements based on the schema.
const FieldRenderer: React.FC<{
  path: string;
  schema: SchemaProperty;
  data: any;
}> = ({ path, schema, data }) => {
  
  // For 'object' types with properties, we create a nested section.
  if (schema.type === 'object' && schema.properties) {
    return (
      <div className="space-y-4 rounded-lg">
        {schema.title && <h3 className="text-md font-semibold text-slate-600 -mb-2">{schema.title}</h3>}
        {Object.entries(schema.properties).map(([key, propSchema]) => (
          <FieldRenderer
            key={key}
            path={`${path}.${key}`}
            schema={propSchema}
            data={data?.[key]}
          />
        ))}
      </div>
    );
  }

  // For 'array' types, we delegate to the ArrayField component.
  if (schema.type === 'array') {
    return (
      <ArrayField
        path={path as keyof ResumeData}
        schema={schema}
        value={data as any[] || []}
      />
    );
  }

  // For all primitive types (string, boolean, etc.), we render a FormField.
  return (
    <FormField
      path={path}
      schema={schema}
      value={data}
    />
  );
};

interface ResumeFormProps {
  onPreview: () => void;
}

const ResumeForm: React.FC<ResumeFormProps> = ({ onPreview }) => {
  const { resumeData } = useResume();

  return (
    <form className="space-y-8 pb-16" onSubmit={(e) => e.preventDefault()}>
      <AiAutofill />
      {Object.entries(resumeSchema.properties).map(([key, schema]) => {
        const fieldKey = key as keyof typeof resumeData;

        return (
          <section key={key} aria-labelledby={`${key}-heading`}>
            <h2 id={`${key}-heading`} className="text-xl font-semibold border-b-2 border-slate-200 pb-2 mb-4 text-slate-800">
              {schema.title}
            </h2>
            <div className="space-y-4">
              <FieldRenderer
                path={key}
                schema={schema}
                data={resumeData[fieldKey]}
              />
            </div>
          </section>
        );
      })}
      <div className="mt-12 pt-6 border-t border-slate-200 flex justify-end">
          <button
            type="button"
            onClick={onPreview}
            className="px-8 py-3 bg-sky-600 text-white text-lg font-semibold rounded-lg shadow-md hover:bg-sky-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-sky-500 transition-all duration-150 ease-in-out transform hover:scale-105"
          >
            Preview Resume →
          </button>
      </div>
    </form>
  );
};

export default ResumeForm;