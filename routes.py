import os
import json
from flask import render_template, request, redirect, url_for, flash, jsonify, send_file, session
from flask_login import current_user
from werkzeug.utils import secure_filename
from sqlalchemy import desc

from app import app, db
from models import User, Project, Image, Annotation, Label, ProjectAssignment, UserRole, ProjectType, VideoFrame, VideoAnnotation
from replit_auth import require_login, require_role, make_replit_blueprint
from utils import (save_uploaded_image, save_uploaded_video, extract_video_frames, 
                  batch_process_images, generate_pascal_voc_xml, generate_yolo_format, get_default_label_colors)

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
        project_type = ProjectType(request.form.get('project_type', 'image'))
        batch_size = int(request.form.get('batch_size', 50))
        
        if not name:
            flash('Project name is required', 'error')
            return render_template('project_form.html')
        
        project = Project(
            name=name,
            description=description,
            project_type=project_type,
            batch_size=batch_size,
            owner_id=current_user.id
        )
        db.session.add(project)
        db.session.commit()
        
        # Handle video upload if it's a video project
        if project_type == ProjectType.VIDEO and 'video_file' in request.files:
            video_file = request.files['video_file']
            frame_interval = int(request.form.get('frame_interval', 30))  # Extract every N frames
            
            if video_file.filename != '':
                app.config['CURRENT_USER_ID'] = current_user.id
                video_info = save_uploaded_video(video_file, project.id)
                if video_info:
                    # Update project with video information
                    project.video_filename = video_info['filename']
                    project.video_filepath = video_info['filepath']
                    project.video_duration = video_info['duration']
                    project.video_fps = video_info['fps']
                    project.total_frames = video_info['total_frames']
                    project.processing_status = 'processing'
                    db.session.commit()
                    
                    # Start frame extraction in background
                    try:
                        # For now, extract frames synchronously but improve UI feedback
                        extracted_frames = extract_video_frames(video_info['filepath'], project.id, frame_interval)
                        project.processing_status = 'completed'
                        db.session.commit()
                        flash(f'Video uploaded successfully! Extracted {len(extracted_frames)} frames for annotation.', 'success')
                    except Exception as e:
                        project.processing_status = 'failed'
                        db.session.commit()
                        flash(f'Error processing video: {str(e)}', 'error')
                else:
                    flash('Invalid video file format', 'error')
                    return render_template('project_form.html')
        
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
    
    if project.project_type == ProjectType.VIDEO:
        # Get video frames instead of images
        video_frames = VideoFrame.query.filter_by(project_id=project_id).all()
        labels = Label.query.filter_by(project_id=project_id).all()
        return render_template('project_detail.html', 
                             project=project, 
                             video_frames=video_frames,
                             labels=labels)
    else:
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
    
    if project.project_type == ProjectType.VIDEO:
        return jsonify({'error': 'Cannot upload images to video projects'}), 400
    
    if 'files' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400
    
    files = request.files.getlist('files')
    
    # Use batch processing for large datasets
    if len(files) > project.batch_size:
        project.processing_status = 'processing'
        db.session.commit()
        
        try:
            app.config['CURRENT_USER_ID'] = current_user.id
            processed_images = batch_process_images(files, project_id, project.batch_size)
            project.processing_status = 'completed'
            db.session.commit()
            
            return jsonify({
                'success': True,
                'uploaded_count': len(processed_images),
                'message': f'{len(processed_images)} images processed in batches',
                'batch_processed': True,
                'total_files': len(files),
                'processing_status': 'completed'
            })
        except Exception as e:
            project.processing_status = 'failed'
            db.session.commit()
            return jsonify({'error': f'Batch processing failed: {str(e)}'}), 500
    else:
        # Process normally for smaller datasets
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
            'message': f'{uploaded_count} images uploaded successfully',
            'batch_processed': False,
            'total_files': len(files),
            'processing_status': 'completed'
        })

