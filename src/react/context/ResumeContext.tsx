
import React, { createContext, useState, useContext, ReactNode, useEffect } from 'react';
import { ResumeData, ResumeContextType, SchemaProperty } from '../types';
import { resumeSchema } from '../constants/resumeSchema';

const LOCAL_STORAGE_KEY = 'ai-resume-builder-data';
const THEME_STORAGE_KEY = 'ai-resume-builder-theme';
const TEMPLATE_STORAGE_KEY = 'ai-resume-builder-template';

// Helper to generate initial state from schema defaults
const generateInitialState = (): ResumeData => {
  const savedData = localStorage.getItem(LOCAL_STORAGE_KEY);
  if (savedData) {
      try {
          // Add basic validation to ensure it's not just a random string
          const parsed = JSON.parse(savedData);
          if(parsed.personalDetails) return parsed;
      } catch (e) {
          console.error("Failed to parse resume data from local storage", e);
      }
  }

  return {
    personalDetails: {
      basicDetails: { name: '', mobile: '', email: '', address: '', hometown: '', dateOfBirth: '', photoUrl: '' },
      moreDetails: { resumeHeadline: '', gender: '', maritalStatus: '', category: '', differentlyAbled: false, careerBreak: false, workPermits: [], nationality: '' },
    },
    careerDetails: { keySkills: [], industry: '', department: '', jobRole: '', desiredEmploymentType: '', preferredWorkLocation: [], noticePeriod: '', expectedSalary: '' },
    employment: [], education: [], projects: [], certifications: [], languages: [],
    onlineProfiles: { linkedIn: '', gitHub: '', portfolio: '' },
    achievements: [], hobbies: [], references: [], publications: [], trainings: [],
  };
};

// Helper to traverse the schema and find the definition for a nested property.
const getNestedSchema = (path: string): SchemaProperty | undefined => {
  const keys = path.split('.');
  let currentSchema: any = resumeSchema;
  for (const key of keys) {
    if (!currentSchema) return undefined;
    currentSchema = currentSchema.properties?.[key];
  }
  return currentSchema;
}

// Helper to create a new item for an array field based on its schema
const createNewArrayItem = (path: string) => {
  const schema = getNestedSchema(path);
  const itemSchema = schema?.items;
  if (!itemSchema) return ''; 

  if (itemSchema.type === 'object' && itemSchema.properties) {
    const newObject: { [key: string]: any } = {};
    for (const key in itemSchema.properties) {
      const prop = itemSchema.properties[key];
      if (prop.type === 'array') newObject[key] = [];
      else if (prop.type === 'boolean') newObject[key] = false;
      else if (prop.type === 'object') newObject[key] = {};
      else newObject[key] = '';
    }
    return newObject;
  }
  return ''; 
};

const ResumeContext = createContext<ResumeContextType | undefined>(undefined);

export const ResumeProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [resumeData, setResumeData] = useState<ResumeData>(generateInitialState);
  const [themeColor, setThemeColor] = useState<string>(() => localStorage.getItem(THEME_STORAGE_KEY) || '#2c3e50');
  const [templateId, setTemplateId] = useState<string>(() => localStorage.getItem(TEMPLATE_STORAGE_KEY) || 'modern');

  useEffect(() => {
    localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(resumeData));
  }, [resumeData]);

  useEffect(() => {
    localStorage.setItem(THEME_STORAGE_KEY, themeColor);
  }, [themeColor]);

  useEffect(() => {
    localStorage.setItem(TEMPLATE_STORAGE_KEY, templateId);
  }, [templateId]);


  const updateField = (path: string, value: any) => {
    setResumeData(prevData => {
      const keys = path.split(/[.\[\]]+/).filter(Boolean); 
      const newData = JSON.parse(JSON.stringify(prevData));
      let current: any = newData;
      for (let i = 0; i < keys.length - 1; i++) {
        if (!current[keys[i]]) {
            current[keys[i]] = /^\d+$/.test(keys[i+1]) ? [] : {};
        }
        current = current[keys[i]];
      }
      current[keys[keys.length - 1]] = value;
      return newData;
    });
  };

  const addArrayItem = (path: string) => {
    setResumeData(prevData => {
      const keys = path.split('.');
      const newData = JSON.parse(JSON.stringify(prevData));
      let current: any = newData;
      for (let i = 0; i < keys.length - 1; i++) {
          current = current[keys[i]];
      }
      const arrayKey = keys[keys.length - 1];
      const currentArray = current[arrayKey] || [];
      const newItem = createNewArrayItem(path);
      current[arrayKey] = [...currentArray, newItem];
      return newData;
    });
  };

  const removeArrayItem = (path: string, index: number) => {
     setResumeData(prevData => {
        const keys = path.split('.');
        const newData = JSON.parse(JSON.stringify(prevData));
        let current: any = newData;
        for (let i = 0; i < keys.length - 1; i++) {
          current = current[keys[i]];
        }
        const arrayKey = keys[keys.length - 1];
        const currentArray = current[arrayKey] || [];
        current[arrayKey] = currentArray.filter((_: any, i: number) => i !== index);
        return newData;
    });
  };

  const loadResumeData = (data: ResumeData) => {
      setResumeData(data);
  }

  const updateThemeColor = (color: string) => {
      setThemeColor(color);
  }

  const updateTemplate = (id: string) => {
      setTemplateId(id);
  }

  const contextValue = {
      resumeData,
      themeColor,
      templateId,
      updateField,
      addArrayItem,
      removeArrayItem,
      loadResumeData,
      updateThemeColor,
      updateTemplate
  }

  return (
    <ResumeContext.Provider value={contextValue}>
      {children}
    </ResumeContext.Provider>
  );
};

export const useResume = (): ResumeContextType => {
  const context = useContext(ResumeContext);
  if (!context) {
    throw new Error('useResume must be used within a ResumeProvider');
  }
  return context;
};