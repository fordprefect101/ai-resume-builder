# Django Integration Implementation Plan (Hybrid Approach)

## Overview
**Keep the existing Node.js backend** for voice conversation and AI extraction, and **add Django backend** for user authentication and resume storage. This creates a hybrid architecture where both backends work together.

## Architecture Overview

```
Frontend (Lit Components)
    ↓
Node.js Backend (server.js) - Voice/AI Processing
    ↓ (extracts resume data)
Django Backend - User Auth & Resume Storage
    ↓
SQLite Database
```

## Phase 1: Django Backend Setup (Parallel to Node.js)

### 1.1 Create Django Project Structure
```bash
# Create Django project in a separate directory
mkdir django_backend
cd django_backend
django-admin startproject resume_storage
cd resume_storage

# Create main app
python manage.py startapp resumes
python manage.py startapp accounts
```

### 1.2 Project Structure
```
Resume Builder copy/
├── backend/                    # Existing Node.js backend
│   ├── server.js              # Voice/AI processing
│   └── package.json
├── django_backend/            # New Django backend
│   ├── resume_storage/
│   │   ├── manage.py
│   │   ├── resume_storage/
│   │   │   ├── settings.py
│   │   │   ├── urls.py
│   │   │   └── wsgi.py
│   │   ├── resumes/
│   │   │   ├── models.py
│   │   │   ├── views.py
│   │   │   ├── serializers.py
│   │   │   └── urls.py
│   │   ├── accounts/
│   │   │   ├── models.py
│   │   │   ├── views.py
│   │   │   ├── serializers.py
│   │   │   └── urls.py
│   │   └── requirements.txt
└── src/                      # Existing frontend
    └── components/
```

### 1.3 Dependencies (django_backend/requirements.txt)
```
Django==4.2.7
djangorestframework==3.14.0
django-cors-headers==4.3.1
djangorestframework-simplejwt==5.3.0
Pillow==10.1.0
python-decouple==3.8
```

## Phase 2: Database Models

### 2.1 User Model (django_backend/accounts/models.py)
```python
from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
```

### 2.2 Resume Model (django_backend/resumes/models.py)
```python
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Resume(models.Model):
    TEMPLATE_CHOICES = [
        ('modern', 'Modern'),
        ('classic', 'Classic'),
        ('general', 'General'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='resumes')
    title = models.CharField(max_length=200, default='My Resume')
    template = models.CharField(max_length=20, choices=TEMPLATE_CHOICES, default='modern')
    theme_color = models.CharField(max_length=7, default='#3b82f6')
    
    # Resume data as JSON (from Node.js extraction)
    personal_details = models.JSONField(default=dict)
    career_details = models.JSONField(default=dict)
    employment = models.JSONField(default=list)
    education = models.JSONField(default=list)
    projects = models.JSONField(default=list)
    certifications = models.JSONField(default=list)
    languages = models.JSONField(default=list)
    online_profiles = models.JSONField(default=dict)
    references = models.JSONField(default=list)
    achievements = models.JSONField(default=list)
    publications = models.JSONField(default=list)
    hobbies = models.JSONField(default=list)
    trainings = models.JSONField(default=list)
    
    # Metadata
    is_public = models.BooleanField(default=False)
    public_url = models.CharField(max_length=255, blank=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.title}"
    
    def save(self, *args, **kwargs):
        if not self.public_url and self.is_public:
            import uuid
            self.public_url = f"resume-{uuid.uuid4().hex[:8]}"
        super().save(*args, **kwargs)
```

## Phase 3: API Views and Serializers

### 3.1 User Serializers (django_backend/accounts/serializers.py)
```python
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

User = get_user_model()

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ['email', 'username', 'password', 'password_confirm', 'first_name', 'last_name']
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(**validated_data)
        return user

class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()
```

### 3.2 Resume Serializers (django_backend/resumes/serializers.py)
```python
from rest_framework import serializers
from .models import Resume

class ResumeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resume
        fields = '__all__'
        read_only_fields = ['user', 'public_url', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

class ResumeListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resume
        fields = ['id', 'title', 'template', 'theme_color', 'is_public', 'public_url', 'updated_at']
```

