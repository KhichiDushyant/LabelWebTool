import os
import json
from flask import render_template, request, redirect, url_for, flash, jsonify, send_file, session
from flask_login import current_user
from werkzeug.utils import secure_filename
from sqlalchemy import desc

from app import app, db
from models import User, Project, Image, Annotation, Label, ProjectAssignment, UserRole
from replit_auth import require_login, require_role, make_replit_blueprint
from utils import save_uploaded_image, generate_pascal_voc_xml, generate_yolo_format, get_default_label_colors

# Register auth blueprint
app.register_blueprint(make_replit_blueprint(), url_prefix="/auth")

# Make session permanent
@app.before_request
def make_session_permanent():
    session.permanent = True

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/dashboard')
@require_login
def dashboard():
    # Get user's projects
    if current_user.role == UserRole.ADMIN:
        projects = Project.query.filter_by(is_active=True).all()
    else:
        owned_projects = Project.query.filter_by(owner_id=current_user.id, is_active=True).all()
        assigned_projects = [assignment.project for assignment in current_user.project_assignments 
                           if assignment.project.is_active]
        projects = list(set(owned_projects + assigned_projects))
    
    # Get recent annotations
    recent_annotations = Annotation.query.filter_by(user_id=current_user.id)\
                                        .order_by(desc(Annotation.created_at))\
                                        .limit(5).all()
    
    # Calculate statistics
    total_annotations = Annotation.query.filter_by(user_id=current_user.id).count()
    total_images_annotated = len(set([ann.image_id for ann in 
                                    Annotation.query.filter_by(user_id=current_user.id).all()]))
    
    return render_template('dashboard.html', 
                         projects=projects,
                         recent_annotations=recent_annotations,
                         total_annotations=total_annotations,
                         total_images_annotated=total_images_annotated)

@app.route('/projects')
@require_login
def projects():
    if current_user.role == UserRole.ADMIN:
        projects = Project.query.filter_by(is_active=True).all()
    else:
        owned_projects = Project.query.filter_by(owner_id=current_user.id, is_active=True).all()
        assigned_projects = [assignment.project for assignment in current_user.project_assignments 
                           if assignment.project.is_active]
        projects = list(set(owned_projects + assigned_projects))
    
    return render_template('projects.html', projects=projects)

@app.route('/projects/new', methods=['GET', 'POST'])
@require_login
def new_project():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description', '')
        
        if not name:
            flash('Project name is required', 'error')
            return render_template('project_form.html')
        
        project = Project(
            name=name,
            description=description,
            owner_id=current_user.id
        )
        db.session.add(project)
        db.session.commit()
        
        # Create default labels
        default_labels = [
            ('person', '#FF6B6B'),
            ('car', '#4ECDC4'),
            ('bicycle', '#45B7D1'),
            ('dog', '#96CEB4'),
            ('cat', '#FFEAA7')
        ]
        
        for label_name, color in default_labels:
            label = Label(name=label_name, color=color, project_id=project.id)
            db.session.add(label)
        
        db.session.commit()
        flash('Project created successfully!', 'success')
        return redirect(url_for('project_detail', project_id=project.id))
    
    return render_template('project_form.html')

@app.route('/projects/<int:project_id>')
@require_login
def project_detail(project_id):
    project = Project.query.get_or_404(project_id)
    
    if not current_user.can_access_project(project):
        return render_template('403.html'), 403
    
    images = Image.query.filter_by(project_id=project_id).all()
    labels = Label.query.filter_by(project_id=project_id).all()
    
    return render_template('project_detail.html', 
                         project=project, 
                         images=images, 
                         labels=labels)

@app.route('/projects/<int:project_id>/upload', methods=['POST'])
@require_login
def upload_images(project_id):
    project = Project.query.get_or_404(project_id)
    
    if not current_user.can_access_project(project):
        return jsonify({'error': 'Access denied'}), 403
    
    if 'files' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400
    
    files = request.files.getlist('files')
    uploaded_count = 0
    
    for file in files:
        if file.filename == '':
            continue
            
        image_info = save_uploaded_image(file, project_id)
        if image_info:
            image = Image(
                filename=image_info['filename'],
                original_filename=image_info['original_filename'],
                filepath=image_info['filepath'],
                width=image_info['width'],
                height=image_info['height'],
                file_size=image_info['file_size'],
                project_id=project_id,
                uploaded_by=current_user.id
            )
            db.session.add(image)
            uploaded_count += 1
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'uploaded_count': uploaded_count,
        'message': f'{uploaded_count} images uploaded successfully'
    })

@app.route('/projects/<int:project_id>/images/<int:image_id>')
@require_login
def serve_image(project_id, image_id):
    project = Project.query.get_or_404(project_id)
    image = Image.query.get_or_404(image_id)
    
    if not current_user.can_access_project(project) or image.project_id != project_id:
        return render_template('403.html'), 403
    
    return send_file(image.filepath)

