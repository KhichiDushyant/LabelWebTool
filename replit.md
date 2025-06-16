# Image Annotation Tool

## Overview

This is a web-based image annotation platform built with Flask for creating high-quality training datasets. The application provides an intuitive interface for annotating images with bounding boxes, managing annotation projects, and exporting data in popular formats like PASCAL VOC and YOLO.

## System Architecture

**Frontend Architecture:**
- Modern HTML5 with Bootstrap 5 dark theme for responsive UI
- JavaScript canvas-based annotation interface for interactive drawing
- Font Awesome icons for consistent visual elements
- Mobile-responsive design with collapsible navigation

**Backend Architecture:**
- Flask web framework with SQLAlchemy ORM for database operations
- Modular structure with separate files for models, routes, utilities, and authentication
- RESTful API endpoints for annotation CRUD operations
- File upload handling with secure filename generation

**Authentication System:**
- Replit OAuth integration for seamless user authentication
- Flask-Login for session management
- Role-based access control (Admin, Annotator, Reviewer)
- Custom decorator functions for route protection

## Key Components

**Database Models:**
- User model with role-based permissions and profile information
- Project model for organizing annotation workflows
- Image model for storing uploaded files and metadata
- Annotation model for bounding box coordinates and labels
- Label model for category definitions with color coding
- ProjectAssignment model for user-project relationships

**Canvas Annotation System:**
- HTML5 Canvas-based drawing interface
- Real-time bounding box creation and editing
- Multi-label support with visual color coding
- Zoom and pan functionality for detailed work
- Keyboard shortcuts for efficient annotation

**File Management:**
- Secure file upload with extension validation
- Project-specific directory organization
- Image processing with PIL for metadata extraction
- Automatic thumbnail generation capabilities

## Data Flow

1. **User Authentication:** Users authenticate via Replit OAuth system
2. **Project Creation:** Authorized users create projects and upload images
3. **Image Processing:** Uploaded images are validated, processed, and stored in project directories
4. **Annotation Workflow:** Users select images and create bounding box annotations with labels
5. **Data Export:** Completed annotations are exported in PASCAL VOC or YOLO formats
6. **Team Collaboration:** Project assignments allow multiple users to work on the same dataset

## External Dependencies

**Core Framework:**
- Flask 3.1.1 for web application framework
- SQLAlchemy 2.0.41 for database ORM
- Flask-Login 0.6.3 for user session management

**Authentication:**
- Flask-Dance 7.1.0 for OAuth integration
- PyJWT 2.10.1 for token handling
- OAuthLib 3.2.2 for OAuth protocol support

**Database:**
- PostgreSQL with psycopg2-binary 2.9.10 driver
- Database tables created automatically on startup

**Image Processing:**
- Pillow 11.2.1 for image manipulation and metadata extraction
- Support for PNG, JPG, JPEG, GIF, BMP, TIFF, and WebP formats

**Frontend Libraries:**
- Bootstrap 5 with custom dark theme
- Font Awesome 6.4.0 for icons
- Custom JavaScript for canvas interactions

## Deployment Strategy

**Replit Configuration:**
- Python 3.11 runtime environment
- Nix package manager for system dependencies
- Autoscale deployment target for production
- Gunicorn WSGI server with automatic reloading

**Environment Variables:**
- SESSION_SECRET for Flask session encryption
- DATABASE_URL for PostgreSQL connection
- File uploads stored in project-specific directories

**Production Setup:**
- Gunicorn with multiple workers for concurrent request handling
- ProxyFix middleware for proper HTTPS URL generation
- Connection pooling for database efficiency
- Automatic database table creation on startup

## Changelog

- June 16, 2025. Initial setup

## User Preferences

Preferred communication style: Simple, everyday language.