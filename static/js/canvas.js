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
        // Set up high DPI canvas
        const dpr = window.devicePixelRatio || 1;
        const rect = this.canvas.getBoundingClientRect();
        
        this.canvas.width = rect.width * dpr;
        this.canvas.height = rect.height * dpr;
        
        this.ctx.scale(dpr, dpr);
        this.canvas.style.width = rect.width + 'px';
        this.canvas.style.height = rect.height + 'px';
        
        // Handle resize
        window.addEventListener('resize', () => {
            this.setupCanvas();
            this.draw();
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
        
        const canvasRect = this.canvas.getBoundingClientRect();
        const scaleX = canvasRect.width / this.image.width;
        const scaleY = canvasRect.height / this.image.height;
        
        this.scale = Math.min(scaleX, scaleY, 1); // Don't scale up beyond 100%
        
        // Center the image
        this.offsetX = (canvasRect.width - this.image.width * this.scale) / 2;
        this.offsetY = (canvasRect.height - this.image.height * this.scale) / 2;
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
        const rect = this.canvas.getBoundingClientRect();
        const x = screenX - rect.left - this.offsetX;
        const y = screenY - rect.top - this.offsetY;
        
        return {
            x: x / this.scale,
            y: y / this.scale
        };
    }
    
    imageToScreen(imageX, imageY) {
        const rect = this.canvas.getBoundingClientRect();
        return {
            x: imageX * this.scale + this.offsetX + rect.left,
            y: imageY * this.scale + this.offsetY + rect.top
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
            screenCoords.x - renderer.canvas.getBoundingClientRect().left,
            screenCoords.y - renderer.canvas.getBoundingClientRect().top,
            screenWidth,
            screenHeight
        );
        
        // Draw fill for selected/hover
        if (this.selected || this.hover) {
            ctx.fillStyle = this.color + '20'; // 20 for alpha
            ctx.fillRect(
                screenCoords.x - renderer.canvas.getBoundingClientRect().left,
                screenCoords.y - renderer.canvas.getBoundingClientRect().top,
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
        const rect = renderer.canvas.getBoundingClientRect();
        
        const handleSize = 6;
        const handles = [
            { x: screenCoords.x - rect.left - handleSize/2, y: screenCoords.y - rect.top - handleSize/2 }, // Top-left
            { x: screenCoords.x - rect.left + screenWidth - handleSize/2, y: screenCoords.y - rect.top - handleSize/2 }, // Top-right
            { x: screenCoords.x - rect.left - handleSize/2, y: screenCoords.y - rect.top + screenHeight - handleSize/2 }, // Bottom-left
            { x: screenCoords.x - rect.left + screenWidth - handleSize/2, y: screenCoords.y - rect.top + screenHeight - handleSize/2 } // Bottom-right
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
