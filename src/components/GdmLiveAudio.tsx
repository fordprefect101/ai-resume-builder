/* tslint:disable */
/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */


import {LitElement, css, html} from 'lit';
import {customElement, state, property} from 'lit/decorators.js';
import './Visual3D';
import { WavRecorder } from '../wavtools/lib/wav_recorder';
import { WavStreamPlayer } from '../wavtools/lib/wav_stream_player';
// import { RealtimeClient } from '@openai/realtime-api-beta'; // Removed direct RealtimeClient import

// Helper to get the AudioContext class, accommodating vendor prefixes
const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;

// Declare the global function for TypeScript
declare global {
  interface Window {
    webkitAudioContext: typeof AudioContext;
    widgetEventHub: EventTarget; // Added for event hub
  }
}                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             



// Define a type for the widget configuration




// Replace direct OpenAI WebSocket with frontend proxy WebSocket
// let frontendSocket: WebSocket | null = null;



@customElement('gdm-live-audio')
export class GdmLiveAudio extends LitElement {
  @state() isRecording = false;
  @state() status = '';
  @state() error = '';
  @state() private isSessionInitialized = false;
  @state() private isSessionRecording = false;
  @state() isRelayConnected = false;

  private _apiKey: string | undefined;
  private _model: string = 'gemini-live-2.5-flash-preview';

  // Audio Processing Setup
  private wavRecorder = new WavRecorder({ sampleRate: 24000 });
  private wavStreamPlayer = new WavStreamPlayer({ sampleRate: 24000 });
  private recordingContext = new AudioContextClass({sampleRate: 48000});
  private recordingDestination = this.recordingContext.createMediaStreamDestination();
  private mediaRecorder: MediaRecorder | null = null;
  private recordedChunks: ArrayBuffer[] = [];
  
  // Session management
  private isSessionActive = false;
  private isSessionOperationInProgress = false;

  private nextStartTime = 0;
  private mediaStream: MediaStream | null = null;
  private errorTimeoutId: number | null = null;;

  // --- WebRTC Real-Time Audio Streaming ---
  private peerConnection: RTCPeerConnection | null = null;
  private remoteAudioElement: HTMLAudioElement | null = null;
  private streamingActive = false;
  private remoteAnalyser: AnalyserNode | null = null;
  private micAnalyser: AnalyserNode | null = null;
  private dataChannel: RTCDataChannel | null = null;
  private sessionCreated = false;
  // Minimal transcript capture: only speaker and message
  private conversationHistory: Array<{
    speaker: 'user' | 'assistant';
    message: string;
  }> = [];
  private sessionStartTime: string | null = null;
  private sessionId: string | null = null;
  
  // Enhanced session management for automated completion
  private isCompletionDetected = false;
  private sessionCompletionTimeout: number | null = null;
  private backendSessionId: string | null = null;

  static styles = css`
    :host {
      display: block;
      width: 100%;
      height: 100%;
      position: relative;
    }
    #status {
      position: absolute;
      bottom: 5vh;
      left: 0;
      right: 0;
      z-index: 10;
      text-align: center;
      color: #fff;
    }
    .controls {
      z-index: 10;
      position: absolute;
      bottom: 2vh;
      left: 0;
      right: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-direction: column;
      gap: 10px;
    }
    .controls button {
      outline: none;
      border: 1px solid rgba(255, 255, 255, 0.2);
      color: white;
      border-radius: 20px;
      background: rgba(255, 255, 255, 0.1);
      width: 32px;
      height: 32px;
      cursor: pointer;
      font-size: 24px;
      padding: 0;
      margin: 0;
    }
    .controls button:hover {
      background: rgba(255, 255, 255, 0.2);
    }
    .controls button[disabled] {
      display: none;
    }
  `;

  // ApiKey
  get apiKey(): string | undefined {
    return this._apiKey;
  }

  set apiKey(value: string | undefined) {
    const oldValue = this._apiKey;
    this._apiKey = value;
    this.requestUpdate('apiKey', oldValue);
  }

  get model(): string {
    return this._model;
  }

  set model(value: string) {
    this._model = value;
  }
    
  // Remove direct RealtimeClient
  // private client: RealtimeClient;

  constructor() {
    super();
    // API key is handled by the backend server via /token endpoint
    // No direct RealtimeClient instantiation
  }

