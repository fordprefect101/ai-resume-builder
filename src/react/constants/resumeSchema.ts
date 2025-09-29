import { ResumeSchema } from '../types';

export const resumeSchema: ResumeSchema = {
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Resume",
  "type": "object",
  "properties": {
    "personalDetails": {
      "type": "object",
      "title": "Personal Details",
      "properties": {
        "basicDetails": {
          "type": "object",
          "title": "Basic Information",
          "properties": {
            "name": { "type": "string", "title": "Full Name" },
            "mobile": { "type": "string", "title": "Mobile Number" },
            "email": { "type": "string", "title": "Email Address", "format": "email" },
            "address": { "type": "string", "title": "Full Address" },
            "hometown": { "type": "string", "title": "Hometown" },
            "dateOfBirth": { "type": "string", "title": "Date of Birth", "format": "date" },
            "photoUrl": { "type": "string", "title": "URL to Profile Photo" }
          },
          "required": ["name", "email"]
        },
        "moreDetails": {
          "type": "object",
          "title": "More Personal Details",
          "properties": {
            "resumeHeadline": { "type": "string", "title": "Resume Headline / Job Title", "format": "textarea" },
            "gender": { "type": "string", "title": "Gender" },
            "maritalStatus": { "type": "string", "title": "Marital Status" },
            "category": { "type": "string", "title": "Category" },
            "differentlyAbled": { "type": "boolean", "title": "I am differently abled" },
            "careerBreak": { "type": "boolean", "title": "I have a career break" },
            "workPermits": {
              "type": "array", "title": "Work Permits",
              "items": { "type": "string" }
            },
            "nationality": { "type": "string", "title": "Nationality" }
          }
        }
      }
    },
    "careerDetails": {
      "type": "object",
      "title": "Career Details",
      "properties": {
        "keySkills": {
          "type": "array", "title": "Key Skills",
          "items": { "type": "string" }
        },
        "industry": { "type": "string", "title": "Industry" },
        "department": { "type": "string", "title": "Department" },
        "jobRole": { "type": "string", "title": "Job Role" },
        "desiredEmploymentType": { "type": "string", "title": "Desired Employment Type", "enum": ["Full-time", "Part-time", "Contract", "Internship"] },
        "preferredWorkLocation": {
          "type": "array", "title": "Preferred Work Locations",
          "items": { "type": "string" }
        },
        "noticePeriod": { "type": "string", "title": "Notice Period" },
        "expectedSalary": { "type": "string", "title": "Expected Salary (e.g., per annum)" }
      }
    },
    "employment": {
      "type": "array",
      "title": "Employment History",
      "items": {
        "type": "object",
        "title": "Job",
        "properties": {
          "companyName": { "type": "string", "title": "Company Name" },
          "jobTitle": { "type": "string", "title": "Job Title" },
          "joiningDate": { "type": "string", "title": "Joining Date", "format": "date" },
          "leavingDate": { "type": "string", "title": "Leaving Date (or 'Present')", "format": "date" },
          "jobProfile": { "type": "string", "title": "Job Profile / Responsibilities", "format": "textarea" },
        },
        "required": ["companyName", "jobTitle", "joiningDate"]
      }
    },
    "education": {
      "type": "array",
      "title": "Education",
      "items": {
        "type": "object",
        "title": "Qualification",
        "properties": {
          "degree": { "type": "string", "title": "Degree / Qualification" },
          "institute": { "type": "string", "title": "Institute / University" },
          "course": { "type": "string", "title": "Course" },
          "specialization": { "type": "string", "title": "Specialization" },
          "courseType": { "type": "string", "title": "Course Type", "enum": ["Full-time", "Part-time", "Correspondence"] },
          "fromDate": { "type": "string", "title": "Start Date", "format": "date" },
          "toDate": { "type": "string", "title": "End Date", "format": "date" }
        }
      }
    },
    "projects": {
      "type": "array",
      "title": "Projects",
      "items": {
        "type": "object",
        "title": "Project",
        "properties": {
          "title": { "type": "string", "title": "Project Title" },
          "client": { "type": "string", "title": "Client" },
          "duration": { "type": "string", "title": "Duration (e.g., 6 months)" },
          "details": { "type": "string", "title": "Project Details / My Role", "format": "textarea" }
        }
      }
    },
    "certifications": {
      "type": "array",
      "title": "Certifications",
      "items": {
        "type": "object",
        "title": "Certification",
        "properties": {
          "title": { "type": "string", "title": "Certification Name" },
          "provider": { "type": "string", "title": "Certification Body" },
          "certificationURL": { "type": "string", "title": "Certification URL", "format": "uri" },
        }
      }
    },
    "onlineProfiles": {
        "type": "object",
        "title": "Online Profiles",
        "properties": {
            "linkedIn": { "type": "string", "title": "LinkedIn Profile URL", "format": "uri" },
            "gitHub": { "type": "string", "title": "GitHub Profile URL", "format": "uri" },
            "portfolio": { "type": "string", "title": "Portfolio URL", "format": "uri" }
        }
    },
    "languages": {
      "type": "array",
      "title": "Languages Known",
      "items": {
        "type": "object",
        "title": "Language",
        "properties": {
          "language": { "type": "string", "title": "Language" },
          "proficiency": { "type": "string", "title": "Proficiency", "enum": ["Beginner", "Intermediate", "Advanced", "Native"] },
          "read": { "type": "boolean", "title": "Read" },
          "write": { "type": "boolean", "title": "Write" },
          "speak": { "type": "boolean", "title": "Speak" }
        }
      }
    },
    "achievements": {
      "type": "array",
      "title": "Achievements",
      "items": { "type": "string" }
    },
    "publications": {
      "type": "array",
      "title": "Publications",
      "items": { "type": "string" }
    },
    "hobbies": {
      "type": "array",
      "title": "Hobbies & Interests",
      "items": { "type": "string" }
    },
    "trainings": {
      "type": "array",
      "title": "Trainings",
      "items": {
        "type": "object",
        "properties": {
          "title": { "type": "string", "title": "Training Title" },
          "provider": { "type": "string", "title": "Training Provider" },
          "year": { "type": "string", "format": "date", "title": "Year", "pattern": "^(\\d{4})$" }
        },
        "required": ["title", "provider", "year"]
      }
    }
  },
  "additionalProperties": false
}
