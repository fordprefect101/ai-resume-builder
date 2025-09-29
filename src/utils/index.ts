/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
*/
import {Blob} from '@google/genai';

function encode(bytes: Uint8Array): string {
  let binary = '';
  const len = bytes.byteLength;
  for (let i = 0; i < len; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

function decode(base64: string): Uint8Array {
  const binaryString = atob(base64);
  const len = binaryString.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return bytes;
}

function createBlob(data: Float32Array): Blob {
  const l = data.length;
  const int16 = new Int16Array(l);
  for (let i = 0; i < l; i++) {
    // convert float32 -1 to 1 to int16 -32768 to 32767
    int16[i] = data[i] * 32768;
  }

  return {
    data: encode(new Uint8Array(int16.buffer)),
    mimeType: 'audio/pcm;rate=16000',
  };
}

async function decodeAudioData(
  data: Uint8Array,
  ctx: AudioContext,
  sampleRate: number,
  numChannels: number,
): Promise<AudioBuffer> {
  if (numChannels <= 0) {
    console.error("decodeAudioData: numChannels must be positive.");
    // Return a minimal valid buffer or throw an error, depending on desired strictness
    // For now, returning a very short silent buffer to prevent downstream crashes.
    return ctx.createBuffer(1, 1, sampleRate); 
  }

  const buffer = ctx.createBuffer(
    numChannels,
    data.length / 2 / numChannels, // This is frames per channel; data.length is byte length of PCM S16LE
    sampleRate,
  );

  const dataInt16 = new Int16Array(data.buffer, data.byteOffset, data.length / 2);
  const dataFloat32 = new Float32Array(dataInt16.length);
  for (let i = 0; i < dataInt16.length; i++) {
    dataFloat32[i] = dataInt16[i] / 32768.0;
  }
  
  // Handles both mono (numChannels === 1) and stereo/multi-channel de-interleaving
  for (let i = 0; i < numChannels; i++) {
    const channelData = new Float32Array(buffer.length); // buffer.length is frames per channel
    for (let j = 0; j < buffer.length; j++) {
      channelData[j] = dataFloat32[j * numChannels + i];
    }
    buffer.copyToChannel(channelData, i);
  }

  return buffer;
}

export {createBlob, decode, decodeAudioData, encode};