### 3.3 User Views (django_backend/accounts/views.py)
```python
from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from .serializers import UserRegistrationSerializer, UserLoginSerializer

class RegisterView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = UserRegistrationSerializer

class LoginView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = UserLoginSerializer
    
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = authenticate(
            email=serializer.validated_data['email'],
            password=serializer.validated_data['password']
        )
        
        if user:
            refresh = RefreshToken.for_user(user)
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                }
            })
        else:
            return Response(
                {'error': 'Invalid credentials'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
```

### 3.4 Resume Views (django_backend/resumes/views.py)
```python
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from django.shortcuts import get_object_or_404
from .models import Resume
from .serializers import ResumeSerializer, ResumeListSerializer

class ResumeListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ResumeSerializer
    
    def get_queryset(self):
        return Resume.objects.filter(user=self.request.user)
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return ResumeListSerializer
        return ResumeSerializer

class ResumeDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ResumeSerializer
    
    def get_queryset(self):
        return Resume.objects.filter(user=self.request.user)

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def public_resume_view(request, public_url):
    resume = get_object_or_404(Resume, public_url=public_url, is_public=True)
    serializer = ResumeSerializer(resume)
    return Response(serializer.data)
```

## Phase 4: URL Configuration

### 4.1 Main URLs (django_backend/resume_storage/urls.py)
```python
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/accounts/', include('accounts.urls')),
    path('api/resumes/', include('resumes.urls')),
]
```

### 4.2 Account URLs (django_backend/accounts/urls.py)
```python
from django.urls import path
from .views import RegisterView, LoginView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
]
```

### 4.3 Resume URLs (django_backend/resumes/urls.py)
```python
from django.urls import path
from .views import ResumeListCreateView, ResumeDetailView, public_resume_view

urlpatterns = [
    path('', ResumeListCreateView.as_view(), name='resume-list-create'),
    path('<int:pk>/', ResumeDetailView.as_view(), name='resume-detail'),
    path('public/<str:public_url>/', public_resume_view, name='public-resume'),
]
```

## Phase 5: Frontend Integration

### 5.1 Update ResumePage.tsx
Add Django integration while keeping Node.js functionality:

```typescript
// Add authentication state
@state() private isAuthenticated = false;
@state() private user: any = null;
@state() private showAuthModal = false;

// Keep existing Node.js methods
private async extractResume(sessionId: string, conversation: any[]): Promise<void> {
  // Existing Node.js extraction logic
  const response = await fetch('/extract-resume', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sessionId, conversation })
  });
  
  if (response.ok) {
    const extractedData = await response.json();
    this.resumeData = extractedData;
    // Now save to Django backend if user is authenticated
    if (this.isAuthenticated) {
      await this.saveToDjango(extractedData);
    }
  }
}

// Add Django save method
private async saveToDjango(resumeData: any) {
  try {
    const token = localStorage.getItem('access_token');
    const response = await fetch('http://localhost:8000/api/resumes/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        title: 'My Resume',
        template: this.selectedTemplate,
        theme_color: '#3b82f6',
        personal_details: resumeData.personalDetails,
        career_details: resumeData.careerDetails,
        employment: resumeData.employment,
        education: resumeData.education,
        projects: resumeData.projects,
        certifications: resumeData.certifications,
        languages: resumeData.languages,
        online_profiles: resumeData.onlineProfiles,
        references: resumeData.references,
        achievements: resumeData.achievements,
        publications: resumeData.publications,
        hobbies: resumeData.hobbies,
        trainings: resumeData.trainings
      })
    });
    
    if (response.ok) {
      this.successMessage = 'Resume saved to your account!';
    }
  } catch (error) {
    console.error('Django save failed:', error);
  }
}

// Add authentication methods
private async login(email: string, password: string) {
  try {
    const response = await fetch('http://localhost:8000/api/accounts/login/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    
    if (response.ok) {
      const data = await response.json();
      localStorage.setItem('access_token', data.access);
      localStorage.setItem('refresh_token', data.refresh);
      this.user = data.user;
      this.isAuthenticated = true;
      this.showAuthModal = false;
      
      // If we have resume data, save it now
      if (this.resumeData) {
        await this.saveToDjango(this.resumeData);
      }
    }
  } catch (error) {
    console.error('Login failed:', error);
  }
}

// Update the save button to trigger auth
private async handleSaveClick() {
  if (!this.isAuthenticated) {
    this.showAuthModal = true;
    return;
  }
  
  await this.saveToDjango(this.resumeData);
}
```

