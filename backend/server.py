from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone
from PIL import Image
import io
import struct
import json
import asyncio
import aiofiles

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create directories for storing images
UPLOAD_DIR = ROOT_DIR / "uploads"
RGB565_DIR = ROOT_DIR / "rgb565"
UPLOAD_DIR.mkdir(exist_ok=True)
RGB565_DIR.mkdir(exist_ok=True)

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"ESP32 connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"ESP32 disconnected. Total connections: {len(self.active_connections)}")

    async def send_image(self, image_data: bytes, image_id: str):
        disconnected = []
        for connection in self.active_connections:
            try:
                # Send image metadata first
                metadata = {
                    "type": "image",
                    "id": image_id,
                    "size": len(image_data)
                }
                await connection.send_text(json.dumps(metadata))
                # Send image data
                await connection.send_bytes(image_data)
                logger.info(f"Sent image {image_id} ({len(image_data)} bytes) to ESP32")
            except Exception as e:
                logger.error(f"Error sending to connection: {e}")
                disconnected.append(connection)
        
        # Remove disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

    async def send_telemetry(self, gear: int, speed: int):
        disconnected = []
        telemetry_data = {
            "type": "telemetry",
            "gear": gear,
            "speed": speed
        }
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(telemetry_data))
                logger.info(f"Sent telemetry: Gear={gear}, Speed={speed}")
            except Exception as e:
                logger.error(f"Error sending telemetry: {e}")
                disconnected.append(connection)
        
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()

# Define Models
class DisplayImage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    original_path: str
    rgb565_path: str
    width: int
    height: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class DisplayImageCreate(BaseModel):
    name: str

class TelemetryData(BaseModel):
    gear: int = Field(ge=0, le=6, description="Gear position (0=N, 1-6=Gears)")
    speed: int = Field(ge=0, le=200, description="Speed in km/h")

# Image conversion functions
def rgb888_to_rgb565(r: int, g: int, b: int) -> int:
    """Convert RGB888 to RGB565 format"""
    r5 = (r >> 3) & 0x1F
    g6 = (g >> 2) & 0x3F
    b5 = (b >> 3) & 0x1F
    return (r5 << 11) | (g6 << 5) | b5

def convert_image_to_rgb565(image_path: str, output_path: str, target_width: int = 480, target_height: int = 320) -> tuple:
    """Convert image to RGB565 format for ESP32 display"""
    try:
        # Open and resize image
        img = Image.open(image_path)
        img = img.convert('RGB')
        img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
        
        # Convert to RGB565
        rgb565_data = bytearray()
        pixels = img.load()
        
        for y in range(target_height):
            for x in range(target_width):
                r, g, b = pixels[x, y]
                rgb565 = rgb888_to_rgb565(r, g, b)
                # Little endian format
                rgb565_data.append(rgb565 & 0xFF)
                rgb565_data.append((rgb565 >> 8) & 0xFF)
        
        # Save RGB565 data
        with open(output_path, 'wb') as f:
            f.write(rgb565_data)
        
        logger.info(f"Converted image to RGB565: {output_path} ({len(rgb565_data)} bytes)")
        return target_width, target_height
    except Exception as e:
        logger.error(f"Error converting image: {e}")
        raise

# API Routes
@api_router.get("/")
async def root():
    return {
        "message": "Bus Simulator Display API",
        "version": "1.0.0",
        "endpoints": {
            "images": "/api/images",
            "upload": "/api/images/upload",
            "websocket": "/ws/esp32"
        }
    }

