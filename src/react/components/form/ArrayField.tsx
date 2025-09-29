
import React from 'react';
import { useResume } from '../../context/ResumeContext';
import { SchemaProperty } from '../../types';
import FormField from './FormField';

interface ArrayFieldProps {
  path: string; // Changed from keyof ResumeData to string to allow nested paths
  schema: SchemaProperty;
  value: any[];
}

const ArrayField: React.FC<ArrayFieldProps> = ({ path, schema, value }) => {
  const itemSchema = schema.items;

  return (
    <div className="space-y-4">
      {value.map((item, index) => (
        <div key={index} className="p-4 border border-slate-200 rounded-lg bg-slate-50/70 relative">
          <div className="space-y-4">
          {itemSchema && itemSchema.type === 'object' && itemSchema.properties ? (
            Object.entries(itemSchema.properties).map(([propKey, propSchema]) => (
              <FormField
                key={propKey}
                path={`${path}[${index}].${propKey}`}
                schema={propSchema}
                value={item[propKey]}
              />
            ))
          ) : (
            <FormField
                key={index}
                path={`${path}[${index}]`}
                schema={{ type: 'string', title: `${schema.title || 'Item'} #${index + 1}` }}
                value={item}
            />
          )}
          </div>
        </div>
      ))}
    </div>
  );
};

export default ArrayField;