  // --- Step 1: OpenAI Session and Greeting Logic ---

  /**
   * Call this method when the user clicks 'Build with AI'.
   * It will start the OpenAI session and send the greeting when ready.
   */
  public async resumePlayback() {
    if (this.wavStreamPlayer && this.wavStreamPlayer.context?.state === 'suspended') {
        console.log('Resuming suspended audio playback context...');
        await this.wavStreamPlayer.context.resume();
        this.updateStatus('Audio playback ready.');
    }
  }

  /**
   * End the current recording session
   */
  public async endRecordingSession() {
    if (this.isSessionOperationInProgress) {
      console.log('Session operation already in progress, skipping...');
      return;
    }
    
    this.isSessionOperationInProgress = true;
    
    try {
      if (this.wavRecorder && this.isSessionActive) {
        console.log('Ending recording session...');
        await this.wavRecorder.quit(); // Use quit() for complete cleanup
        this.isSessionActive = false;
        console.log('Recording session ended successfully');
      }
    } catch (err) {
      console.warn('Error ending recording session:', err);
      // Reset state even if there was an error
      this.isSessionActive = false;
    } finally {
      this.isSessionOperationInProgress = false;
    }
  }

  /**
   * Start recording with microphone permission check
   */
  public async startRecording() {
    if (this.isSessionOperationInProgress) {
      console.log('Session operation already in progress, skipping startRecording...');
      return;
    }
    
    this.isSessionOperationInProgress = true;
    
    try {
      // End any existing recording session first
      await this.endRecordingSession();

      // Start the recording
      console.log('Starting new recording session...');
      await this.wavRecorder.begin();
      await this.wavRecorder.record((audioData) => {
        // Audio recording callback - can be used for local processing
        console.log('Audio data recorded:', audioData.mono.byteLength, 'bytes');
      });
      
      this.isSessionActive = true;
      this.updateStatus('Recording started...');
      this.isRecording = true;
      
      // Trigger re-render after input analyser is initialized
      this.requestUpdate();
    } catch (err) {
      this.updateError('Failed to start recording: ' + err);
      this.isSessionActive = false;
    } finally {
      this.isSessionOperationInProgress = false;
    }
  }

  /**
   * Stop recording
   */
  public async stopRecording() {
    if (this.isSessionOperationInProgress) {
      console.log('Session operation already in progress, skipping stopRecording...');
      return;
    }
    
    this.isSessionOperationInProgress = true;
    
    const wasRecording = this.isRecording;
    this.isRecording = false;

    if (wasRecording) {
      this.updateStatus('Stopping recording...');
    }

    // End the recording session
    await this.endRecordingSession();

    if (wasRecording) {
      if (this.isSessionInitialized) {
        this.updateStatus('Recording stopped. Press 🔴 to start again.');
      } else {
        this.updateStatus('Recording stopped. Session is not active.');
      }
    } else {
      if (!this.isSessionInitialized) {
        this.updateStatus('Ready. Press the red button to start recording.');
      }
    }
    
    this.isSessionOperationInProgress = false;
  }

  /**
   * Reset the component
   */
  public async reset() {
    this.updateStatus('Resetting application...');
    this.updateError('');
    await this.stopRecording();

    this.isSessionInitialized = false;
    this.isSessionActive = false;
    this.isSessionOperationInProgress = false;
  }

