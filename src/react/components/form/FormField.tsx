import React from 'react';
import { useResume } from '../../context/ResumeContext';
import { SchemaProperty } from '../../types';

interface FormFieldProps {
  path: string;
  schema: SchemaProperty;
  value: any; // Value can be string, number, boolean, etc.
}

const FormField: React.FC<FormFieldProps> = ({ path, schema, value }) => {
  const { updateField } = useResume();

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    updateField(path, e.target.value);
  };
  
  const handleCheckboxChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    updateField(path, e.target.checked);
  }

  const inputId = path.replace(/\[|\]|\./g, '-'); // Create a valid HTML id from the path

  // --- Boolean Checkbox ---
  if (schema.type === 'boolean') {
      return (
          <div className="flex items-center gap-x-2 pt-2">
               <input
                  id={inputId}
                  type="checkbox"
                  checked={!!value}
                  onChange={handleCheckboxChange}
                  className="h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-2 focus:ring-sky-500"
                />
              <label htmlFor={inputId} className="text-sm font-medium text-slate-700 select-none">
                {schema.title}
              </label>
          </div>
      );
  }

  const commonProps = {
    id: inputId,
    value: value || '',
    onChange: handleChange,
    placeholder: schema.title,
    className: "mt-1 block w-full px-3 py-2 bg-white border border-slate-300 rounded-md text-sm shadow-sm placeholder-slate-400 focus:outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500 disabled:bg-slate-50 disabled:text-slate-500 disabled:border-slate-200 disabled:shadow-none"
  };

  // --- Select Dropdown for Enums ---
  if (schema.enum) {
    return (
        <div>
            <label htmlFor={inputId} className="block text-sm font-medium text-slate-700">{schema.title}</label>
            <select {...commonProps}>
                <option value="" disabled>-- Select an option --</option>
                {schema.enum.map((option) => (
                    <option key={option} value={option}>{option}</option>
                ))}
            </select>
        </div>
    )
  }

  const renderInput = () => {
    if (schema.format === 'textarea') {
      return <textarea {...commonProps} rows={4} />;
    }

    // Special case for year-only fields
    if (schema.format === 'date' && schema.pattern === '^(\\d{4})$') {
      return (
        <input 
          type="number" 
          {...commonProps} 
          min="1900" 
          max="2100" 
          placeholder="YYYY"
          className="mt-1 block w-full px-3 py-2 bg-white border border-slate-300 rounded-md text-sm shadow-sm placeholder-slate-400 focus:outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500 disabled:bg-slate-50 disabled:text-slate-500 disabled:border-slate-200 disabled:shadow-none"
        />
      );
    }

    let inputType = "text";
    if (schema.format === 'date') inputType = "date";
    if (schema.format === 'email') inputType = "email";
    if (schema.format === 'uri') inputType = "url";

    return <input type={inputType} {...commonProps} />;
  };

  return (
    <div>
      <label htmlFor={inputId} className="block text-sm font-medium text-slate-700">
        {schema.title}
      </label>
      {renderInput()}
    </div>
  );
};

export default FormField;