import express from 'express';
import path from 'path';
import cors from 'cors';
import dotenv from 'dotenv';
import { dirname } from 'path';
import { fileURLToPath } from 'url';
import OpenAI from 'openai'; // Added for resume extraction endpoint
import fs from 'fs'; // For loading the schema from file
import crypto from 'crypto'; // For generating unique session IDs
// In-memory storage for resume data (in production, use a database)
const resumeStorage = new Map();

// Session tracking for automated completion detection
const activeSessions = new Map();

dotenv.config();

const PORT = process.env.PORT || 8081;
const app = express();

const __dirname = dirname(fileURLToPath(import.meta.url));

app.use(express.static(path.join(__dirname, 'public')));
app.use(cors());
app.use(express.json());

// Serve the resume schema
app.get('/resume-schema.json', (req, res) => {
  res.sendFile(path.join(__dirname, 'resume-schema.json'));
});

//Config for OpenAI Realtime API
const instructions = `You are a friendly, voice-first resume-building assistant. 
You're helping a friend put together their resume by having a natural, warm conversation — like 
you're catching up over coffee. Your tone must always be friendly, casual, and supportive — like a thoughtful 
friend who's just curious about their journey. NEVER sound robotic, stiff, or like you're filling a form.

---

🔁 FLOW CONTROL (IMPORTANT):  
You **strictly** follow the script flow step-by-step in the order provided below.  
Do **not skip**, **rearrange**, or **combine distant sections**.  
After each section, ask if the user wants to add another item (where applicable).  
Only move to the next section once the user says "done" or "no more".

---

🛠️ HIDDEN LOGIC (Do Not Show or Mention to User):

- Mobile number: must be 10 digits.
- Email: must contain '@'
- Address: must include house/flat number, street, and city.
- Date of birth: collect full date (day, month, year).
- If address contains 'India', ask for category (General, OBC, etc.).
- Ask if they're 'differently abled' and collect details only if they say yes.
- Ask if they've had a 'career break'; collect reason/timeline only if yes.
- Always ask to add another for work experience, education, projects, certifications.
- Never say 'please enter' or mention rules/validations.

---
📌 Acknowledging Inputs:
Do NOT repeat the user's input back word-for-word.

Instead, acknowledge naturally with friendly affirmations like:
- 'Alright, got it.'
- 'Perfect, thanks.'
- 'Cool, let's keep going.'

Only repeat or rephrase what they said if:
1. You didn't understand it,
2. You're confirming something specific,
3. Or the user asks you to.


---

💬 TONE & STYLE:

- Always sound like you're catching up with a friend.
- Group related questions into one friendly sentence.
- Keep responses short, natural, and voice-optimized.
- Avoid technical terms like 'field' or 'required'.
- Say things like:  
  - 'Cool, tell me about...'  
  - 'Want to add another one?'  
  - 'Totally fine — what happened during that time?'
  - 'Alright, just a few more basics...'

---

🧭 SCRIPT FLOW (Follow Exactly, Do Not Skip or Reorder):

**1) Personal & Online Profiles**
- Full name + LinkedIn/GitHub/Portfolio
- Mobile number + Email
- Current location + Hometown
- Full address
- Resume photo (URL/path) + One-line headline
- Gender + Marital status + Date of birth
- (If India) Ask for category
- Ask: Are you differently-abled?
  → If yes, ask for type of disability and assistance needed
- Ask: Have you had a career break?
  → If yes, ask for reason, start date, and current status
- Ask: Do you hold any work permits?

**2) Career & Compensation**
- Key skills + Industry/Department
- Role category vs actual role
- Open to: job types (full-time/part-time/contract) + shift + preferred locations
- Notice period + Salary expectation

**3) Work Experience **
- For each job: Company, role, start/end dates, responsibilities, tools/skills
- Ask: Got another job to add?

**4) Education **
- For each degree: Degree name, college, specialization, mode (full-time/distance), year
- Ask: Got another one?

**5) Projects **
- For each: Title, during job or college, client (if any), duration, what was built/done
- Ask: Any more?

**6) Certifications **
- For each: Title, issuer, valid period, link
- Ask: Any more?

**7) Languages**
- For each: Language + comfort in reading, writing, speaking

**8) Extras**
- References or "Available on request"?
- Awards or recognitions?
- Any publications?
- Hobbies or interests?
- Trainings or workshops?

---

✅ FINAL WRAP-UP  
Once everything is collected, give a friendly summary like:

"Alright! I've got everything I need.  
Your name is ____, you're based in ____, your number is ____, and your email's ____.  
You've studied at ____, worked at ____, done awesome projects like ____, and have achievements like ____...  
Looks like you're all   set!"

Let it feel warm and encouraging — like you're proud of them. 🎉

`;

