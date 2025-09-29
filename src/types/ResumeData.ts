export interface ResumeData {
  personalDetails: {
    basicDetails: {
      name: string;
      mobile: string;
      email: string;
      address: string;
      hometown: string;
      dateOfBirth: string;
      onlineProfiles: {
        linkedIn: string;
        gitHub: string;
        portfolio: string;
      };
      photoUrl: string;
    };
    moreDetails: {
      resumeHeadline: string;
      gender: string;
      maritalStatus: string;
      category: string;
      differentlyAbled: boolean;
      disabilityType: string;
      disabilityAssistance: string;
      careerBreak: boolean;
      reasonOfBreak: string;
      breakStartedFrom: string;
      breakEndedIn: string;
      workPermits: string[];
      nationality: string;
      passportNumber: string;
      visaStatus: string;
    };
  };
  careerDetails: {
    keySkills: string[];
    industry: string;
    department: string;
    roleCategory: string;
    jobRole: string;
    desiredJobType: string;
    desiredEmploymentType: string;
    preferredShift: string;
    preferredWorkLocation: string[];
    noticePeriod: string;
    expectedSalary: string;
  };
  employment: Array<{
    companyName: string;
    jobTitle: string;
    joiningDate: string;
    leavingDate: string;
    jobProfile: string;
    skillsUsed: string[];
    employmentType: string;
  }>;
  education: Array<{
    degree: string;
    institute: string;
    course: string;
    specialization: string;
    courseType: string;
    fromDate: string;
    toDate: string;
  }>;
  projects: Array<{
    title: string;
    during: string;
    client: string;
    duration: string;
    details: string;
  }>;
  certifications: Array<{
    title: string;
    provider: string;
    certificationURL: string;
    validityFrom: string;
    validityTo: string;
  }>;
  languages: Array<{
    language: string;
    proficiency: string;
    read: boolean;
    write: boolean;
    speak: boolean;
  }>;
  onlineProfiles: {
    linkedIn: string;
    gitHub: string;
    portfolio: string;
  };
  references: Array<{
    name: string;
    relationship: string;
    contact: string;
  }>;
  achievements: string[];
  publications: string[];
  hobbies: string[];
  trainings: Array<{
    title: string;
    provider: string;
    year: string;
  }>;
} 