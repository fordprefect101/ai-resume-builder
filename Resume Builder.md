# Resume Builder

# Project Specifications

1. Gather all the relevant information from a candidate that pertains to following sections:

   1. Personal Details  
      - Basic Details (required): name, mobile, email, address, hometown, dateOfBirth, onlineProfiles (linkedIn, gitHub, portfolio)
      - More Details: resumeHeadline, gender, maritalStatus, category, differentlyAbled, disabilityType, disabilityAssistance, careerBreak, reasonOfBreak, breakStartedFrom, breakEndedIn, workPermits, nationality, passportNumber, visaStatus
   2. Career Details  
   3. Employment  
   4. Education  
   5. Projects  
   6. Certifications  
   7. Languages  
   8. Online Profiles  
   9. References  
   10. Achievements  
   11. Publications  
   12. Hobbies  
   13. Trainings

2. The gathering of above information should be very casual so that the candidate feels as if they are not being interviewed for mechanically filling a form using voice, it should feel as if a friend is asking them about their life. For example, multiple questions should be bundled at time – like "Hey, where do you live these days, and where are you from; \<follow-up\>and btw, what's your address in Jaipur \< where do you live these days\>".

3. Once all the information is gathered, they should be able to review this information in a form style format and in case they want to change any information they should be able to do it using voice agent \[Stage 2\] or by clicking and changing the information manually. Gather the Photo upload at this point.

4. They will then choose 1 one the 10 templates and view their information in that template – review, download, print, share \[public URL\], email it.

5. This should be hosted on [https://hyrefox.com/free-resume-builer](https://hyrefox.com/free-resume-builer)

   1. User will be able to create a Resume  
   2. Then on saving, will be able to Signup / Register on the platform  
   3. They will be able to login to the platform to see their resume

6. Refer: [https://resume.io/app/resumes/4085718/edit](https://resume.io/app/resumes/4085718/edit)

# Appendix 1 – JSON Format

{  
  "personalDetails": {  
    "basicDetails": {  
      "name": "",  
      "mobile": "",  
      "email": "",  
      "address": "",  
      "hometown": "",  
      "dateOfBirth": "",                  // YYYY-MM-DD  
      "onlineProfiles": {  
        "linkedIn": "",  
        "gitHub": "",  
        "portfolio": ""  
      },
      "photoUrl": ""                       // URL or file path for resume headshot
    },  
    "moreDetails": {  
      "resumeHeadline": "",  
      "gender": "",  
      "maritalStatus": "",  
      "category": "",                     // e.g. General, OBC, SC, ST  
      "differentlyAbled": false,  
      "disabilityType": "",  
      "disabilityAssistance": "",  
      "careerBreak": false,  
      "reasonOfBreak": "",  
      "breakStartedFrom": "",             // YYYY-MM-DD  
      "breakEndedIn": "",                 // YYYY-MM-DD or "Present"  
      "workPermits": [ "" ],  
      "nationality": "",  
      "passportNumber": "",  
      "visaStatus": ""  
    }  
  },  
  "careerDetails": {  
    "keySkills": [ "" ],  
    "industry": "",  
    "department": "",  
    "roleCategory": "",  
    "jobRole": "",  
    "desiredJobType": "",               // e.g. Permanent, Contract  
    "desiredEmploymentType": "",        // e.g. Full-time, Part-time  
    "preferredShift": "",               // e.g. Day, Night  
    "preferredWorkLocation": [ "" ],  
    "noticePeriod": "",  
    "expectedSalary": ""  
  },  
  "employment": [  
    {  
      "companyName": "",  
      "jobTitle": "",  
      "joiningDate": "",                // YYYY-MM-DD  
      "leavingDate": "",                // YYYY-MM-DD or "Present"  
      "jobProfile": "",  
      "skillsUsed": [ "" ],  
      "employmentType": ""              // e.g. Full-time, Internship  
    }  
  ],  
  "education": [  
    {  
      "degree": "",                       
      "institute": "",  
      "course": "",                       
      "specialization": "",  
      "courseType": "",                   
      "fromDate": "",                     
      "toDate": ""                        
    }  
  ],  
  "projects": [  
    {  
      "title": "",  
      "during": "",                     // employer or institution name  
      "client": "",                     // optional  
      "duration": "",                   // e.g. "Jan 2023 – Jun 2023"  
      "details": ""  
    }  
  ],  
  "certifications": [  
    {  
      "title": "",  
      "provider": "",  
      "certificationURL": "",  
      "validityFrom": "",               // YYYY-MM-DD  
      "validityTo": ""                  // YYYY-MM-DD or empty  
    }  
  ],  
  "languages": [  
    {  
      "language": "",  
      "proficiency": "",                // e.g. Beginner, Fluent  
      "read": false,  
      "write": false,  
      "speak": false  
    }  
  ],  
  "onlineProfiles": {  
    "linkedIn": "",  
    "gitHub": "",  
    "portfolio": ""  
  },  
  "references": [  
    {  
      "name": "",  
      "relationship": "",  
      "contact": ""  
    }  
  ],  
  "achievements": [ "" ],   // Includes awards and recognitions
  "publications": [ "" ],  
  "hobbies": [ "" ],  
  "trainings": [  
    {  
      "title": "",  
      "provider": "",  
      "year": ""                       // YYYY or YYYY-MM  
    }  
  ]  
}

# Appendix 2

Example Conversation to gather information with branching

**0:** Hey! I'm putting together your resume info, let's just chat like we're catching up. Sounds good?

---

**1) Personal & Online Profiles**

**1:** First off, what should I call you (your full name), and can I snag your LinkedIn or GitHub (or portfolio) links too?

**2:** Sweet. And your mobile number and email?

**3:** Where are you living these days, and hey — where are you originally from (your hometown)? Also, what's the exact postal address?

**4:** Got it. Mind sharing a photo URL or file path for your resume headshot, plus a one-liner "resume headline"?

**5:** And a few more basics: gender, marital status, date of birth?

**6:** In India, there's the "category" box — e.g. General, OBC, SC, ST — plus are you differently-abled?

*(branch: if differentlyAbled: true)*  
**7:** Oh, gotcha — what's your disability type and what assistance do you need?

**8:** Ever taken a career break?

*(branch: if careerBreak: true)*  
**9:** No worries — what was the reason, when did it start, and has it ended yet (or still "Present")?

**10:** Which countries' work permits do you hold?

---

**2) Career & Compensation**

