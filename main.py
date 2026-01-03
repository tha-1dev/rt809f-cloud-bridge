#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RT809F CLOUD BRIDGE - Cloud Run Edition
สำหรับ pmic-thai-dev.online
"""

import os
import json
import asyncio
import aiohttp
import logging
import base64
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# ============================================
# CONFIGURATION
# ============================================

class Config:
    """Configuration for RT809F Cloud Bridge"""
    PORT = int(os.getenv("PORT", 8080))
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    
    # RT809F Device Config
    RT809F_SIMULATION = True  # Simulate RT809F if no physical device
    DEVICE_POOL_SIZE = 5
    
    # Cloud Run specific
    PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "pmic-thai-dev")
    REGION = os.getenv("REGION", "asia-southeast1")
    SERVICE_NAME = os.getenv("K_SERVICE", "rt809f-bridge")
    
    # Security
    API_KEY = os.getenv("API_KEY", "thai_dev_rt809f_2023")
    ALLOWED_ORIGINS = json.loads(os.getenv("ALLOWED_ORIGINS", '["*"]'))
    
    # WebSocket
    WS_MAX_CONNECTIONS = 100
    WS_TIMEOUT = 300  # seconds

config = Config()

# ============================================
# MODELS
# ============================================

class DeviceInfo(BaseModel):
    """Device information model"""
    device_id: str
    name: str
    type: str = "rt809f"
    status: str = "disconnected"
    ip_address: Optional[str] = None
    port: Optional[int] = None
    last_seen: Optional[datetime] = None
    capabilities: List[str] = []
    metadata: Dict[str, Any] = {}

class ConnectionRequest(BaseModel):
    """Connection request model"""
    device_id: str
    api_key: Optional[str] = None
    protocol: str = "websocket"
    timeout: int = 30

class CommandRequest(BaseModel):
    """Command execution model"""
    command: str
    parameters: Dict[str, Any] = {}
    device_id: str
    timeout: int = 10

class CommandResponse(BaseModel):
    """Command response model"""
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time: float
    timestamp: datetime

# ============================================
# RT809F DEVICE SIMULATOR
# ============================================

class RT809FSimulator:
    """Simulates RT809F programmer device"""
    
    def __init__(self):
        self.devices = self._generate_devices()
        self.connections = {}
        self.command_history = []
        
    def _generate_devices(self) -> Dict[str, DeviceInfo]:
        """Generate simulated RT809F devices"""
        devices = {}
        for i in range(config.DEVICE_POOL_SIZE):
            device_id = f"rt809f_{i+1:03d}"
            devices[device_id] = DeviceInfo(
                device_id=device_id,
                name=f"RT809F Programmer #{i+1}",
                type="rt809f",
                status="connected" if i < 2 else "disconnected",
                ip_address=f"192.168.1.{100 + i}",
                port=8090 + i,
                last_seen=datetime.now(),
                capabilities=[
                    "flash_read",
                    "flash_write",
                    "chip_detect",
                    "eeprom_program",
                    "spi_interface",
                    "i2c_interface"
                ],
                metadata={
                    "firmware_version": "V1.8",
                    "serial_number": f"SN{str(uuid.uuid4())[:8].upper()}",
                    "manufacturer": "THAI-DEV",
                    "supported_chips": ["24Cxx", "25Qxx", "93Cxx", "M95xxx"]
                }
            )
        return devices
    
    async def connect(self, device_id: str) -> bool:
        """Simulate device connection"""
        if device_id in self.devices:
            device = self.devices[device_id]
            device.status = "connected"
            device.last_seen = datetime.now()
            self.connections[device_id] = {
                "connected_at": datetime.now(),
                "session_id": str(uuid.uuid4())
            }
            return True
        return False
    
    async def disconnect(self, device_id: str) -> bool:
        """Simulate device disconnection"""
        if device_id in self.connections:
            del self.connections[device_id]
            if device_id in self.devices:
                self.devices[device_id].status = "disconnected"
            return True
        return False
    
    async def execute_command(self, device_id: str, command: str, params: Dict) -> CommandResponse:
        """Execute command on simulated device"""
        start_time = time.time()
        
        if device_id not in self.devices:
            return CommandResponse(
                success=False,
                error=f"Device {device_id} not found",
                execution_time=time.time() - start_time,
                timestamp=datetime.now()
            )
        
        if self.devices[device_id].status != "connected":
            return CommandResponse(
                success=False,
                error=f"Device {device_id} is not connected",
                execution_time=time.time() - start_time,
                timestamp=datetime.now()
            )
        
        # Simulate command execution
        await asyncio.sleep(random.uniform(0.1, 1.0))
        
        # Command processing
        result = None
        error = None
        success = True
        
        if command == "detect_chip":
            result = {
                "chip_found": True,
                "chip_type": random.choice(["24C64", "25Q32", "93C46", "M95010"]),
                "size": random.choice([8192, 32768, 65536, 131072]),
                "manufacturer": random.choice(["Microchip", "Winbond", "ST", "Atmel"])
            }
        elif command == "read_flash":
            size = params.get("size", 1024)
            result = {
                "data": base64.b64encode(os.urandom(size)).decode(),
                "size": size,
                "checksum": hashlib.md5(os.urandom(size)).hexdigest()
            }
        elif command == "write_flash":
            result = {
                "success": True,
                "bytes_written": params.get("data_size", 0),
                "verification_passed": True
            }
        elif command == "get_device_info":
            result = self.devices[device_id].dict()
        elif command == "list_supported_chips":
            result = {
                "chips": [
                    {"name": "24C01", "interface": "I2C", "size": 128},
                    {"name": "24C64", "interface": "I2C", "size": 8192},
                    {"name": "25Q32", "interface": "SPI", "size": 4194304},
                    {"name": "93C46", "interface": "MICROWIRE", "size": 1024},
                    {"name": "M95010", "interface": "SPI", "size": 1024}
                ]
            }
        else:
            success = False
            error = f"Unknown command: {command}"
        
        response = CommandResponse(
            success=success,
            result=result,
            error=error,
            execution_time=time.time() - start_time,
            timestamp=datetime.now()
        )
        
        self.command_history.append({
            "device_id": device_id,
            "command": command,
            "response": response.dict(),
            "timestamp": datetime.now()
        })
        
        return response

# ============================================
# CLOUD BRIDGE MANAGER
# ============================================

class CloudBridgeManager:
    """Manages cloud bridge connections"""
    
    def __init__(self):
        self.rt809f = RT809FSimulator()
        self.websocket_connections: Dict[str, WebSocket] = {}
        self.bridge_sessions: Dict[str, Dict] = {}
        
    async def handle_device_connection(self, websocket: WebSocket, device_id: str):
        """Handle device WebSocket connection"""
        await websocket.accept()
        self.websocket_connections[device_id] = websocket
        self.bridge_sessions[device_id] = {
            "connected_at": datetime.now(),
            "last_activity": datetime.now(),
            "message_count": 0
        }
        
        try:
            # Connect to simulated device
            await self.rt809f.connect(device_id)
            
            # Send connection confirmation
            await websocket.send_json({
                "type": "connection_established",
                "device_id": device_id,
                "timestamp": datetime.now().isoformat(),
                "message": "RT809F Bridge Connected via Cloud Run"
            })
            
            # Keep connection alive
            while True:
                try:
                    data = await websocket.receive_json(timeout=config.WS_TIMEOUT)
                    
                    # Update activity
                    self.bridge_sessions[device_id]["last_activity"] = datetime.now()
                    self.bridge_sessions[device_id]["message_count"] += 1
                    
                    # Process message
                    await self._process_device_message(device_id, data)
                    
                except asyncio.TimeoutError:
                    # Send ping to keep connection alive
                    await websocket.send_json({"type": "ping", "timestamp": datetime.now().isoformat()})
                    
        except WebSocketDisconnect:
            logger.info(f"Device {device_id} disconnected")
        finally:
            # Cleanup
            await self.rt809f.disconnect(device_id)
            if device_id in self.websocket_connections:
                del self.websocket_connections[device_id]
            if device_id in self.bridge_sessions:
                del self.bridge_sessions[device_id]
    
    async def _process_device_message(self, device_id: str, data: Dict):
        """Process message from device"""
        message_type = data.get("type")
        
        if message_type == "command":
            command = data.get("command")
            params = data.get("parameters", {})
            
            # Execute command on RT809F
            response = await self.rt809f.execute_command(device_id, command, params)
            
            # Send response back
            if device_id in self.websocket_connections:
                await self.websocket_connections[device_id].send_json({
                    "type": "command_response",
                    "command": command,
                    "response": response.dict()
                })
        
        elif message_type == "status_update":
            # Update device status
            logger.info(f"Device {device_id} status: {data.get('status')}")
        
        elif message_type == "data_transfer":
            # Handle data transfer
            await self._handle_data_transfer(device_id, data)
    
    async def _handle_data_transfer(self, device_id: str, data: Dict):
        """Handle data transfer from/to device"""
        # In production, this would handle actual flash data
        transfer_id = data.get("transfer_id", str(uuid.uuid4()))
        
        # Simulate data processing
        await asyncio.sleep(0.1)
        
        if device_id in self.websocket_connections:
            await self.websocket_connections[device_id].send_json({
                "type": "transfer_complete",
                "transfer_id": transfer_id,
                "success": True,
                "timestamp": datetime.now().isoformat()
            })

# ============================================
# FASTAPI APPLICATION
# ============================================

# Initialize FastAPI
app = FastAPI(
    title="RT809F Cloud Bridge API",
    description="Cloud Run deployment for RT809F programmer bridge",
    version="1.0.0",
    docs_url="/docs" if config.DEBUG else None,
    redoc_url="/redoc" if config.DEBUG else None
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize managers
bridge_manager = CloudBridgeManager()

# ============================================
# API ROUTES
# ============================================

@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint with web interface"""
    return """
    <!DOCTYPE html>
    <html lang="th">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>RT809F Cloud Bridge - pmic-thai-dev.online</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }
            
            body {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                color: #333;
                padding: 20px;
            }
            
            .container {
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                overflow: hidden;
            }
            
            .header {
                background: linear-gradient(135deg, #1a237e 0%, #283593 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }
            
            .header h1 {
                font-size: 2.5em;
                margin-bottom: 10px;
            }
            
            .header p {
                opacity: 0.9;
                font-size: 1.1em;
            }
            
            .content {
                padding: 40px;
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 40px;
            }
            
            .card {
                background: #f8f9fa;
                border-radius: 15px;
                padding: 30px;
                box-shadow: 0 5px 15px rgba(0,0,0,0.1);
                transition: transform 0.3s;
            }
            
            .card:hover {
                transform: translateY(-5px);
            }
            
            .card h2 {
                color: #1a237e;
                margin-bottom: 20px;
                padding-bottom: 10px;
                border-bottom: 2px solid #667eea;
            }
            
            .device-list {
                display: flex;
                flex-direction: column;
                gap: 15px;
            }
            
            .device-item {
                background: white;
                padding: 20px;
                border-radius: 10px;
                border-left: 5px solid #4caf50;
                box-shadow: 0 3px 10px rgba(0,0,0,0.1);
            }
            
            .device-item.offline {
                border-left-color: #f44336;
                opacity: 0.7;
            }
            
            .device-name {
                font-weight: bold;
                font-size: 1.2em;
                margin-bottom: 5px;
            }
            
            .device-info {
                color: #666;
                font-size: 0.9em;
                margin-bottom: 10px;
            }
            
            .device-status {
                display: inline-block;
                padding: 5px 15px;
                border-radius: 20px;
                font-size: 0.8em;
                font-weight: bold;
            }
            
            .status-online {
                background: #e8f5e9;
                color: #2e7d32;
            }
            
            .status-offline {
                background: #ffebee;
                color: #c62828;
            }
            
            .btn {
                display: inline-block;
                padding: 12px 25px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 10px;
                font-weight: bold;
                cursor: pointer;
                text-decoration: none;
                transition: all 0.3s;
                text-align: center;
            }
            
            .btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 7px 20px rgba(102, 126, 234, 0.4);
            }
            
            .btn-secondary {
                background: #6c757d;
            }
            
            .api-info {
                background: #e3f2fd;
                padding: 20px;
                border-radius: 10px;
                margin-top: 20px;
            }
            
            .api-info code {
                background: #1a237e;
                color: white;
                padding: 10px;
                border-radius: 5px;
                display: block;
                margin: 10px 0;
                font-family: monospace;
                overflow-x: auto;
            }
            
            .footer {
                text-align: center;
                padding: 30px;
                background: #f8f9fa;
                color: #666;
                border-top: 1px solid #dee2e6;
            }
            
            @media (max-width: 768px) {
                .content {
                    grid-template-columns: 1fr;
                }
            }
        </style>
        <script>
            async function loadDevices() {
                try {
                    const response = await fetch('/api/devices');
                    const devices = await response.json();
                    
                    const container = document.getElementById('devices-container');
                    container.innerHTML = '';
                    
                    devices.forEach(device => {
                        const deviceEl = document.createElement('div');
                        deviceEl.className = `device-item ${device.status === 'connected' ? '' : 'offline'}`;
                        
                        const statusClass = device.status === 'connected' ? 'status-online' : 'status-offline';
                        
                        deviceEl.innerHTML = `
                            <div class="device-name">${device.name}</div>
                            <div class="device-info">ID: ${device.device_id} | IP: ${device.ip_address || 'N/A'}</div>
                            <div>
                                <span class="device-status ${statusClass}">${device.status.toUpperCase()}</span>
                                ${device.status === 'connected' ? 
                                    '<button class="btn" style="margin-left: 10px;" onclick="connectDevice(\'' + device.device_id + '\')">Connect</button>' : 
                                    ''}
                            </div>
                        `;
                        
                        container.appendChild(deviceEl);
                    });
                    
                } catch (error) {
                    console.error('Failed to load devices:', error);
                }
            }
            
            async function connectDevice(deviceId) {
                try {
                    const response = await fetch(`/api/devices/${deviceId}/connect`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-API-Key': '${config.API_KEY}'
                        }
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        alert(`Connected to ${deviceId} successfully!`);
                        loadDevices();
                    } else {
                        alert(`Failed to connect: ${result.error}`);
                    }
                    
                } catch (error) {
                    console.error('Connection failed:', error);
                    alert('Connection failed');
                }
            }
            
            async function openWebSocket() {
                const deviceId = 'rt809f_001';
                const ws = new WebSocket(`ws://${window.location.host}/ws/device/${deviceId}`);
                
                ws.onopen = () => {
                    console.log('WebSocket connected');
                    document.getElementById('ws-status').innerHTML = 
                        '<span style="color: green;">● Connected</span>';
                };
                
                ws.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    console.log('Received:', data);
                    
                    if (data.type === 'connection_established') {
                        document.getElementById('ws-messages').innerHTML += 
                            `<div>Device ${data.device_id} connected via Cloud Run</div>`;
                    }
                };
                
                ws.onerror = (error) => {
                    console.error('WebSocket error:', error);
                    document.getElementById('ws-status').innerHTML = 
                        '<span style="color: red;">● Error</span>';
                };
                
                ws.onclose = () => {
                    console.log('WebSocket disconnected');
                    document.getElementById('ws-status').innerHTML = 
                        '<span style="color: gray;">● Disconnected</span>';
                };
                
                window.ws = ws;
            }
            
            // Load devices on page load
            document.addEventListener('DOMContentLoaded', () => {
                loadDevices();
                setInterval(loadDevices, 10000); // Refresh every 10 seconds
            });
        </script>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>RT809F Cloud Bridge</h1>
                <p>pmic-thai-dev.online | Deployed on Google Cloud Run</p>
                <p style="margin-top: 15px; font-size: 0.9em; opacity: 0.8;">
                    Service: ${config.SERVICE_NAME} | Region: ${config.REGION}
                </p>
            </div>
            
            <div class="content">
                <div class="card">
                    <h2>📡 Connected Devices</h2>
                    <div class="device-list" id="devices-container">
                        <!-- Devices will be loaded here -->
                    </div>
                    <button class="btn" onclick="loadDevices()" style="margin-top: 20px; width: 100%;">
                        🔄 Refresh Devices
                    </button>
                </div>
                
                <div class="card">
                    <h2>⚡ WebSocket Bridge</h2>
                    <div style="margin-bottom: 20px;">
                        <div>Status: <span id="ws-status">● Not connected</span></div>
                        <button class="btn" onclick="openWebSocket()" style="margin-top: 10px;">
                            🔗 Connect WebSocket
                        </button>
                    </div>
                    
                    <div style="background: #f5f5f5; padding: 15px; border-radius: 10px; height: 200px; overflow-y: auto;">
                        <div id="ws-messages">
                            <!-- WebSocket messages will appear here -->
                        </div>
                    </div>
                    
                    <div class="api-info" style="margin-top: 20px;">
                        <h3>🌐 API Endpoints</h3>
                        <p>Access RT809F Bridge via REST API:</p>
                        <code>GET /api/devices</code>
                        <code>POST /api/devices/{id}/connect</code>
                        <code>POST /api/devices/{id}/command</code>
                        <code>WS /ws/device/{id}</code>
                    </div>
                </div>
            </div>
            
            <div class="footer">
                <p>© 2023 PMIC Thai-Dev | RT809F Cloud Bridge v1.0</p>
                <p style="font-size: 0.9em; margin-top: 10px;">
                    Deployed on Google Cloud Run | Bridge Status: <strong style="color: green;">Active</strong>
                </p>
                <p style="font-size: 0.8em; margin-top: 10px; opacity: 0.7;">
                    Service URL: ${os.getenv('K_SERVICE_URL', 'https://rt809f-bridge.run.app')}
                </p>
            </div>
        </div>
    </body>
    </html>
    """

