import os
import uuid
import cv2
import numpy as np
from PIL import Image
from werkzeug.utils import secure_filename
from flask import current_app

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'webp'}
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'webm'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_uploaded_image(file, project_id):
    """Save uploaded image and return image info"""
    if not file or not allowed_file(file.filename):
        return None
    
    # Generate unique filename
    original_filename = secure_filename(file.filename)
    filename = f"{uuid.uuid4().hex}_{original_filename}"
    
    # Create project-specific directory
    project_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], str(project_id))
    os.makedirs(project_dir, exist_ok=True)
    
    filepath = os.path.join(project_dir, filename)
    file.save(filepath)
    
    # Get image dimensions
    with Image.open(filepath) as img:
        width, height = img.size
    
    # Get file size
    file_size = os.path.getsize(filepath)
    
    return {
        'filename': filename,
        'original_filename': original_filename,
        'filepath': filepath,
        'width': width,
        'height': height,
        'file_size': file_size
    }

def generate_pascal_voc_xml(image, annotations):
    """Generate PASCAL VOC XML format for annotations"""
    xml_content = f"""<annotation>
    <folder>{image.project.name}</folder>
    <filename>{image.original_filename}</filename>
    <path>{image.filepath}</path>
    <source>
        <database>Unknown</database>
    </source>
    <size>
        <width>{image.width}</width>
        <height>{image.height}</height>
        <depth>3</depth>
    </size>
    <segmented>0</segmented>"""
    
    for annotation in annotations:
        xmin = int(annotation.x)
        ymin = int(annotation.y)
        xmax = int(annotation.x + annotation.width)
        ymax = int(annotation.y + annotation.height)
        
        xml_content += f"""
    <object>
        <name>{annotation.label.name}</name>
        <pose>Unspecified</pose>
        <truncated>0</truncated>
        <difficult>0</difficult>
        <bndbox>
            <xmin>{xmin}</xmin>
            <ymin>{ymin}</ymin>
            <xmax>{xmax}</xmax>
            <ymax>{ymax}</ymax>
        </bndbox>
    </object>"""
    
    xml_content += "\n</annotation>"
    return xml_content

def generate_yolo_format(image, annotations):
    """Generate YOLO format for annotations"""
    yolo_lines = []
    
    for annotation in annotations:
        # Convert to YOLO format (normalized coordinates)
        x_center = (annotation.x + annotation.width / 2) / image.width
        y_center = (annotation.y + annotation.height / 2) / image.height
        width = annotation.width / image.width
        height = annotation.height / image.height
        
        # Assuming label.id is the class index (you might need to adjust this)
        class_id = annotation.label.id
        yolo_lines.append(f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}")
    
    return "\n".join(yolo_lines)

def allowed_video_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_VIDEO_EXTENSIONS

def save_uploaded_video(file, project_id):
    """Save uploaded video and return video info"""
    if not file or not allowed_video_file(file.filename):
        return None
    
    # Generate unique filename
    original_filename = secure_filename(file.filename)
    filename = f"{uuid.uuid4().hex}_{original_filename}"
    
    # Create project-specific directory
    project_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], str(project_id))
    os.makedirs(project_dir, exist_ok=True)
    
    filepath = os.path.join(project_dir, filename)
    file.save(filepath)
    
    # Get video properties using OpenCV
    cap = cv2.VideoCapture(filepath)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = frame_count / fps if fps > 0 else 0
    cap.release()
    
    # Get file size
    file_size = os.path.getsize(filepath)
    
    return {
        'filename': filename,
        'original_filename': original_filename,
        'filepath': filepath,
        'width': width,
        'height': height,
        'file_size': file_size,
        'duration': duration,
        'fps': fps,
        'total_frames': frame_count
    }

def extract_video_frames(video_path, project_id, frame_interval=30):
    """Extract frames from video at specified intervals"""
    from models import VideoFrame, db
    
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # Create frames directory
    frames_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], str(project_id), 'frames')
    os.makedirs(frames_dir, exist_ok=True)
    
    extracted_frames = []
    frame_number = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        # Extract frame every frame_interval frames
        if frame_number % frame_interval == 0:
            timestamp = frame_number / fps
            
            # Save frame as thumbnail
            thumbnail_filename = f"frame_{frame_number:06d}.jpg"
            thumbnail_path = os.path.join(frames_dir, thumbnail_filename)
            
            # Resize frame for thumbnail (maintain aspect ratio)
            max_size = 800
            if width > height:
                new_width = max_size
                new_height = int(height * (max_size / width))
            else:
                new_height = max_size
                new_width = int(width * (max_size / height))
            
            resized_frame = cv2.resize(frame, (new_width, new_height))
            cv2.imwrite(thumbnail_path, resized_frame)
            
            # Create VideoFrame record
            video_frame = VideoFrame(
                project_id=project_id,
                frame_number=frame_number,
                timestamp=timestamp,
                thumbnail_path=thumbnail_path,
                width=new_width,
                height=new_height
            )
            db.session.add(video_frame)
            extracted_frames.append(video_frame)
        
        frame_number += 1
    
    cap.release()
    db.session.commit()
    
    return extracted_frames

def batch_process_images(image_files, project_id, batch_size=50):
    """Process images in batches for large datasets"""
    from models import Image as ImageModel, db
    
    processed_images = []
    batch_count = 0
    
    for i in range(0, len(image_files), batch_size):
        batch = image_files[i:i + batch_size]
        batch_images = []
        
        for file in batch:
            if file.filename != '':
                image_info = save_uploaded_image(file, project_id)
                if image_info:
                    image = ImageModel(
                        filename=image_info['filename'],
                        original_filename=image_info['original_filename'],
                        filepath=image_info['filepath'],
                        width=image_info['width'],
                        height=image_info['height'],
                        file_size=image_info['file_size'],
                        project_id=project_id,
                        uploaded_by=current_app.config.get('CURRENT_USER_ID')
                    )
                    batch_images.append(image)
        
        # Add batch to database
        db.session.add_all(batch_images)
        db.session.commit()
        
        processed_images.extend(batch_images)
        batch_count += 1
        
        # Update processing status
        if batch_count % 5 == 0:  # Update every 5 batches
            current_app.logger.info(f"Processed {len(processed_images)} images in {batch_count} batches")
    
    return processed_images

def get_default_label_colors():
    """Return a list of default colors for labels"""
    return [
        "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7",
        "#DDA0DD", "#98D8C8", "#F7DC6F", "#BB8FCE", "#85C1E9",
        "#F8C471", "#82E0AA", "#F1948A", "#85C1E9", "#D5A6BD"
    ]