  // --- WebRTC Real-Time Audio Streaming ---
  /**
   * Start real-time audio streaming (WebRTC)
   */
  public async startStreaming() {
    if (this.streamingActive) return;
    
    try {
      this.updateStatus('Starting WebRTC streaming...');
      
      // 1. Get session token from backend
      const tokenResponse = await fetch('http://localhost:8081/token');
      if (!tokenResponse.ok) {
        throw new Error(`Failed to get token: ${tokenResponse.status}`);
      }
      const tokenData = await tokenResponse.json();
      console.log('Token received:', tokenData);
      
      // 2. Create peer connection
      this.peerConnection = new RTCPeerConnection();
      
      // 3. Set up remote audio playback and analyser
      this.remoteAudioElement = document.createElement('audio');
      this.remoteAudioElement.autoplay = true;
      
      // Create audio context for remote audio analysis
      const remoteAudioContext = new AudioContext();
      const remoteSource = remoteAudioContext.createMediaElementSource(this.remoteAudioElement);
      const remoteAnalyser = remoteAudioContext.createAnalyser();
      remoteSource.connect(remoteAnalyser);
      remoteAnalyser.connect(remoteAudioContext.destination);
      this.remoteAnalyser = remoteAnalyser;
      
      // Handle remote audio track
      this.peerConnection.ontrack = (e) => {
        console.log('Remote audio track received');
        this.remoteAudioElement!.srcObject = e.streams[0];
      };
      
      // 4. Get mic and add to peer connection
      const micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      // Create audio context for mic analysis
      const micAudioContext = new AudioContext();
      const micSource = micAudioContext.createMediaStreamSource(micStream);
      const micAnalyser = micAudioContext.createAnalyser();
      micSource.connect(micAnalyser);
      this.micAnalyser = micAnalyser;
      
      // Add mic track to peer connection
      micStream.getTracks().forEach((track) => this.peerConnection!.addTrack(track, micStream));
      
      // 4.5. Create data channel for sending instructions
      this.dataChannel = this.peerConnection.createDataChannel("oai-events");
      console.log("Data channel created:", this.dataChannel);
      
      // Set up data channel event listeners
      this.dataChannel.addEventListener("open", () => {
        console.log("Data channel opened - ready to send instructions");
      });
      
      // Add summary detection and auto-close logic
      let autoClosed = false; // Guard to prevent double-closing
      // Set up data channel event listeners
      this.dataChannel.addEventListener("message", (e) => {
        // Only collect transcript for these two event types
        try {
          const event = JSON.parse(e.data);
          // User speech event
          if (event.type === "conversation.item.input_audio_transcription.completed" && event.transcript) {
            this.conversationHistory.push({
              speaker: 'user',
              message: event.transcript
            });
            console.log('User transcript captured:', event.transcript);
          }
          // Assistant speech event
          if (event.type === "response.audio_transcript.done" && event.transcript) {
            this.conversationHistory.push({
              speaker: 'assistant',
              message: event.transcript
            });
            console.log('Assistant transcript captured:', event.transcript);
            // Summary detection: auto-close if summary is detected
            if (!autoClosed && isFinalSummary(event.transcript)) {
              autoClosed = true;
              console.log('Final summary detected, auto-closing widget.');
              this.handleCloseWidget();
            }
          }
          // Ignore all other event types for transcript
        } catch (err) {
          console.warn('Failed to parse data channel message:', e.data, err);
        }
      });
      // Helper function for summary detection
      function isFinalSummary(message: string): boolean {
        // Adjust this logic as needed for your summary phrasing
        return (
          message.includes("I've got everything I need") &&
          message.includes("you're all set")
        );
      }
      
      this.dataChannel.addEventListener("error", (error) => {
        console.error("Data channel error:", error);
      });
      
      this.dataChannel.addEventListener("close", () => {
        console.log("Data channel closed");
      });
      
      // 5. Create SDP offer and send to OpenAI
      const offer = await this.peerConnection.createOffer();
      await this.peerConnection.setLocalDescription(offer);
      
      // 6. Send offer to OpenAI Realtime API
      const baseUrl = "https://api.openai.com/v1/realtime";
      const model = "gpt-4o-mini-realtime-preview-2024-12-17";
      const sdpResponse = await fetch(`${baseUrl}?model=${model}`, {
        method: "POST",
        body: offer.sdp,
        headers: {
          Authorization: `Bearer ${tokenData.client_secret.value}`,
          "Content-Type": "application/sdp",
        },
      });
      
      if (!sdpResponse.ok) {
        throw new Error(`OpenAI API error: ${sdpResponse.status}`);
      }
      
      // 7. Set remote SDP answer
      const answer = {
        type: "answer" as const,
        sdp: await sdpResponse.text(),
      };
      await this.peerConnection.setRemoteDescription(answer);
      
      this.streamingActive = true;
      this.sessionStartTime = new Date().toISOString();
      this.sessionId = crypto.randomUUID();
      this.conversationHistory = []; // Reset conversation history
      this.updateStatus('WebRTC streaming active - connected to OpenAI');
      
      // Fallback: Send instructions after a delay if session.created event doesn't come
      setTimeout(() => {
        if (!this.sessionCreated && this.dataChannel?.readyState === 'open') {
          console.log('Fallback: Sending instructions after timeout');
          this.sessionCreated = true;
          this.sendSessionUpdate();
        }
      }, 3000);
      
      // Trigger re-render to update visualizer with new analysers
      this.requestUpdate();
      
    } catch (err) {
      console.error('WebRTC streaming error:', err);
      this.updateError(`Streaming failed: ${err instanceof Error ? err.message : String(err)}`);
      this.stopStreaming();
    }
  }

