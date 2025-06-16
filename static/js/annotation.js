/**
 * Main annotation tool class that handles the complete annotation workflow
 */
class AnnotationTool {
    constructor(options) {
        this.canvasId = options.canvasId;
        this.canvas = options.canvas;
        this.imageUrl = options.imageUrl;
        this.imageWidth = options.imageWidth;
        this.imageHeight = options.imageHeight;
        
        // Convert labels array to object if needed
        this.labels = {};
        if (options.labels) {
            if (Array.isArray(options.labels)) {
                options.labels.forEach(label => {
                    this.labels[label.id] = label;
                });
            } else {
                this.labels = options.labels;
            }
        }
        
        // Canvas and renderer
        this.renderer = null;
        
        // Annotation management
        this.annotations = [];
        this.selectedAnnotation = null;
        this.selectedLabelId = null;
        
        // Drawing state
        this.isDrawing = false;
        this.drawingBox = null;
        this.startPoint = null;
        
        // Interaction state
        this.isDragging = false;
        this.isResizing = false;
        this.dragStart = null;
        this.resizeHandle = null;
        
        // Initialize from existing annotations
        if (options.annotations && options.annotationIds && options.annotationLabels) {
            this.loadExistingAnnotations(
                options.annotations, 
                options.annotationIds, 
                options.annotationLabels
            );
        }
    }
    
    init() {
        // Handle both canvas element and canvas ID
        if (this.canvas) {
            console.log('Using provided canvas element');
        } else if (this.canvasId) {
            this.canvas = document.getElementById(this.canvasId);
            if (!this.canvas) {
                console.error('Canvas element not found:', this.canvasId);
                return;
            }
        } else {
            console.error('No canvas element or canvas ID provided');
            return;
        }
        
        this.renderer = new CanvasRenderer(this.canvas);
        this.setupEventListeners();
        
        return this.renderer.loadImage(this.imageUrl).then(() => {
            console.log('Image loaded, drawing annotations');
            this.draw();
        });
    }
    
    setupEventListeners() {
        // Mouse events
        this.canvas.addEventListener('mousedown', this.onMouseDown.bind(this));
        this.canvas.addEventListener('mousemove', this.onMouseMove.bind(this));
        this.canvas.addEventListener('mouseup', this.onMouseUp.bind(this));
        this.canvas.addEventListener('mouseleave', this.onMouseLeave.bind(this));
        
        // Touch events for mobile support
        this.canvas.addEventListener('touchstart', this.onTouchStart.bind(this));
        this.canvas.addEventListener('touchmove', this.onTouchMove.bind(this));
        this.canvas.addEventListener('touchend', this.onTouchEnd.bind(this));
        
        // Prevent context menu
        this.canvas.addEventListener('contextmenu', (e) => e.preventDefault());
        
        // Wheel event for zooming
        this.canvas.addEventListener('wheel', this.onWheel.bind(this));
    }
    
    loadExistingAnnotations(annotations, ids, labelIds) {
        console.log('Loading existing annotations:', annotations);
        for (let i = 0; i < annotations.length; i++) {
            const ann = annotations[i];
            const id = ids[i];
            const labelId = labelIds[i];
            const label = this.labels[labelId];
            
            if (label) {
                const box = new AnnotationBox(
                    ann.x, ann.y, ann.width, ann.height,
                    labelId, label.color, id
                );
                box.saved = true; // Mark as saved
                this.annotations.push(box);
                console.log('Added annotation box:', box);
            } else {
                console.warn('Label not found for ID:', labelId);
            }
        }
        console.log('Total annotations loaded:', this.annotations.length);
    }
    