**1:** Now let's talk about career goals: what are your top key skills, and what industry/department do you work in?

**2:** How would you describe your role category vs. your actual job role?

**3:** What kind of jobs are you hunting for — permanent vs contract, full-time vs part-time, shift preference, and where would you like to work?

**4:** Quick one — what's your notice period, and what salary are you expecting?

---

**3) Work History (repeat until done)**

**1:** Tell me about your most recent job — company name, your title, when you joined and (if you've left) left, plus a quick "what you did" and what skills you used there.

**2:** Any other roles to add? 

*(branch: loop back until candidate says "no more")*

---

**4) Education (repeat until done)**

**1:** Cool— your highest degree first: degree name, institute, course & specialization, full-time or distance, and dates?

**2:** Any other diplomas or certifications?

*(branch: loop back until candidate says "no more")*

---

**5) Projects (repeat until done)**

**1:** Got any standout projects? For each: title, was it during a job or school (which one), client name if any, how long, and what you built.

**2:** More projects?

*(branch: loop back until candidate says "no more")*

---

**6) Certifications**

**1:** Any professional certs — title, provider, link, valid from/to?

**2:** More certifications?

*(branch: loop back until candidate says "no more")*

---

**7) Languages**

**1:** What languages do you know, and how well can you read/write/speak them?

---
**8) Extras**

**1:** References — want to list referees or just say "Available on request"?

**2:** Any achievements, awards or publications you might have?

**3:** Any Hobbies & interests?

**4:** Trainings or workshops you've done outside of school?