  /**
   * Process conversation events and capture messages for transcript
   */
  private processConversationEvent(event: any) {
    // Handle user messages (when user speaks)
    if (event.type === "conversation.item.create" && event.item?.content) {
      const userMessage = event.item.content[0]?.text;
      if (userMessage) {
        this.conversationHistory.push({
          speaker: 'user',
          message: userMessage
        });
        console.log('User message captured:', userMessage);
        
        // Update backend session with user message
        this.updateBackendSession({
          speaker: 'user',
          message: userMessage
        });
      }
    }
    
    // Handle assistant responses (when AI speaks)
    if (event.type === "response.done" && event.response?.output) {
      // Look for text output in the response
      const textOutput = event.response.output.find((output: any) => output.type === "text");
      if (textOutput?.text) {
        this.conversationHistory.push({
          speaker: 'assistant',
          message: textOutput.text
        });
        console.log('Assistant message captured:', textOutput.text);
        
        // Update backend session with assistant message
        this.updateBackendSession({
          speaker: 'assistant',
          message: textOutput.text
        });
        
        // Check for completion
        this.checkForCompletion(textOutput.text);
      }
    }
    
    // Handle response creation events (when AI starts responding)
    if (event.type === "response.create") {
      console.log('AI starting to respond...');
    }
    
    // Handle response delta events (streaming responses)
    if (event.type === "response.delta" && event.delta?.output) {
      const textDelta = event.delta.output.find((output: any) => output.type === "text");
      if (textDelta?.text) {
        console.log('AI response delta:', textDelta.text);
      }
    }
  }

  /**
   * Check for completion keywords in AI response
   */
  private checkForCompletion(aiMessage: string): void {
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
    const isComplete = completionKeywords.some(keyword => lowerMessage.includes(keyword));
    
    if (isComplete && !this.isCompletionDetected) {
      console.log('Completion detected! Triggering automated widget close...');
      this.isCompletionDetected = true;
      
      // Set a small delay to allow the AI to finish speaking
      this.sessionCompletionTimeout = window.setTimeout(() => {
        this.handleAutomatedCompletion();
      }, 2000); // 2 second delay
    }
  }

  /**
   * Handle automated completion - extract resume and close widget
   */
  private async handleAutomatedCompletion(): Promise<void> {
    console.log('Handling automated completion...');
    
    if (this.sessionCompletionTimeout) {
      clearTimeout(this.sessionCompletionTimeout);
      this.sessionCompletionTimeout = null;
    }
    
    // Stop streaming first
    this.stopStreaming();
    
    // Navigate to resume page with conversation data for extraction
    if (this.conversationHistory.length > 0) {
      const sessionId = this.backendSessionId || crypto.randomUUID();
      const conversationParam = encodeURIComponent(JSON.stringify(this.conversationHistory));
      
      console.log('Navigating to resume page with conversation data for extraction');
      window.location.href = `#resume?sessionId=${sessionId}&conversation=${conversationParam}`;
      
      // Close the widget after navigation
      this.dispatchEvent(new CustomEvent('close-widget', { bubbles: true, composed: true }));
    } else {
      console.log('No conversation to extract, closing widget...');
      this.dispatchEvent(new CustomEvent('close-widget', { bubbles: true, composed: true }));
    }
  }