    onMouseDown(e) {
        e.preventDefault();
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        
        // Check if clicking on an existing annotation
        const clickedAnnotation = this.getAnnotationAt(x, y);
        
        if (clickedAnnotation) {
            this.selectedAnnotation = clickedAnnotation;
            this.selectedAnnotation.selected = true;
            this.annotations.forEach(ann => {
                if (ann !== this.selectedAnnotation) ann.selected = false;
            });
            this.updateAnnotationSelection();
            this.isDragging = true;
            this.dragStart = { x, y };
            this.canvas.style.cursor = 'move';
        } else if (this.selectedLabelId && this.renderer.isPointInImage(x, y)) {
            // Start drawing new annotation
            this.isDrawing = true;
            const imageCoords = this.renderer.screenToImage(x, y);
            this.startPoint = imageCoords;
            this.canvas.style.cursor = 'crosshair';
            
            // Deselect any selected annotation
            this.selectedAnnotation = null;
            this.updateAnnotationSelection();
        } else {
            // Deselect any selected annotation
            this.selectedAnnotation = null;
            this.updateAnnotationSelection();
        }
        
        this.draw();
    }
    
    onMouseMove(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        
        if (this.isDrawing && this.startPoint) {
            // Draw new annotation
            const imageCoords = this.renderer.screenToImage(x, y);
            const width = Math.abs(imageCoords.x - this.startPoint.x);
            const height = Math.abs(imageCoords.y - this.startPoint.y);
            const minX = Math.min(this.startPoint.x, imageCoords.x);
            const minY = Math.min(this.startPoint.y, imageCoords.y);
            
            // Constrain to image bounds
            const constrainedX = Math.max(0, Math.min(minX, this.imageWidth));
            const constrainedY = Math.max(0, Math.min(minY, this.imageHeight));
            const constrainedWidth = Math.min(width, this.imageWidth - constrainedX);
            const constrainedHeight = Math.min(height, this.imageHeight - constrainedY);
            
            if (constrainedWidth > 1 && constrainedHeight > 1) {
                const label = this.labels[this.selectedLabelId];
                if (label) {
                    this.drawingBox = new AnnotationBox(
                        constrainedX, constrainedY, constrainedWidth, constrainedHeight,
                        this.selectedLabelId, label.color
                    );
                }
            }
            
            this.draw();
        } else if (this.isDragging && this.selectedAnnotation && this.dragStart) {
            // Drag existing annotation
            const deltaX = (x - this.dragStart.x) / this.renderer.scale;
            const deltaY = (y - this.dragStart.y) / this.renderer.scale;
            
            const newX = Math.max(0, Math.min(this.selectedAnnotation.x + deltaX, 
                                            this.imageWidth - this.selectedAnnotation.width));
            const newY = Math.max(0, Math.min(this.selectedAnnotation.y + deltaY, 
                                            this.imageHeight - this.selectedAnnotation.height));
            
            this.selectedAnnotation.setBounds(newX, newY, 
                                            this.selectedAnnotation.width, 
                                            this.selectedAnnotation.height);
            this.selectedAnnotation.saved = false;
            
            this.dragStart = { x, y };
            this.draw();
        } else {
            // Update hover state
            const hoverAnnotation = this.getAnnotationAt(x, y);
            this.updateHoverState(hoverAnnotation);
            
            // Update cursor
            if (hoverAnnotation) {
                this.canvas.style.cursor = 'pointer';
            } else if (this.selectedLabelId && this.renderer.isPointInImage(x, y)) {
                this.canvas.style.cursor = 'crosshair';
            } else {
                this.canvas.style.cursor = 'default';
            }
        }
    }
    
    onMouseUp(e) {
        if (!e) e = { clientX: 0, clientY: 0 };
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        
        if (this.isDrawing && this.drawingBox) {
            // Finish drawing new annotation
            if (this.drawingBox.width > 10 && this.drawingBox.height > 10) {
                this.drawingBox.saved = false; // Mark as unsaved
                this.annotations.push(this.drawingBox);
                
                // Enable save button
                const saveBtn = document.getElementById('saveBtn');
                if (saveBtn) saveBtn.disabled = false;
                
                // Update annotation count
                this.updateAnnotationCount();
            }
            this.drawingBox = null;
            this.isDrawing = false;
            this.startPoint = null;
        }
        
        this.isDragging = false;
        this.isResizing = false;
        this.dragStart = null;
        this.resizeHandle = null;
        this.canvas.style.cursor = 'default';
        
        this.draw();
    }
    