@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run"""
    return {
        "status": "healthy",
        "service": config.SERVICE_NAME,
        "timestamp": datetime.now().isoformat(),
        "environment": "production" if not config.DEBUG else "development",
        "region": config.REGION,
        "device_count": len(bridge_manager.rt809f.devices)
    }

@app.get("/api/devices")
async def list_devices():
    """List all available RT809F devices"""
    devices = list(bridge_manager.rt809f.devices.values())
    return devices

@app.get("/api/devices/{device_id}")
async def get_device(device_id: str):
    """Get specific device information"""
    if device_id not in bridge_manager.rt809f.devices:
        raise HTTPException(status_code=404, detail="Device not found")
    
    return bridge_manager.rt809f.devices[device_id]

@app.post("/api/devices/{device_id}/connect")
async def connect_device(device_id: str, request: ConnectionRequest):
    """Connect to a specific device"""
    # Validate API key
    if request.api_key != config.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    if device_id not in bridge_manager.rt809f.devices:
        raise HTTPException(status_code=404, detail="Device not found")
    
    success = await bridge_manager.rt809f.connect(device_id)
    
    if success:
        return {
            "success": True,
            "device_id": device_id,
            "message": f"Connected to {device_id}",
            "session_id": bridge_manager.rt809f.connections[device_id]["session_id"]
        }
    else:
        return {
            "success": False,
            "error": "Connection failed"
        }

@app.post("/api/devices/{device_id}/command")
async def execute_device_command(device_id: str, command: CommandRequest):
    """Execute command on device"""
    if device_id not in bridge_manager.rt809f.devices:
        raise HTTPException(status_code=404, detail="Device not found")
    
    response = await bridge_manager.rt809f.execute_command(
        device_id, 
        command.command, 
        command.parameters
    )
    
    return response

@app.websocket("/ws/device/{device_id}")
async def websocket_device_endpoint(websocket: WebSocket, device_id: str):
    """WebSocket endpoint for real-time device communication"""
    await bridge_manager.handle_device_connection(websocket, device_id)

# ============================================
# DEPLOYMENT SCRIPTS
# ============================================

# Dockerfile สำหรับ Cloud Run
DOCKERFILE = """FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create non-root user
RUN useradd -m -u 1000 cloudrun && chown -R cloudrun:cloudrun /app
USER cloudrun