  /**
   * Update backend session with conversation entry
   */
  private async updateBackendSession(conversationEntry: { speaker: 'user' | 'assistant'; message: string }): Promise<void> {
    if (!this.backendSessionId) {
      // Create new backend session if not exists
      try {
        const sessionResponse = await fetch('http://localhost:8081/session/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        });
        
        if (sessionResponse.ok) {
          const sessionData = await sessionResponse.json();
          this.backendSessionId = sessionData.sessionId;
          console.log('Backend session created:', this.backendSessionId);
        }
      } catch (err) {
        console.warn('Failed to create backend session:', err);
        return;
      }
    }
    
    // Update session with conversation entry
    try {
      const updateResponse = await fetch(`http://localhost:8081/session/${this.backendSessionId}/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ conversationEntry })
      });
      
      if (updateResponse.ok) {
        const result = await updateResponse.json();
        if (result.isComplete) {
          console.log('Backend detected completion, triggering automated close...');
          this.checkForCompletion(conversationEntry.message);
        }
      }
    } catch (err) {
      console.warn('Failed to update backend session:', err);
    }
  }

  /**
   * Generate and download transcript
   */
  private downloadTranscript() {
    if (this.conversationHistory.length === 0) {
      console.log('No conversation history to download');
      return;
    }
    
    const endTime = new Date().toISOString();
    const duration = this.sessionStartTime 
      ? Math.round((new Date(endTime).getTime() - new Date(this.sessionStartTime).getTime()) / 1000)
      : 0;
    
    const transcript = {
      conversation: this.conversationHistory,
      sessionId: this.sessionId,
      startTime: this.sessionStartTime,
      endTime: endTime,
      metadata: {
        model: "gpt-4o-mini-realtime-preview-2024-12-17",
        voice: "alloy",
        duration: duration,
        messageCount: this.conversationHistory.length
      }
    };
    
    // Generate filename with timestamp
    const now = new Date();
    const timestamp = now.toISOString().replace(/[:.]/g, '-').split('T')[0] + '-' + 
                     now.getHours().toString().padStart(2, '0') + '-' +
                     now.getMinutes().toString().padStart(2, '0') + '-' +
                     now.getSeconds().toString().padStart(2, '0');
    const filename = `resume-transcript-${timestamp}.json`;
    
    // Download file
    const blob = new Blob([JSON.stringify(transcript, null, 2)], {
      type: 'application/json'
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    console.log('Transcript downloaded:', filename);
    console.log('Conversation length:', this.conversationHistory.length);
  }

  /**
   * Send custom session instructions via data channel
   */
  private sendSessionUpdate() {
    console.log("sendSessionUpdate called - data channel state:", this.dataChannel?.readyState);
    
    if (!this.dataChannel || this.dataChannel.readyState !== 'open') {
      console.warn('Data channel not ready for session update. State:', this.dataChannel?.readyState);
      return;
    }
    
    const sessionUpdate = {
      type: "session.update",
      session: {
        instructions: `You are a friendly, voice-first resume-building assistant. 
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
  → If yes, ask for which countries

**2) Career & Compensation**
- Key skills + Industry/Department
- Role category vs actual role
- Open to: job types (full-time/part-time/contract) + shift + preferred locations
- Notice period + Salary expectation

**3) Work Experience **
- For each job: Company, role, start/end dates, responsibilities, tools/skills
- Ask after each job: Got another job to add?
- Loop this until user says no more.

**4) Education **
- For each degree: Degree name, college, specialization, mode (full-time/distance), year
- Ask after each degree: Got another one?
- Loop this until user says no more.

**5) Projects **
- For each: Title, during job or college, client (if any), duration, what was built/done
- Ask after each project: Any more?
- Loop this until user says no more.

**6) Certifications **
- For each: Title, issuer, valid period, link
- Ask after each certification: Any more?
- Loop this until user says no more.

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
Looks like you're all set!"