    onMouseLeave() {
        this.onMouseUp();
        this.updateHoverState(null);
    }
    
    onTouchStart(e) {
        e.preventDefault();
        if (e.touches && e.touches.length === 1) {
            const touch = e.touches[0];
            const mockEvent = {
                preventDefault: () => {},
                clientX: touch.clientX,
                clientY: touch.clientY
            };
            this.onMouseDown(mockEvent);
        }
    }
    
    onTouchMove(e) {
        e.preventDefault();
        if (e.touches && e.touches.length === 1) {
            const touch = e.touches[0];
            const mockEvent = {
                clientX: touch.clientX,
                clientY: touch.clientY
            };
            this.onMouseMove(mockEvent);
        }
    }
    
    onTouchEnd(e) {
        e.preventDefault();
        const mockEvent = {
            preventDefault: () => {},
            clientX: 0,
            clientY: 0
        };
        this.onMouseUp(mockEvent);
    }
    
    onWheel(e) {
        e.preventDefault();
        
        if (e.deltaY < 0) {
            this.zoomIn();
        } else {
            this.zoomOut();
        }
    }
    
    getAnnotationAt(screenX, screenY) {
        const imageCoords = this.renderer.screenToImage(screenX, screenY);
        
        // Check from top to bottom (last drawn first)
        for (let i = this.annotations.length - 1; i >= 0; i--) {
            const annotation = this.annotations[i];
            if (annotation.containsPoint(imageCoords.x, imageCoords.y)) {
                return annotation;
            }
        }
        
        return null;
    }
    
    updateHoverState(hoverAnnotation) {
        this.annotations.forEach(annotation => {
            annotation.setHover(annotation === hoverAnnotation);
        });
        this.draw();
    }
    
    updateAnnotationSelection() {
        this.annotations.forEach(annotation => {
            annotation.setSelected(annotation === this.selectedAnnotation);
        });
        
        // Update UI
        document.querySelectorAll('.annotation-item').forEach(item => {
            item.classList.remove('selected');
            if (this.selectedAnnotation && 
                parseInt(item.dataset.annotationId) === this.selectedAnnotation.id) {
                item.classList.add('selected');
            }
        });
    }
    
    draw() {
        if (!this.renderer || !this.renderer.imageLoaded) {
            console.log('Cannot draw: renderer not ready or image not loaded');
            return;
        }
        
        // Draw image first
        this.renderer.draw();
        
        // Draw all annotations
        console.log('Drawing', this.annotations.length, 'annotations');
        this.annotations.forEach((annotation, index) => {
            if (annotation.draw) {
                console.log(`Drawing annotation ${index}:`, annotation);
                annotation.draw(this.renderer.ctx, this.renderer);
            } else {
                console.warn('Annotation missing draw method:', annotation);
            }
        });
        
        // Draw current drawing box
        if (this.drawingBox && this.drawingBox.draw) {
            console.log('Drawing current box:', this.drawingBox);
            this.drawingBox.draw(this.renderer.ctx, this.renderer);
        }
    }
    
    // Public API methods
    setSelectedLabel(labelId) {
        this.selectedLabelId = labelId;
    }
    
    selectAnnotation(annotationId) {
        this.selectedAnnotation = this.annotations.find(ann => ann.id === annotationId) || null;
        this.updateAnnotationSelection();
        this.draw();
    }
    
    removeAnnotation(annotationId) {
        const index = this.annotations.findIndex(ann => ann.id === annotationId);
        if (index !== -1) {
            if (this.selectedAnnotation && this.selectedAnnotation.id === annotationId) {
                this.selectedAnnotation = null;
            }
            this.annotations.splice(index, 1);
            this.draw();
        }
    }
    