### 5.2 Create Auth Modal Component
```typescript
@customElement('auth-modal')
export class AuthModal extends LitElement {
  @property({ type: Boolean }) show = false;
  @property({ type: String }) mode: 'login' | 'register' = 'login';
  @property({ type: Function }) onLogin = (email: string, password: string) => {};
  @property({ type: Function }) onRegister = (email: string, password: string) => {};
  
  render() {
    if (!this.show) return html``;
    
    return html`
      <div class="modal-overlay">
        <div class="modal-content">
          <h2>${this.mode === 'login' ? 'Login' : 'Register'} to Save Resume</h2>
          <p>Create an account to save your resume and access it later.</p>
          <form @submit="${this.handleSubmit}">
            <input type="email" placeholder="Email" required />
            <input type="password" placeholder="Password" required />
            ${this.mode === 'register' ? html`
              <input type="password" placeholder="Confirm Password" required />
            ` : ''}
            <button type="submit">${this.mode === 'login' ? 'Login' : 'Register'}</button>
          </form>
          <button @click="${this.toggleMode}">
            ${this.mode === 'login' ? 'Need an account? Register' : 'Have an account? Login'}
          </button>
        </div>
      </div>
    `;
  }
}
```

## Phase 6: Deployment Configuration

### 6.1 Django Settings (django_backend/resume_storage/settings.py)
```python
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key')

DEBUG = os.environ.get('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'your-domain.com']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'accounts',
    'resumes',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# CORS settings - allow Node.js backend
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8081",  # Node.js backend
]

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Custom user model
AUTH_USER_MODEL = 'accounts.User'

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}
```

## Phase 7: Running Both Backends

### 7.1 Development Setup
```bash
# Terminal 1: Run Node.js backend (existing)
cd "Resume Builder copy/backend"
npm start  # or node server.js

# Terminal 2: Run Django backend (new)
cd "Resume Builder copy/django_backend/resume_storage"
python manage.py runserver 8000

# Terminal 3: Run frontend
cd "Resume Builder copy"
npm run dev
```

### 7.2 Production Setup
```bash
# Node.js backend (port 8081)
cd backend && npm start

# Django backend (port 8000)
cd django_backend/resume_storage && python manage.py runserver 8000

# Frontend (port 5173)
npm run dev
```

## Phase 8: Data Flow Integration

### 8.1 Complete User Journey
1. **User starts voice conversation** → Node.js backend processes
2. **AI extracts resume data** → Node.js backend returns structured data
3. **User clicks "Save"** → Frontend checks authentication
4. **If not authenticated** → Shows login/register modal
5. **After authentication** → Saves to Django backend
6. **User can view/edit** → Loads from Django backend
7. **User can share** → Public URL from Django backend

### 8.2 API Endpoints Summary
```
Node.js Backend (Port 8081):
- POST /extract-resume - AI extraction
- GET /resume/:sessionId - Get extracted data
- POST /token - OpenAI session token

Django Backend (Port 8000):
- POST /api/accounts/register/ - User registration
- POST /api/accounts/login/ - User login
- GET /api/resumes/ - List user resumes
- POST /api/resumes/ - Save resume
- GET /api/resumes/public/:url/ - Public resume view
```

## Benefits of Hybrid Approach

1. **Preserves Voice Functionality**: Node.js backend handles AI/voice processing
2. **Adds User Management**: Django provides authentication and storage
3. **Scalable Architecture**: Each backend handles its specialty
4. **Easy Migration**: Can gradually move features between backends
5. **Best of Both Worlds**: Node.js for real-time, Django for data management

## Implementation Timeline

1. **Week 1**: Django project setup and models
2. **Week 2**: Django API endpoints
3. **Week 3**: Frontend integration with both backends
4. **Week 4**: Testing and deployment configuration 