
// --- Personal Details ---
export interface OnlineProfile {
  linkedIn?: string;
  gitHub?: string;
  portfolio?: string;
}

export interface BasicDetails {
  name: string;
  mobile?: string;
  email: string;
  address?: string;
  hometown?: string;
  dateOfBirth?: string;
  photoUrl?: string;
}

export interface MoreDetails {
  resumeHeadline?: string;
  gender?: string;
  maritalStatus?: string;
  category?: string;
  differentlyAbled?: boolean;
  disabilityType?: string;
  disabilityAssistance?: string;
  careerBreak?: boolean;
  reasonOfBreak?: string;
  breakStartedFrom?: string;
  breakEndedIn?: string; // Can be date or "Present"
  isBreakOngoing?: boolean; // Checkbox for "Currently on break"
  workPermits?: string[];
  nationality?: string;
  passportNumber?: string;
  visaStatus?: string;
}

export interface PersonalDetails {
  basicDetails: BasicDetails;
  moreDetails: MoreDetails;
}

// --- Career Details ---
export interface CareerDetails {
  keySkills: string[];
  industry?: string;
  department?: string;
  roleCategory?: string;
  jobRole?: string;
  desiredJobType?: string;
  desiredEmploymentType?: string;
  preferredShift?: string;
  preferredWorkLocation?: string[];
  noticePeriod?: string;
  expectedSalary?: string;
}

// --- Employment ---
export interface Employment {
  companyName: string;
  jobTitle: string;
  joiningDate: string;
  leavingDate?: string; // Can be date or "Present"
  currentlyWorking?: boolean; // Checkbox for "Currently working here"
  jobProfile?: string;
  skillsUsed?: string[];
  employmentType?: string;
}

// --- Education ---
export interface Education {
  degree?: string;
  institute?: string;
  course?: string;
  specialization?: string;
  courseType?: string;
  fromDate?: string;
  toDate?: string;
  isCurrentlyStudying?: boolean; // Checkbox for "Currently studying"
}

// --- Projects ---
export interface Project {
  title?: string;
  during?: string;
  client?: string;
  duration?: string;
  details?: string;
}

// --- Certifications ---
export interface Certification {
  title?: string;
  provider?: string;
  certificationURL?: string;
  validityFrom?: string;
  validityTo?: string; // Can be date or empty
  isValidOngoing?: boolean; // Checkbox for "Currently valid"
}

// --- Languages ---
export interface Language {
  language?: string;
  proficiency?: string;
  read?: boolean;
  write?: boolean;
  speak?: boolean;
}

// --- References ---
export interface Reference {
  name?: string;
  relationship?: string;
  contact?: string;
}

// --- Trainings ---
export interface Training {
  title?: string;
  provider?: string;
  year?: string;
}

// --- Main Resume Data Structure ---
export interface ResumeData {
  personalDetails: PersonalDetails;
  careerDetails: CareerDetails;
  employment: Employment[];
  education: Education[];
  projects: Project[];
  certifications: Certification[];
  languages: Language[];
  onlineProfiles: OnlineProfile;
  references: Reference[];
  achievements: string[];
  publications: string[];
  hobbies: string[];
  trainings: Training[];
}

export interface ResumeContextType {
  resumeData: ResumeData;
  themeColor: string;
  templateId: string;
  updateField: (path: string, value: any) => void;
  addArrayItem: (path: string) => void;
  removeArrayItem: (path: string, index: number) => void;
  loadResumeData: (data: ResumeData) => void;
  updateThemeColor: (color: string) => void;
  updateTemplate: (templateId: string) => void;
}

// --- JSON Schema Typing ---
// This interface defines the structure of a property within our JSON schema.
export interface SchemaProperty {
  type: 'string' | 'object' | 'array' | 'boolean' | 'number';
  title?: string;
  description?: string;
  // `format` provides semantic meaning to string types for UI hints.
  format?: 'date' | 'textarea' | 'email' | 'uri';
  // For 'object' types, `properties` defines nested fields.
  properties?: { [key: string]: SchemaProperty };
  // For 'array' types, `items` defines the schema for each element.
  items?: SchemaProperty;
  required?: string[];
  additionalProperties?: boolean;
  // `oneOf` and `anyOf` are JSON schema constructs for complex validation.
  oneOf?: SchemaProperty[];
  anyOf?: SchemaProperty[];
  // `enum` specifies a list of allowed values, perfect for dropdowns.
  enum?: string[];
  pattern?: string;
}

// This is the root schema interface for the entire resume.
export interface ResumeSchema {
  title: string;
  description?: string;
  type: 'object';
  properties: { [key: string]: SchemaProperty }; // Use a generic key index
  additionalProperties?: boolean;
  '$schema'?: string;
}