// Hardcoded config object
const config = {
  model: "gpt-4o-mini-realtime-preview-2024-12-17",
  modalities: ["audio", "text"],
  instructions: instructions,
  voice: "echo",
  input_audio_format: "pcm16",
  output_audio_format: "pcm16",
  input_audio_transcription: {
    model: "whisper-1",
  },
  tools: [],
  tool_choice: "none",
  turn_detection: {
    type: "server_vad",
    threshold: 0.5,
    prefix_padding_ms: 300,
    silence_duration_ms: 500,
    create_response: true,
    interrupt_response: true
    }
};

// API route for token generation (following openai-realtime-console-main pattern)
app.get("/token", async (req, res) => {
  try {
    if (!process.env.OPENAI_API_KEY) {
      console.error('OPENAI_API_KEY not found in environment variables');
      return res.status(500).json({ error: 'OpenAI API key not configured' });
    }

    const response = await fetch(
      "https://api.openai.com/v1/realtime/sessions",
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${process.env.OPENAI_API_KEY}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model: config.model,
          voice: config.voice,
          modalities: config.modalities,
          input_audio_format: config.input_audio_format,
          output_audio_format: config.output_audio_format,
          input_audio_transcription: config.input_audio_transcription,
          tools: config.tools,
          tool_choice: config.tool_choice,
          turn_detection: config.turn_detection,
        }),
      },
    );

    if (!response.ok) {
      const errorData = await response.text();
      console.error("OpenAI API error:", response.status, errorData);
      return res.status(response.status).json({ error: `OpenAI API error: ${response.status}` });
    }

    const data = await response.json();
    console.log("Token generated successfully for model:", config.model);
    res.json(data);
  } catch (error) {
    console.error("Token generation error:", error);
    res.status(500).json({ error: "Failed to generate token" });
  }
});

// --- Resume Data Retrieval Endpoint ---
app.get('/resume/:sessionId', (req, res) => {
  try {
    const { sessionId } = req.params;
    const resumeData = resumeStorage.get(sessionId);
    
    if (!resumeData) {
      return res.status(404).json({ error: 'Resume data not found for this session' });
    }
    
    res.json(resumeData.resume);
  } catch (error) {
    console.error('Resume retrieval error:', error);
    res.status(500).json({ error: `Failed to retrieve resume: ${error.message}` });
  }
});

// --- Enhanced Resume Endpoints for Phase 1 ---

// Update resume data
app.put('/resume/:sessionId', express.json(), async (req, res) => {
  try {
    const { sessionId } = req.params;
    const updatedResume = req.body;
    
    const existingData = resumeStorage.get(sessionId);
    if (!existingData) {
      return res.status(404).json({ error: 'Resume data not found for this session' });
    }
    
    // Update the resume data
    existingData.resume = updatedResume;
    existingData.lastUpdated = new Date().toISOString();
    
    resumeStorage.set(sessionId, existingData);
    
    console.log('Resume updated successfully for session:', sessionId);
    res.json({ success: true, sessionId });
  } catch (error) {
    console.error('Resume update error:', error);
    res.status(500).json({ error: `Failed to update resume: ${error.message}` });
  }
});