@app.route('/projects/<int:project_id>/status')
@require_login
def project_status(project_id):
    project = Project.query.get_or_404(project_id)
    
    if not current_user.can_access_project(project):
        return jsonify({'error': 'Access denied'}), 403
    
    if project.project_type == ProjectType.VIDEO:
        total_frames = VideoFrame.query.filter_by(project_id=project_id).count()
        return jsonify({
            'processing_status': project.processing_status,
            'project_type': project.project_type.value,
            'total_frames': total_frames,
            'video_duration': project.video_duration,
            'video_fps': project.video_fps
        })
    else:
        total_images = Image.query.filter_by(project_id=project_id).count()
        annotated_images = len(set([ann.image_id for ann in 
                                  Annotation.query.join(Image).filter(Image.project_id == project_id).all()]))
        return jsonify({
            'processing_status': project.processing_status,
            'project_type': project.project_type.value,
            'total_images': total_images,
            'annotated_images': annotated_images,
            'progress_percentage': (annotated_images / total_images * 100) if total_images > 0 else 0
        })

@app.route('/projects/<int:project_id>/reextract-frames', methods=['POST'])
@require_login
def reextract_video_frames(project_id):
    project = Project.query.get_or_404(project_id)
    
    if not current_user.can_access_project(project):
        return jsonify({'error': 'Access denied'}), 403
    
    if project.project_type != ProjectType.VIDEO:
        return jsonify({'error': 'Only video projects support frame extraction'}), 400
    
    if not project.video_filepath:
        return jsonify({'error': 'No video file found'}), 400
    
    data = request.get_json()
    
    try:
        # Delete existing frames
        VideoFrame.query.filter_by(project_id=project_id).delete()
        db.session.commit()
        
        # Extract new frames
        project.processing_status = 'processing'
        db.session.commit()
        
        # Check if using FPS-based extraction or frame interval
        if 'target_fps' in data:
            target_fps = int(data.get('target_fps', 1))
            if target_fps == 0:  # Extract all frames
                extracted_frames = extract_video_frames_by_fps(project.video_filepath, project_id, None)
                message = f'Extracted all frames'
            else:
                extracted_frames = extract_video_frames_by_fps(project.video_filepath, project_id, target_fps)
                message = f'Extracted frames at {target_fps} FPS'
        else:
            frame_interval = int(data.get('frame_interval', 30))
            extracted_frames = extract_video_frames(project.video_filepath, project_id, frame_interval)
            message = f'Re-extracted {len(extracted_frames)} frames with interval {frame_interval}'
        
        project.processing_status = 'completed'
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': message,
            'total_frames': len(extracted_frames)
        })
    except Exception as e:
        project.processing_status = 'failed'
        db.session.commit()
        return jsonify({'error': f'Frame extraction failed: {str(e)}'}), 500

@app.route('/projects/<int:project_id>/images/<int:image_id>')
@require_login
def serve_image(project_id, image_id):
    project = Project.query.get_or_404(project_id)
    image = Image.query.get_or_404(image_id)
    
    if not current_user.can_access_project(project) or image.project_id != project_id:
        return render_template('403.html'), 403
    
    return send_file(image.filepath)

@app.route('/projects/<int:project_id>/frames/<int:frame_id>')
@require_login
def serve_video_frame(project_id, frame_id):
    project = Project.query.get_or_404(project_id)
    frame = VideoFrame.query.get_or_404(frame_id)
    
    if not current_user.can_access_project(project) or frame.project_id != project_id:
        return render_template('403.html'), 403
    
    return send_file(frame.thumbnail_path)

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

