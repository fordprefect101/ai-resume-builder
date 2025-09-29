import { Type } from "@google/genai";

const typeMap: { [key: string]: Type } = {
  'string': Type.STRING,
  'object': Type.OBJECT,
  'array': Type.ARRAY,
  'boolean': Type.BOOLEAN,
  'number': Type.NUMBER,
  'integer': Type.INTEGER,
};

/**
 * Recursively converts a standard JSON Schema into the format required
 * by the Google AI SDK for function calling and structured responses.
 * It primarily maps string-based types to the SDK's `Type` enum.
 * @param schema The JSON Schema object to convert.
 * @returns A new schema object compatible with the Google AI SDK.
 */
export const convertJsonSchemaToGoogleAiSchema = (schema: any): any => {
  if (!schema) return schema;

  // Create a copy to avoid mutating the original schema
  const newSchema = { ...schema };

  // Convert the main `type` property
  if (typeof schema.type === 'string' && typeMap[schema.type]) {
    newSchema.type = typeMap[schema.type];
  }

  // Recursively convert nested properties in an object
  if (schema.properties) {
    newSchema.properties = {};
    for (const key in schema.properties) {
      newSchema.properties[key] = convertJsonSchemaToGoogleAiSchema(schema.properties[key]);
    }
  }

  // Recursively convert the `items` schema in an array
  if (schema.items) {
    newSchema.items = convertJsonSchemaToGoogleAiSchema(schema.items);
  }

  // Recursively convert schemas in `oneOf` or `anyOf`
  if (schema.oneOf) {
    newSchema.oneOf = schema.oneOf.map(convertJsonSchemaToGoogleAiSchema);
  }
  if (schema.anyOf) {
      newSchema.anyOf = schema.anyOf.map(convertJsonSchemaToGoogleAiSchema);
  }

  return newSchema;
};