import os
import uuid
from PIL import Image
from werkzeug.utils import secure_filename
from flask import current_app

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'webp'}

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

def get_default_label_colors():
    """Return a list of default colors for labels"""
    return [
        "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7",
        "#DDA0DD", "#98D8C8", "#F7DC6F", "#BB8FCE", "#85C1E9",
        "#F8C471", "#82E0AA", "#F1948A", "#85C1E9", "#D5A6BD"
    ]