# Expose port
EXPOSE 8080

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
"""

# requirements.txt
REQUIREMENTS = """fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.4.2
websockets==12.0
aiohttp==3.9.0
python-multipart==0.0.6
"""

# cloudbuild.yaml สำหรับ deploy อัตโนมัติ
CLOUDBUILD_YAML = """steps:
  # Build Docker image
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/rt809f-bridge:latest', '.']
  
  # Push to Container Registry
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/rt809f-bridge:latest']
  
  # Deploy to Cloud Run
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: gcloud
    args:
      - 'run'
      - 'deploy'
      - 'rt809f-bridge'
      - '--image'
      - 'gcr.io/$PROJECT_ID/rt809f-bridge:latest'
      - '--region'
      - 'asia-southeast1'
      - '--platform'
      - 'managed'
      - '--allow-unauthenticated'
      - '--memory'
      - '512Mi'
      - '--cpu'
      - '1'
      - '--max-instances'
      - '10'
      - '--timeout'
      - '300'

images:
  - 'gcr.io/$PROJECT_ID/rt809f-bridge:latest'
"""

# deployment.yaml สำหรับ Kubernetes (ถ้าต้องการ)
DEPLOYMENT_YAML = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: rt809f-bridge
  labels:
    app: rt809f-bridge
spec:
  replicas: 3
  selector:
    matchLabels:
      app: rt809f-bridge
  template:
    metadata:
      labels:
        app: rt809f-bridge
    spec:
      containers:
      - name: rt809f-bridge
        image: gcr.io/pmic-thai-dev/rt809f-bridge:latest
        ports:
        - containerPort: 8080
        env:
        - name: PORT
          value: "8080"
        - name: API_KEY
          valueFrom:
            secretKeyRef:
              name: rt809f-secrets
              key: api-key
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: rt809f-bridge-service
spec:
  selector:
    app: rt809f-bridge
  ports:
  - port: 80
    targetPort: 8080
  type: LoadBalancer
"""