Let it feel warm and encouraging — like you're proud of them. 🎉`
      }
    };
    
    console.log('Sending session update with custom instructions:', sessionUpdate);
    try {
      this.dataChannel.send(JSON.stringify(sessionUpdate));
      console.log('Session update sent successfully');
    } catch (error) {
      console.error('Error sending session update:', error);
    }
  }

  /**
   * Stop real-time audio streaming (WebRTC)
   */
  public stopStreaming() {
    if (!this.streamingActive) return;
    
    try {
      if (this.dataChannel) {
        this.dataChannel.close();
        this.dataChannel = null;
      }
      this.sessionCreated = false;
      this.sessionStartTime = null;
      this.sessionId = null;
      
      if (this.peerConnection) {
        this.peerConnection.getSenders().forEach((sender) => sender.track && sender.track.stop());
        this.peerConnection.close();
        this.peerConnection = null;
      }
      if (this.remoteAudioElement) {
        this.remoteAudioElement.srcObject = null;
        this.remoteAudioElement = null;
      }
      if (this.remoteAnalyser) {
        this.remoteAnalyser.disconnect();
        this.remoteAnalyser = null;
      }
      if (this.micAnalyser) {
        this.micAnalyser.disconnect();
        this.micAnalyser = null;
      }
      
      this.streamingActive = false;
      this.updateStatus('WebRTC streaming stopped.');
      
      // Trigger re-render to update visualizer
      this.requestUpdate();
      
    } catch (err) {
      console.error('Error stopping streaming:', err);
    }
  }

  render() {
    const commonDisabled = this.isRecording;
    const hasAnalysers = this.streamingActive 
      ? (this.micAnalyser && this.remoteAnalyser)
      : (this.wavRecorder.analyser && this.wavStreamPlayer.analyser);
    return html`
      <div style="position: relative; width: 100%; height: 100%;">
        ${this.error ? html`
          <div style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 1000; background: rgba(0,0,0,0.95); color: #ff6b6b; display: flex; flex-direction: column; align-items: center; justify-content: center; font-size: 1.2em;">
            <div style="margin-bottom: 1em;">${this.error}</div>
            <button style="padding: 0.5em 2em; font-size: 1em; border-radius: 6px; border: none; background: #fff; color: #222; cursor: pointer;" @click=${() => { this.error = ''; }}>Close</button>
          </div>
        ` : null}
        ${hasAnalysers ? html`
          <gdm-live-audio-visuals-3d
            .inputNode=${this.streamingActive ? this.micAnalyser : this.wavRecorder.analyser}
            .outputNode=${this.streamingActive ? this.remoteAnalyser : this.wavStreamPlayer.analyser}
            style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 1;"
          ></gdm-live-audio-visuals-3d>
        ` : html`
          <div style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 1; display: flex; align-items: center; justify-content: center; color: white; font-size: 14px;">
            ${this.streamingActive ? 'Initializing WebRTC visualizer...' : 'Initializing audio visualizer...'}
          </div>
        `}
        <div class="controls">
          <button class="icon-button" @click=${this.handleCloseWidget} title="Close Widget">
            X
          </button>
        </div>
      </div>
    `;
  }

  private async handleCloseWidget() {
    console.log('Close widget button clicked');
    
    // Clear any pending automated completion
    if (this.sessionCompletionTimeout) {
      clearTimeout(this.sessionCompletionTimeout);
      this.sessionCompletionTimeout = null;
    }
    
    // Stop streaming and cleanup
    this.stopStreaming();
    
    // Navigate to resume page with conversation data for extraction
    if (this.conversationHistory.length > 0) {
      const sessionId = this.backendSessionId || crypto.randomUUID();
      const conversationParam = encodeURIComponent(JSON.stringify(this.conversationHistory));
      
      console.log('Manual navigation to resume page with conversation data for extraction');
      window.location.href = `#resume?sessionId=${sessionId}&conversation=${conversationParam}`;
      
      // Close the widget after navigation
      this.dispatchEvent(new CustomEvent('close-widget', { bubbles: true, composed: true }));
    } else {
      console.log('No conversation to extract resume from');
      // Close widget even if no conversation
      this.dispatchEvent(new CustomEvent('close-widget', { bubbles: true, composed: true }));
    }
  }

  async connectedCallback() {
    super.connectedCallback();
    console.log('GdmLiveAudio connectedCallback called');
    await this.wavStreamPlayer.connect();
    console.log('WavStreamPlayer connected.');
  }

  disconnectedCallback() {
    // No direct OpenAI disconnect needed
    super.disconnectedCallback();
  }

  private updateStatus(msg: string) {
    this.status = msg;
    console.log("Status:", msg);
  }

  private updateError(msg: string) {
    if (this.errorTimeoutId) {
      clearTimeout(this.errorTimeoutId);
      this.errorTimeoutId = null;
    }
    this.error = msg;
    if (msg) {
      console.error("Error:", msg);
      this.errorTimeoutId = window.setTimeout(() => {
        if (this.error === msg) {
          this.error = '';
        }
        this.errorTimeoutId = null;
      }, 10000);
    }
  }
}