@api_router.post("/images/upload")
async def upload_image(file: UploadFile = File(...)):
    """Upload and convert image to RGB565 format"""
    try:
        # Validate file type
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Generate unique ID
        image_id = str(uuid.uuid4())
        original_filename = file.filename or "unnamed.png"
        
        # Save original image
        original_path = UPLOAD_DIR / f"{image_id}_{original_filename}"
        async with aiofiles.open(original_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        # Convert to RGB565
        rgb565_filename = f"{image_id}.rgb565"
        rgb565_path = RGB565_DIR / rgb565_filename
        
        width, height = convert_image_to_rgb565(str(original_path), str(rgb565_path))
        
        # Save to database
        image_doc = DisplayImage(
            id=image_id,
            name=original_filename,
            original_path=str(original_path),
            rgb565_path=str(rgb565_path),
            width=width,
            height=height
        )
        
        doc = image_doc.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        await db.display_images.insert_one(doc)
        
        return {
            "success": True,
            "image": image_doc,
            "message": f"Image uploaded and converted to RGB565 ({width}x{height})"
        }
    
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/images", response_model=List[DisplayImage])
async def get_images():
    """Get all uploaded images"""
    images = await db.display_images.find({}, {"_id": 0}).to_list(1000)
    
    # Convert ISO string timestamps back to datetime objects
    for img in images:
        if isinstance(img['created_at'], str):
            img['created_at'] = datetime.fromisoformat(img['created_at'])
    
    return images

@api_router.get("/images/{image_id}")
async def get_image(image_id: str):
    """Get image details by ID"""
    image = await db.display_images.find_one({"id": image_id}, {"_id": 0})
    
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    if isinstance(image['created_at'], str):
        image['created_at'] = datetime.fromisoformat(image['created_at'])
    
    return image

@api_router.get("/images/{image_id}/preview")
async def get_image_preview(image_id: str):
    """Get original image for preview"""
    image = await db.display_images.find_one({"id": image_id}, {"_id": 0})
    
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    original_path = Path(image['original_path'])
    if not original_path.exists():
        raise HTTPException(status_code=404, detail="Image file not found")
    
    return FileResponse(original_path)

@api_router.get("/images/{image_id}/rgb565")
async def get_image_rgb565(image_id: str):
    """Get RGB565 data for ESP32 serial transfer"""
    image = await db.display_images.find_one({"id": image_id}, {"_id": 0})
    
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    rgb565_path = Path(image['rgb565_path'])
    if not rgb565_path.exists():
        raise HTTPException(status_code=404, detail="RGB565 file not found")
    
    return FileResponse(rgb565_path, media_type="application/octet-stream")

@api_router.delete("/images/{image_id}")
async def delete_image(image_id: str):
    """Delete image"""
    image = await db.display_images.find_one({"id": image_id}, {"_id": 0})
    
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Delete files
    try:
        Path(image['original_path']).unlink(missing_ok=True)
        Path(image['rgb565_path']).unlink(missing_ok=True)
    except Exception as e:
        logger.error(f"Error deleting files: {e}")
    
    # Delete from database
    await db.display_images.delete_one({"id": image_id})
    
    return {"success": True, "message": "Image deleted"}

@api_router.post("/images/{image_id}/send")
async def send_image_to_esp32(image_id: str):
    """Send image to connected ESP32 via WebSocket"""
    image = await db.display_images.find_one({"id": image_id}, {"_id": 0})
    
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    rgb565_path = Path(image['rgb565_path'])
    if not rgb565_path.exists():
        raise HTTPException(status_code=404, detail="RGB565 file not found")
    
    if not manager.active_connections:
        raise HTTPException(status_code=503, detail="No ESP32 connected")
    
    # Read RGB565 data
    async with aiofiles.open(rgb565_path, 'rb') as f:
        image_data = await f.read()
    
    # Send to all connected ESP32 devices
    await manager.send_image(image_data, image_id)
    
    return {
        "success": True,
        "message": f"Image sent to {len(manager.active_connections)} ESP32 device(s)",
        "connections": len(manager.active_connections)
    }

@api_router.post("/telemetry/send")
async def send_telemetry(data: TelemetryData):
    """Send telemetry data (gear, speed) to ESP32"""
    if not manager.active_connections:
        raise HTTPException(status_code=503, detail="No ESP32 connected")
    
    await manager.send_telemetry(data.gear, data.speed)
    
    return {
        "success": True,
        "message": f"Telemetry sent to {len(manager.active_connections)} device(s)",
        "data": data
    }

@api_router.get("/esp32/status")
async def esp32_status():
    """Get ESP32 connection status"""
    return {
        "connected": len(manager.active_connections) > 0,
        "connections": len(manager.active_connections)
    }

@api_router.get("/esp32/download-sketch")
async def download_sketch():
    """Download ESP32 Arduino sketch (USB Serial version)"""
    sketch_path = ROOT_DIR / "esp32_display_serial.ino"
    if not sketch_path.exists():
        raise HTTPException(status_code=404, detail="Sketch file not found")
    return FileResponse(
        sketch_path,
        media_type="text/plain",
        filename="esp32_display_serial.ino"
    )

# WebSocket endpoint for ESP32
@app.websocket("/ws/esp32")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and receive messages from ESP32
            data = await websocket.receive_text()
            logger.info(f"Received from ESP32: {data}")
            
            # Handle ESP32 responses (e.g., acknowledgments)
            try:
                message = json.loads(data)
                if message.get("type") == "ack":
                    logger.info(f"ESP32 acknowledged: {message.get('message')}")
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