@app.route('/annotate/<int:image_id>')
@require_login
def annotate_image(image_id):
    image = Image.query.get_or_404(image_id)
    
    if not current_user.can_access_project(image.project):
        return render_template('403.html'), 403
    
    annotations = Annotation.query.filter_by(image_id=image_id).all()
    labels = Label.query.filter_by(project_id=image.project_id).all()
    
    # Get next and previous images in the project
    all_images = Image.query.filter_by(project_id=image.project_id)\
                           .order_by(Image.id).all()
    
    current_index = next((i for i, img in enumerate(all_images) if img.id == image_id), 0)
    prev_image = all_images[current_index - 1] if current_index > 0 else None
    next_image = all_images[current_index + 1] if current_index < len(all_images) - 1 else None
    
    return render_template('annotate.html',
                         image=image,
                         annotations=annotations,
                         labels=labels,
                         prev_image=prev_image,
                         next_image=next_image)

@app.route('/api/annotations', methods=['POST'])
@require_login
def create_annotation():
    data = request.get_json()
    
    image = Image.query.get_or_404(data['image_id'])
    if not current_user.can_access_project(image.project):
        return jsonify({'error': 'Access denied'}), 403
    
    annotation = Annotation(
        image_id=data['image_id'],
        label_id=data['label_id'],
        user_id=current_user.id,
        x=data['x'],
        y=data['y'],
        width=data['width'],
        height=data['height']
    )
    
    db.session.add(annotation)
    db.session.commit()
    
    return jsonify({
        'id': annotation.id,
        'message': 'Annotation created successfully'
    })

@app.route('/api/annotations/<int:annotation_id>', methods=['PUT'])
@require_login
def update_annotation(annotation_id):
    annotation = Annotation.query.get_or_404(annotation_id)
    
    if not current_user.can_access_project(annotation.image.project):
        return jsonify({'error': 'Access denied'}), 403
    
    data = request.get_json()
    annotation.x = data['x']
    annotation.y = data['y']
    annotation.width = data['width']
    annotation.height = data['height']
    annotation.label_id = data['label_id']
    
    db.session.commit()
    
    return jsonify({'message': 'Annotation updated successfully'})

@app.route('/api/annotations/<int:annotation_id>', methods=['DELETE'])
@require_login
def delete_annotation(annotation_id):
    annotation = Annotation.query.get_or_404(annotation_id)
    
    if not current_user.can_access_project(annotation.image.project):
        return jsonify({'error': 'Access denied'}), 403
    
    db.session.delete(annotation)
    db.session.commit()
    
    return jsonify({'message': 'Annotation deleted successfully'})

@app.route('/projects/<int:project_id>/labels', methods=['POST'])
@require_login
def create_label(project_id):
    project = Project.query.get_or_404(project_id)
    
    if not current_user.can_access_project(project):
        return jsonify({'error': 'Access denied'}), 403
    
    data = request.get_json()
    
    # Check if label name already exists in project
    existing_label = Label.query.filter_by(name=data['name'], project_id=project_id).first()
    if existing_label:
        return jsonify({'error': 'Label name already exists'}), 400
    
    label = Label(
        name=data['name'],
        color=data['color'],
        project_id=project_id
    )
    
    db.session.add(label)
    db.session.commit()
    
    return jsonify({
        'id': label.id,
        'name': label.name,
        'color': label.color,
        'message': 'Label created successfully'
    })

@app.route('/projects/<int:project_id>/export/<format>')
@require_login
def export_annotations(project_id, format):
    project = Project.query.get_or_404(project_id)
    
    if not current_user.can_access_project(project):
        return render_template('403.html'), 403
    
    if format not in ['pascal_voc', 'yolo']:
        return jsonify({'error': 'Invalid export format'}), 400
    
    images = Image.query.filter_by(project_id=project_id).all()
    export_data = {}
    
    for image in images:
        annotations = Annotation.query.filter_by(image_id=image.id).all()
        if annotations:
            if format == 'pascal_voc':
                export_data[image.original_filename] = generate_pascal_voc_xml(image, annotations)
            elif format == 'yolo':
                export_data[image.original_filename] = generate_yolo_format(image, annotations)
    
    return jsonify(export_data)

@app.route('/admin')
@require_role(UserRole.ADMIN)
def admin_panel():
    users = User.query.all()
    projects = Project.query.all()
    total_annotations = Annotation.query.count()
    total_images = Image.query.count()
    
    return render_template('admin.html',
                         users=users,
                         projects=projects,
                         total_annotations=total_annotations,
                         total_images=total_images)

@app.route('/admin/users/<user_id>/role', methods=['POST'])
@require_role(UserRole.ADMIN)
def update_user_role(user_id):
    user = User.query.get_or_404(user_id)
    new_role = UserRole(request.form.get('role'))
    
    user.role = new_role
    db.session.commit()
    
    flash(f'User role updated to {new_role.value}', 'success')
    return redirect(url_for('admin_panel'))

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500
