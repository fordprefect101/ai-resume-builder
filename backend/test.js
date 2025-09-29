// To run this code you need to install the following dependencies:
// npm install @google/genai mime
// npm install -D @types/node

import { GoogleGenAI } from '@google/genai';
import dotenv from 'dotenv';

dotenv.config();
const GEMINI_API_KEY = process.env.GEMINI_API_KEY;

async function main() {
  const ai = new GoogleGenAI({
    apiKey: GEMINI_API_KEY,
  });
  const config = {
    thinkingConfig: {
      thinkingBudget: -1,
    },
  };
  const model = 'gemini-2.5-flash';
  const contents = [
    {
      role: 'user',
      parts: [
        {
          text: `Give me all the details about Albert Hall Museum, Ram Niwas Garden, Ashok Nagar, Jaipur <Display Name>, <ShortAddress> from a perspective of a tourist visiting Jaipur <City>`,
        },
      ],
    },
  ];
  
  const result = await ai.models.generateContentStream({
    model,
    config,
    contents,
  });

  for await (const chunk of result.stream) {
    console.log(chunk.text());
  }
}

main();  