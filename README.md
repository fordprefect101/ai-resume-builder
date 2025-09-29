# AI Resume Builder

A modern, AI-powered resume builder built with React, TypeScript, and Node.js. Create professional resumes with multiple templates, real-time AI assistance, and seamless PDF export capabilities.

## 🚀 Features

### Core Functionality
- **Multiple Resume Templates**: Modern, Classic, and General templates
- **Real-time AI Assistance**: AI-powered form completion and suggestions
- **Live Preview**: See your resume update in real-time as you type
- **PDF Export**: Print or download your resume as a PDF
- **Responsive Design**: Works perfectly on desktop, tablet, and mobile devices

### AI-Powered Features
- **Smart Form Completion**: AI analyzes your input and suggests improvements
- **Content Enhancement**: Get AI suggestions for better resume content
- **Audio Processing**: Voice-to-text capabilities for hands-free input
- **Real-time Collaboration**: Live updates and suggestions

### Technical Features
- **Modern Tech Stack**: React 18, TypeScript, Vite, Node.js
- **Real-time Communication**: WebSocket integration for live updates
- **Audio Processing**: Advanced audio analysis and processing
- **3D Visualizations**: Interactive 3D components using Three.js
- **Widget System**: Embeddable resume builder widgets

## 🛠️ Tech Stack

### Frontend
- **React 18** with TypeScript
- **Vite** for fast development and building
- **Tailwind CSS** for styling
- **Three.js** for 3D visualizations
- **Socket.io** for real-time communication

### Backend
- **Node.js** with Express
- **Socket.io** for WebSocket connections
- **OpenAI API** for AI features
- **CORS** enabled for cross-origin requests

### AI & Audio
- **Google Generative AI** for content generation
- **OpenAI Realtime API** for voice processing
- **Whisper** for speech-to-text
- **Custom audio processing** with Web Audio API

## 📁 Project Structure

```
├── src/
│   ├── react/                 # Main React application
│   │   ├── components/        # React components
│   │   │   ├── form/         # Form components
│   │   │   └── templates/   # Resume templates
│   │   ├── context/          # React context providers
│   │   ├── services/         # API services
│   │   └── utils/            # Utility functions
│   ├── components/           # Shared components
│   ├── shaders/              # WebGL shaders
│   ├── wavtools/            # Audio processing tools
│   └── types/               # TypeScript type definitions
├── backend/                  # Node.js backend server
├── public/                   # Static assets
└── dist/                     # Built files
```

## 🚀 Getting Started

### Prerequisites
- Node.js (v18 or higher)
- npm or yarn
- OpenAI API key (for AI features)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/fordprefect101/ai-resume-builder.git
   cd ai-resume-builder
   ```

2. **Install dependencies**
   ```bash
   # Install frontend dependencies
   npm install
   
   # Install backend dependencies
   cd backend
   npm install
   cd ..
   ```

3. **Set up environment variables**
   ```bash
   # Create .env file in the root directory
   touch .env
   ```
   
   Add the following to your `.env` file:
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   PORT=8081
   ```

4. **Start the development servers**
   ```bash
   # Start the backend server (in one terminal)
   cd backend
   npm start
   
   # Start the frontend development server (in another terminal)
   npm run dev
   ```

5. **Open your browser**
   Navigate to `http://localhost:4173` to see the application.

## 📖 Usage

### Creating a Resume

1. **Fill out the form** with your personal information, work experience, education, and skills
2. **Use AI assistance** to get suggestions and auto-complete fields
3. **Choose a template** from Modern, Classic, or General options
4. **Customize the theme** with different color schemes
5. **Preview your resume** in real-time
6. **Export as PDF** when you're satisfied

### AI Features

- **Smart Suggestions**: AI analyzes your input and suggests improvements
- **Auto-completion**: Let AI help fill in missing information
- **Content Enhancement**: Get suggestions for better wording and formatting
- **Voice Input**: Use voice-to-text for hands-free input

## 🎨 Templates

### Modern Template
- Clean, contemporary design
- Focus on typography and white space
- Perfect for tech and creative professionals

### Classic Template
- Traditional, professional layout
- Conservative design elements
- Ideal for corporate and business roles

### General Template
- Versatile design that works for any industry
- Balanced layout with clear sections
- Suitable for all career levels

## 🔧 Development

### Available Scripts

```bash
# Frontend development
npm run dev          # Start development server
npm run build        # Build for production
npm run preview      # Preview production build

# Backend development
cd backend
npm start           # Start backend server
```

### Building for Production

```bash
# Build the frontend
npm run build

# The built files will be in the dist/ directory
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- OpenAI for the powerful AI APIs
- Google for Generative AI capabilities
- The React and TypeScript communities
- Three.js for 3D graphics capabilities

## 📞 Support

If you have any questions or need help, please:
- Open an issue on GitHub
- Check the documentation
- Contact the development team

---

**Built with ❤️ using React, TypeScript, and AI**