// Delete resume data
app.delete('/resume/:sessionId', (req, res) => {
  try {
    const { sessionId } = req.params;
    
    if (!resumeStorage.has(sessionId)) {
      return res.status(404).json({ error: 'Resume data not found for this session' });
    }
    
    resumeStorage.delete(sessionId);
    activeSessions.delete(sessionId);
    
    console.log('Resume deleted successfully for session:', sessionId);
    res.json({ success: true });
  } catch (error) {
    console.error('Resume deletion error:', error);
    res.status(500).json({ error: `Failed to delete resume: ${error.message}` });
  }
});

// Export resume as PDF/Word (placeholder for Phase 4)
app.get('/resume/:sessionId/export', (req, res) => {
  try {
    const { sessionId } = req.params;
    const { format = 'pdf' } = req.query;
    
    const resumeData = resumeStorage.get(sessionId);
    if (!resumeData) {
      return res.status(404).json({ error: 'Resume data not found for this session' });
    }
    
    // TODO: Implement actual PDF/Word generation in Phase 4
    console.log(`Export requested for session ${sessionId} in ${format} format`);
    res.json({ 
      success: true, 
      message: `Export functionality will be implemented in Phase 4`,
      format,
      sessionId 
    });
  } catch (error) {
    console.error('Resume export error:', error);
    res.status(500).json({ error: `Failed to export resume: ${error.message}` });
  }
});

// Apply template to resume (placeholder for Phase 4)
app.post('/resume/:sessionId/template', express.json(), (req, res) => {
  try {
    const { sessionId } = req.params;
    const { templateId } = req.body;
    
    const resumeData = resumeStorage.get(sessionId);
    if (!resumeData) {
      return res.status(404).json({ error: 'Resume data not found for this session' });
    }
    
    // TODO: Implement template application in Phase 4
    console.log(`Template ${templateId} requested for session ${sessionId}`);
    res.json({ 
      success: true, 
      message: `Template functionality will be implemented in Phase 4`,
      templateId,
      sessionId 
    });
  } catch (error) {
    console.error('Template application error:', error);
    res.status(500).json({ error: `Failed to apply template: ${error.message}` });
  }
});

// --- Automated Completion Detection ---

// Function to detect completion based on AI response
function detectCompletion(aiMessage) {
  const completionKeywords = [
    'alright! i\'ve got everything i need',
    'looks like you\'re all set',
    'that\'s everything i need',
    'perfect! i have all the information',
    'great! i\'ve collected everything',
    'excellent! i have your complete resume',
    'wonderful! i\'ve got all your details',
    'fantastic! your resume is complete',
    'super! i have everything i need',
    'brilliant! your resume is ready'
  ];
  
  const lowerMessage = aiMessage.toLowerCase();
  return completionKeywords.some(keyword => lowerMessage.includes(keyword));
}