@app.route('/annotate/frame/<int:frame_id>')
@require_login
def annotate_video_frame(frame_id):
    frame = VideoFrame.query.get_or_404(frame_id)
    
    if not current_user.can_access_project(frame.project):
        return render_template('403.html'), 403
    
    annotations = VideoAnnotation.query.filter_by(frame_id=frame_id).all()
    labels = Label.query.filter_by(project_id=frame.project_id).all()
    
    # Get next and previous frames in the project
    all_frames = VideoFrame.query.filter_by(project_id=frame.project_id)\
                                 .order_by(VideoFrame.frame_number).all()
    
    current_index = next((i for i, f in enumerate(all_frames) if f.id == frame_id), 0)
    prev_frame = all_frames[current_index - 1] if current_index > 0 else None
    next_frame = all_frames[current_index + 1] if current_index < len(all_frames) - 1 else None
    
    return render_template('annotate_frame.html',
                         frame=frame,
                         annotations=annotations,
                         labels=labels,
                         prev_frame=prev_frame,
                         next_frame=next_frame)

@app.route('/api/annotations', methods=['POST'])
@require_login
def create_annotation():
    data = request.get_json()
    
    # Handle image annotations
    if 'image_id' in data:
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
    elif 'frame_id' in data:
        frame = VideoFrame.query.get_or_404(data['frame_id'])
        if not current_user.can_access_project(frame.project):
            return jsonify({'error': 'Access denied'}), 403
        
        annotation = VideoAnnotation(
            frame_id=data['frame_id'],
            label_id=data['label_id'],
            user_id=current_user.id,
            x=data['x'],
            y=data['y'],
            width=data['width'],
            height=data['height']
        )
    else:
        return jsonify({'error': 'Either image_id or frame_id is required'}), 400
    
    db.session.add(annotation)
    db.session.commit()
    
    return jsonify({
        'id': annotation.id,
        'message': 'Annotation created successfully'
    })

@app.route('/api/video-annotations', methods=['POST'])
@require_login
def create_video_annotation():
    data = request.get_json()
    
    frame = VideoFrame.query.get_or_404(data['frame_id'])
    if not current_user.can_access_project(frame.project):
        return jsonify({'error': 'Access denied'}), 403
    
    annotation = VideoAnnotation(
        frame_id=data['frame_id'],
        label_id=data['label_id'],
        user_id=current_user.id,
        x=data['x'],
        y=data['y'],
        width=data['width'],
        height=data['height']
    )
    
    db.session.add(annotation)
    db.session.commit()
    
    return jsonify({'id': annotation.id, 'message': 'Video annotation created'}), 201

@app.route('/api/annotations/<int:annotation_id>', methods=['PUT'])
@require_login
def update_annotation(annotation_id):
    # Try both image and video annotations
    annotation = Annotation.query.filter_by(id=annotation_id).first()
    video_annotation = VideoAnnotation.query.filter_by(id=annotation_id).first()
    
    if annotation:
        if not current_user.can_access_project(annotation.image.project):
            return jsonify({'error': 'Access denied'}), 403
        target_annotation = annotation
    elif video_annotation:
        if not current_user.can_access_project(video_annotation.frame.project):
            return jsonify({'error': 'Access denied'}), 403
        target_annotation = video_annotation
    else:
        return jsonify({'error': 'Annotation not found'}), 404
    
    data = request.get_json()
    target_annotation.x = data['x']
    target_annotation.y = data['y']
    target_annotation.width = data['width']
    target_annotation.height = data['height']
    target_annotation.label_id = data['label_id']
    
    db.session.commit()
    
    return jsonify({'message': 'Annotation updated successfully'})

@app.route('/api/annotations/<int:annotation_id>', methods=['DELETE'])
@require_login
def delete_annotation(annotation_id):
    # Try both image and video annotations
    annotation = Annotation.query.filter_by(id=annotation_id).first()
    video_annotation = VideoAnnotation.query.filter_by(id=annotation_id).first()
    
    if annotation:
        if not current_user.can_access_project(annotation.image.project):
            return jsonify({'error': 'Access denied'}), 403
        target_annotation = annotation
    elif video_annotation:
        if not current_user.can_access_project(video_annotation.frame.project):
            return jsonify({'error': 'Access denied'}), 403
        target_annotation = video_annotation
    else:
        return jsonify({'error': 'Annotation not found'}), 404
    
    db.session.delete(target_annotation)
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
