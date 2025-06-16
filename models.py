from datetime import datetime
from app import db
from flask_dance.consumer.storage.sqla import OAuthConsumerMixin
from flask_login import UserMixin
from sqlalchemy import UniqueConstraint
from enum import Enum

# User roles enum
class UserRole(Enum):
    ADMIN = "admin"
    ANNOTATOR = "annotator"
    REVIEWER = "reviewer"

# (IMPORTANT) This table is mandatory for Replit Auth, don't drop it.
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.String, primary_key=True)
    email = db.Column(db.String, unique=True, nullable=True)
    first_name = db.Column(db.String, nullable=True)
    last_name = db.Column(db.String, nullable=True)
    profile_image_url = db.Column(db.String, nullable=True)
    role = db.Column(db.Enum(UserRole), default=UserRole.ANNOTATOR, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    projects = db.relationship('Project', backref='owner', lazy=True)
    annotations = db.relationship('Annotation', backref='annotator', lazy=True)
    project_assignments = db.relationship('ProjectAssignment', backref='user', lazy=True)

    @property
    def display_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        return self.email or self.id

    def has_role(self, role):
        return self.role == role

    def can_access_project(self, project):
        if self.role == UserRole.ADMIN:
            return True
        if project.owner_id == self.id:
            return True
        return any(assignment.project_id == project.id for assignment in self.project_assignments)

# (IMPORTANT) This table is mandatory for Replit Auth, don't drop it.
class OAuth(OAuthConsumerMixin, db.Model):
    user_id = db.Column(db.String, db.ForeignKey(User.id))
    browser_session_key = db.Column(db.String, nullable=False)
    user = db.relationship(User)
    
    __table_args__ = (UniqueConstraint(
        'user_id',
        'browser_session_key',
        'provider',
        name='uq_user_browser_session_key_provider',
    ),)

class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    owner_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    images = db.relationship('Image', backref='project', lazy=True, cascade='all, delete-orphan')
    labels = db.relationship('Label', backref='project', lazy=True, cascade='all, delete-orphan')
    assignments = db.relationship('ProjectAssignment', backref='project', lazy=True, cascade='all, delete-orphan')

    @property
    def total_images(self):
        return len(self.images)

    @property
    def annotated_images(self):
        return len([img for img in self.images if img.annotations])

    @property
    def progress_percentage(self):
        if self.total_images == 0:
            return 0
        return round((self.annotated_images / self.total_images) * 100, 1)

class ProjectAssignment(db.Model):
    __tablename__ = 'project_assignments'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    assigned_at = db.Column(db.DateTime, default=datetime.now)
    
    __table_args__ = (UniqueConstraint('project_id', 'user_id', name='uq_project_user'),)

class Label(db.Model):
    __tablename__ = 'labels'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    color = db.Column(db.String(7), nullable=False)  # Hex color code
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # Relationships
    annotations = db.relationship('Annotation', backref='label', lazy=True)
    
    __table_args__ = (UniqueConstraint('name', 'project_id', name='uq_label_project'),)

class Image(db.Model):
    __tablename__ = 'images'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    filepath = db.Column(db.String(500), nullable=False)
    width = db.Column(db.Integer, nullable=False)
    height = db.Column(db.Integer, nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    uploaded_by = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # Relationships
    annotations = db.relationship('Annotation', backref='image', lazy=True, cascade='all, delete-orphan')
    uploader = db.relationship('User', foreign_keys=[uploaded_by])

    @property
    def is_annotated(self):
        return len(self.annotations) > 0

class Annotation(db.Model):
    __tablename__ = 'annotations'
    id = db.Column(db.Integer, primary_key=True)
    image_id = db.Column(db.Integer, db.ForeignKey('images.id'), nullable=False)
    label_id = db.Column(db.Integer, db.ForeignKey('labels.id'), nullable=False)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    
    # Bounding box coordinates
    x = db.Column(db.Float, nullable=False)
    y = db.Column(db.Float, nullable=False)
    width = db.Column(db.Float, nullable=False)
    height = db.Column(db.Float, nullable=False)
    
    # Optional fields
    confidence = db.Column(db.Float, default=1.0)
    notes = db.Column(db.Text)
    is_verified = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    @property
    def bbox_dict(self):
        return {
            'x': self.x,
            'y': self.y,
            'width': self.width,
            'height': self.height
        }