// Enhanced resume extraction with completion detection
app.post('/extract-resume', express.json(), async (req, res) => {
  try {
    if (!process.env.OPENAI_API_KEY) {
      return res.status(500).json({ error: 'OpenAI API key not configured' });
    }
    const { conversation, sessionId } = req.body;
    if (!conversation || !Array.isArray(conversation)) {
      return res.status(400).json({ error: 'Missing or invalid conversation array' });
    }

    // Check if this is a completion-triggered extraction
    const isCompletionExtraction = sessionId && activeSessions.has(sessionId);
    
    // Initialize OpenAI client for this specific endpoint (model isolation)
    const openai = new OpenAI({
      apiKey: process.env.OPENAI_API_KEY,
    });

    // Load the resume schema from file
    const appendix1Schema = fs.readFileSync(path.join(__dirname, 'resume-schema.json'), 'utf8');

    // Build the prompt
    const systemPrompt = `You are an expert resume parser. Extract the following conversation into a structured resume JSON in this format:

${appendix1Schema}

Only output valid JSON matching the schema above. Output only the JSON object, with no extra text or explanation.`;

    const userPrompt = `Conversation to extract resume from:
${conversation.map(msg => `${msg.speaker}: ${msg.message}`).join('\n')}`;

    console.log('Calling GPT-4o mini for resume extraction...');
    const completion = await openai.chat.completions.create({
      model: 'gpt-4o-mini-2024-07-18', // Explicit model specification for isolation
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: userPrompt }
      ],
      response_format: { type: 'json_object' },
      temperature: 0.1,
    });

    const extractedResume = JSON.parse(completion.choices[0].message.content);
    
    // Generate a unique session ID if not provided
    const finalSessionId = sessionId || crypto.randomUUID();
    
    // Store the resume data with enhanced metadata
    resumeStorage.set(finalSessionId, {
      resume: extractedResume,
      conversation: conversation,
      timestamp: new Date().toISOString(),
      sessionId: finalSessionId,
      isCompletionExtraction: isCompletionExtraction,
      extractionMethod: isCompletionExtraction ? 'automated' : 'manual'
    });

    // Clean up active session if this was a completion extraction
    if (isCompletionExtraction) {
      activeSessions.delete(finalSessionId);
      console.log('Session completed and cleaned up:', finalSessionId);
    }

    console.log('Resume extracted successfully, session ID:', finalSessionId);
    res.json({ 
      sessionId: finalSessionId, 
      success: true,
      isCompletionExtraction: isCompletionExtraction
    });

  } catch (error) {
    console.error('Resume extraction error:', error);
    res.status(500).json({ error: `Resume extraction failed: ${error.message}` });
  }
});

// --- Session Management Endpoints ---

// Start a new session
app.post('/session/start', (req, res) => {
  try {
    const sessionId = crypto.randomUUID();
    const sessionData = {
      sessionId,
      startTime: new Date().toISOString(),
      status: 'active',
      conversationHistory: []
    };
    
    activeSessions.set(sessionId, sessionData);
    
    console.log('New session started:', sessionId);
    res.json({ sessionId, success: true });
  } catch (error) {
    console.error('Session start error:', error);
    res.status(500).json({ error: `Failed to start session: ${error.message}` });
  }
});

// Get session status
app.get('/session/:sessionId/status', (req, res) => {
  try {
    const { sessionId } = req.params;
    const sessionData = activeSessions.get(sessionId);
    
    if (!sessionData) {
      return res.status(404).json({ error: 'Session not found' });
    }
    
    res.json(sessionData);
  } catch (error) {
    console.error('Session status error:', error);
    res.status(500).json({ error: `Failed to get session status: ${error.message}` });
  }
});

// Update session with conversation data
app.post('/session/:sessionId/update', express.json(), (req, res) => {
  try {
    const { sessionId } = req.params;
    const { conversationEntry } = req.body;
    
    const sessionData = activeSessions.get(sessionId);
    if (!sessionData) {
      return res.status(404).json({ error: 'Session not found' });
    }
    
    // Add conversation entry
    sessionData.conversationHistory.push(conversationEntry);
    
    // Check for completion if it's an AI message
    if (conversationEntry.speaker === 'assistant') {
      const isComplete = detectCompletion(conversationEntry.message);
      if (isComplete) {
        sessionData.status = 'complete';
        sessionData.completionTime = new Date().toISOString();
        console.log('Session completion detected:', sessionId);
      }
    }
    
    activeSessions.set(sessionId, sessionData);
    
    res.json({ 
      success: true, 
      isComplete: sessionData.status === 'complete',
      sessionId 
    });
  } catch (error) {
    console.error('Session update error:', error);
    res.status(500).json({ error: `Failed to update session: ${error.message}` });
  }
});

// --- Health Check Endpoint ---
app.get('/health', (req, res) => {
  res.json({ 
    status: 'healthy', 
    activeSessions: activeSessions.size,
    storedResumes: resumeStorage.size,
    timestamp: new Date().toISOString()
  });
});

app.listen(PORT, () => {
  console.log(`Express server running on *:${PORT}`);
  console.log(`Health check available at: http://localhost:${PORT}/health`);
});