# ============================================
# DEPLOYMENT UTILITIES
# ============================================

def generate_deployment_files():
    """Generate necessary deployment files"""
    files = {
        "Dockerfile": DOCKERFILE,
        "requirements.txt": REQUIREMENTS,
        "cloudbuild.yaml": CLOUDBUILD_YAML,
        "deployment.yaml": DEPLOYMENT_YAML,
        "main.py": __file__  # This file
    }
    
    print("📦 Generating deployment files for Cloud Run...")
    
    for filename, content in files.items():
        if filename == "main.py":
            # Save current file
            with open("main.py", "w") as f:
                f.write(content)
        else:
            with open(filename, "w") as f:
                f.write(content)
        
        print(f"✅ Created {filename}")
    
    print("\n🚀 Deployment files ready!")
    print("\nCommands to deploy:")
    print("1. Set up Google Cloud Project:")
    print("   gcloud config set project pmic-thai-dev")
    print("\n2. Build and deploy with Cloud Build:")
    print("   gcloud builds submit --config cloudbuild.yaml")
    print("\n3. Or deploy directly to Cloud Run:")
    print("   gcloud run deploy rt809f-bridge \\")
    print("     --source . \\")
    print("     --region asia-southeast1 \\")
    print("     --allow-unauthenticated")
    print("\n4. Access your service:")
    print("   https://rt809f-bridge-[hash]-[region].run.app")

# ============================================
# MAIN EXECUTION
# ============================================

if __name__ == "__main__":
    import sys
    
    # Generate deployment files if requested
    if len(sys.argv) > 1 and sys.argv[1] == "generate":
        generate_deployment_files()
    else:
        # Start the server
        print(f"""
        🚀 RT809F Cloud Bridge Starting...
        
        Service: {config.SERVICE_NAME}
        Port: {config.PORT}
        Debug: {config.DEBUG}
        
        Endpoints:
          Web UI: http://localhost:{config.PORT}/
          API Docs: http://localhost:{config.PORT}/docs
          Health: http://localhost:{config.PORT}/health
          WebSocket: ws://localhost:{config.PORT}/ws/device/rt809f_001
        
        Cloud Run Deployment Ready!
        """)
        
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=config.PORT,
            log_level="info" if config.DEBUG else "warning"
        )
