
import { GoogleGenAI } from "@google/genai";
import { resumeSchema } from '../constants/resumeSchema';
import { convertJsonSchemaToGoogleAiSchema } from '../utils/schemaConverter';
import { ResumeData } from '../types';

if (!import.meta.env.VITE_API_KEY) {
    throw new Error("VITE_API_KEY environment variable not set.");
}

// Initialize the AI client once in a central place
const ai = new GoogleGenAI({ apiKey: import.meta.env.VITE_API_KEY });

/**
 * Processes raw resume text by translating it, parsing it into a structured
 * ResumeData object, and generating a professional headline, all using a

 * single, efficient API call.
 * @param text The raw resume text, in any language.
 * @returns A promise that resolves to the structured ResumeData object.
 */
export const autofillFromText = async (text: string): Promise<ResumeData> => {
    // Convert our standard JSON schema to the format the Gemini SDK requires.
    const geminiSchema = convertJsonSchemaToGoogleAiSchema(resumeSchema);
    
    // Use a single, powerful prompt to instruct the model to perform all steps at once.
    const response = await ai.models.generateContent({
        model: 'gemini-2.5-flash',
        contents: `Please process the following resume text:\n\n---\n\n${text}`,
        config: {
            // This system instruction is key. It tells the model to perform a multi-step process internally.
            systemInstruction: "You are an expert resume assistant. Your primary task is to create a structured JSON object from resume text, strictly following these rules:\n1. Translate the text to English internally before processing.\n2. Populate the provided JSON schema with the translated information.\n3. Generate a professional headline (4-8 words) for the 'personalDetails.moreDetails.resumeHeadline' field based on the structured data.\n4. **CRITICAL RULE:** For any current job or educational course (e.g., end date is 'Present' or ongoing), its corresponding end date field ('leavingDate' or 'toDate') in the JSON MUST be an empty string (\"\"). Do not guess a date, and do not use the word 'Present'.\nYour final output must be ONLY the populated JSON object, with no other text.",
            responseMimeType: "application/json",
            responseSchema: geminiSchema,
            temperature: 0.1, // Lower temperature for more deterministic, structured output
        },
    });

    const jsonText = response.text.trim();
    return JSON.parse(jsonText) as ResumeData;
};