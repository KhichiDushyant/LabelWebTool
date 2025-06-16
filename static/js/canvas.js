/**
 * Canvas utility class for handling image display and transformations
 */
class CanvasRenderer {
    constructor(canvas) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.scale = 1;
        this.offsetX = 0;
        this.offsetY = 0;
        this.image = null;
        this.imageLoaded = false;
        
        this.setupCanvas();
    }
    
    setupCanvas() {
        // Set canvas size to fill the container
        const container = this.canvas.parentElement;
        const containerRect = container.getBoundingClientRect();
        
        // Calculate optimal canvas size (minimum 800x600, but scale to fit container)
        const minWidth = 800;
        const minHeight = 600;
        const maxWidth = Math.max(containerRect.width - 20, minWidth);
        const maxHeight = Math.max(containerRect.height - 20, minHeight);
        
        // Set canvas size directly without DPI scaling for simpler coordinate system
        this.canvas.width = maxWidth;
        this.canvas.height = maxHeight;
        this.canvas.style.width = maxWidth + 'px';
        this.canvas.style.height = maxHeight + 'px';
        
        // Handle resize
        window.addEventListener('resize', () => {
            this.setupCanvas();
            if (this.imageLoaded) {
                this.fitImageToCanvas();
                this.draw();
            }
        });
    }
    
    loadImage(url) {
        return new Promise((resolve, reject) => {
            this.image = new Image();
            this.image.onload = () => {
                this.imageLoaded = true;
                this.fitImageToCanvas();
                this.draw();
                resolve();
            };
            this.image.onerror = reject;
            this.image.src = url;
        });
    }
    
    fitImageToCanvas() {
        if (!this.image) return;
        
        const scaleX = this.canvas.width / this.image.width;
        const scaleY = this.canvas.height / this.image.height;
        
        // Use a larger scale to fill more of the canvas, allow scaling up to 2x for small images
        this.scale = Math.min(scaleX, scaleY, 2); 
        
        // Center the image
        this.offsetX = (this.canvas.width - this.image.width * this.scale) / 2;
        this.offsetY = (this.canvas.height - this.image.height * this.scale) / 2;
    }
    
    draw() {
        if (!this.imageLoaded) return;
        
        // Clear canvas
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Draw image
        this.ctx.drawImage(
            this.image,
            this.offsetX,
            this.offsetY,
            this.image.width * this.scale,
            this.image.height * this.scale
        );
    }
    
    screenToImage(screenX, screenY) {
        const x = screenX - this.offsetX;
        const y = screenY - this.offsetY;
        
        return {
            x: x / this.scale,
            y: y / this.scale
        };
    }
    
    imageToScreen(imageX, imageY) {
        return {
            x: imageX * this.scale + this.offsetX,
            y: imageY * this.scale + this.offsetY
        };
    }
    
    zoomIn(factor = 1.2) {
        this.scale *= factor;
        this.draw();
    }
    
    zoomOut(factor = 1.2) {
        this.scale /= factor;
        this.draw();
    }
    
    resetZoom() {
        this.fitImageToCanvas();
        this.draw();
    }
    
    pan(deltaX, deltaY) {
        this.offsetX += deltaX;
        this.offsetY += deltaY;
        this.draw();
    }
    
    getImageBounds() {
        if (!this.image) return null;
        
        return {
            x: this.offsetX,
            y: this.offsetY,
            width: this.image.width * this.scale,
            height: this.image.height * this.scale
        };
    }
    
    isPointInImage(screenX, screenY) {
        const bounds = this.getImageBounds();
        if (!bounds) return false;
        
        const rect = this.canvas.getBoundingClientRect();
        const x = screenX - rect.left;
        const y = screenY - rect.top;
        
        return x >= bounds.x && x <= bounds.x + bounds.width &&
               y >= bounds.y && y <= bounds.y + bounds.height;
    }
}

/**
 * Annotation box class for handling bounding box rendering and interaction
 */
class AnnotationBox {
    constructor(x, y, width, height, labelId, color, id = null) {
        this.x = x;
        this.y = y;
        this.width = width;
        this.height = height;
        this.labelId = labelId;
        this.color = color;
        this.id = id;
        this.selected = false;
        this.hover = false;
        this.saved = id !== null;
    }
    
    draw(ctx, renderer) {
        const screenCoords = renderer.imageToScreen(this.x, this.y);
        const screenWidth = this.width * renderer.scale;
        const screenHeight = this.height * renderer.scale;
        
        // Draw bounding box
        ctx.strokeStyle = this.color;
        ctx.lineWidth = this.selected ? 3 : 2;
        ctx.setLineDash(this.saved ? [] : [5, 5]);
        
        ctx.strokeRect(
            screenCoords.x,
            screenCoords.y,
            screenWidth,
            screenHeight
        );
        
        // Draw fill for selected/hover
        if (this.selected || this.hover) {
            ctx.fillStyle = this.color + '20'; // 20 for alpha
            ctx.fillRect(
                screenCoords.x,
                screenCoords.y,
                screenWidth,
                screenHeight
            );
        }
        
        // Draw resize handles for selected annotation
        if (this.selected) {
            this.drawResizeHandles(ctx, renderer);
        }
        
        ctx.setLineDash([]);
    }
    
    drawResizeHandles(ctx, renderer) {
        const screenCoords = renderer.imageToScreen(this.x, this.y);
        const screenWidth = this.width * renderer.scale;
        const screenHeight = this.height * renderer.scale;
        
        const handleSize = 6;
        const handles = [
            { x: screenCoords.x - handleSize/2, y: screenCoords.y - handleSize/2 }, // Top-left
            { x: screenCoords.x + screenWidth - handleSize/2, y: screenCoords.y - handleSize/2 }, // Top-right
            { x: screenCoords.x - handleSize/2, y: screenCoords.y + screenHeight - handleSize/2 }, // Bottom-left
            { x: screenCoords.x + screenWidth - handleSize/2, y: screenCoords.y + screenHeight - handleSize/2 } // Bottom-right
        ];
        
        ctx.fillStyle = this.color;
        handles.forEach(handle => {
            ctx.fillRect(handle.x, handle.y, handleSize, handleSize);
        });
    }
    
    containsPoint(x, y) {
        return x >= this.x && x <= this.x + this.width &&
               y >= this.y && y <= this.y + this.height;
    }
    
    getBounds() {
        return {
            x: this.x,
            y: this.y,
            width: this.width,
            height: this.height
        };
    }
    
    setBounds(x, y, width, height) {
        this.x = Math.max(0, x);
        this.y = Math.max(0, y);
        this.width = Math.max(1, width);
        this.height = Math.max(1, height);
    }
    
    setSelected(selected) {
        this.selected = selected;
    }
    
    setHover(hover) {
        this.hover = hover;
    }
    
    clone() {
        return new AnnotationBox(
            this.x, this.y, this.width, this.height,
            this.labelId, this.color, this.id
        );
    }
}