    deleteSelectedAnnotation() {
        if (this.selectedAnnotation) {
            this.removeAnnotation(this.selectedAnnotation.id);
        }
    }
    
    getSelectedAnnotation() {
        return this.selectedAnnotation;
    }
    
    getAnnotationCount() {
        return this.annotations.length;
    }
    
    updateAnnotationCount() {
        const countElement = document.getElementById('annotationCount');
        if (countElement) {
            countElement.textContent = this.annotations.length;
        }
    }
    
    getUnsavedAnnotations() {
        return this.annotations.filter(annotation => !annotation.saved);
    }
    
    markAnnotationsSaved() {
        this.annotations.forEach(annotation => {
            annotation.saved = true;
        });
    }
    
    cancelDrawing() {
        this.isDrawing = false;
        this.drawingBox = null;
        this.startPoint = null;
        this.canvas.style.cursor = 'default';
        this.draw();
    }
    
    zoomIn(factor = 1.2) {
        this.renderer.zoomIn(factor);
        this.draw();
    }
    
    zoomOut(factor = 1.2) {
        this.renderer.zoomOut(factor);
        this.draw();
    }
    
    resetZoom() {
        this.renderer.resetZoom();
        this.draw();
    }
    
    // Utility methods
    exportAnnotations(format = 'json') {
        const exportData = this.annotations.map(annotation => ({
            id: annotation.id,
            x: annotation.x,
            y: annotation.y,
            width: annotation.width,
            height: annotation.height,
            labelId: annotation.labelId,
            labelName: this.labels[annotation.labelId]?.name
        }));
        
        if (format === 'json') {
            return JSON.stringify(exportData, null, 2);
        }
        
        return exportData;
    }
    
    importAnnotations(data) {
        try {
            const annotations = typeof data === 'string' ? JSON.parse(data) : data;
            
            this.annotations = annotations.map(ann => {
                const label = this.labels[ann.labelId];
                return new AnnotationBox(
                    ann.x, ann.y, ann.width, ann.height,
                    ann.labelId, label?.color || '#FF6B6B', ann.id
                );
            });
            
            this.draw();
            return true;
        } catch (error) {
            console.error('Failed to import annotations:', error);
            return false;
        }
    }
    
    // Keyboard shortcut handlers
    handleKeyDown(e) {
        switch (e.key) {
            case 'Delete':
            case 'Backspace':
                if (this.selectedAnnotation) {
                    this.deleteSelectedAnnotation();
                }
                break;
            case 'Escape':
                this.cancelDrawing();
                break;
            case '=':
            case '+':
                this.zoomIn();
                break;
            case '-':
                this.zoomOut();
                break;
            case '0':
                this.resetZoom();
                break;
        }
    }
    
    // Statistics
    getStatistics() {
        const stats = {
            total: this.annotations.length,
            byLabel: {}
        };
        
        this.annotations.forEach(annotation => {
            const labelName = this.labels[annotation.labelId]?.name || 'Unknown';
            stats.byLabel[labelName] = (stats.byLabel[labelName] || 0) + 1;
        });
        
        return stats;
    }
    
    // Validation
    validateAnnotations() {
        const errors = [];
        
        this.annotations.forEach((annotation, index) => {
            if (annotation.x < 0 || annotation.y < 0) {
                errors.push(`Annotation ${index + 1}: Invalid position`);
            }
            
            if (annotation.width <= 0 || annotation.height <= 0) {
                errors.push(`Annotation ${index + 1}: Invalid dimensions`);
            }
            
            if (annotation.x + annotation.width > this.imageWidth ||
                annotation.y + annotation.height > this.imageHeight) {
                errors.push(`Annotation ${index + 1}: Outside image bounds`);
            }
            
            if (!this.labels[annotation.labelId]) {
                errors.push(`Annotation ${index + 1}: Invalid label`);
            }
        });
        
        return errors;
    }
}

// Export for use in other modules
window.AnnotationTool = AnnotationTool;
