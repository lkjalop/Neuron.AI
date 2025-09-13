"""
TitanAI Phase 4 Enhanced: Professional Web Interface
Complete web application with AI-powered compliance assessment capabilities.
Supports real-time processing, professional reporting, and comprehensive audit trails.
"""

import logging
import json
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
import tempfile
import mimetypes

# FastAPI and web components
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Form, Depends
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.requests import Request
from starlette.websockets import WebSocketState
import aiofiles

# Pydantic models
from pydantic import BaseModel, Field
from enum import Enum

# Enhanced TitanAI components
from ..phase1_enhanced.infrastructure import get_infrastructure
from ..phase2_enhanced.assessment_engine import get_assessment_engine, ImplementationStatus
from ..phase3_enhanced.professional_reports import get_report_generator
from ..local_llm.llm_manager import get_llm_manager
from ..config_enhanced import config

# Auditor interface
from .auditor_interface import get_auditor_router

logger = logging.getLogger(__name__)

# Initialize FastAPI app with professional configuration
app = FastAPI(
    title="TitanAI Professional Compliance Assessment Platform",
    description="AI-powered compliance assessment with zero API costs and complete data sovereignty",
    version="1.0.0",
    docs_url="/api/docs" if config.DEBUG else None,
    redoc_url="/api/redoc" if config.DEBUG else None,
    openapi_url="/api/openapi.json" if config.DEBUG else None
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"] if config.DEBUG else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Initialize components
infrastructure = get_infrastructure()
assessment_engine = get_assessment_engine()
report_generator = get_report_generator()
llm_manager = get_llm_manager()

# Security (basic for now)
security = HTTPBearer(auto_error=False)

# Static files and templates
templates_dir = Path(__file__).parent / "templates"
static_dir = Path(__file__).parent / "static"
templates_dir.mkdir(exist_ok=True, parents=True)
static_dir.mkdir(exist_ok=True, parents=True)

templates = Jinja2Templates(directory=str(templates_dir))
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Include auditor router
app.include_router(get_auditor_router())


# Pydantic models for API
class AssessmentRequest(BaseModel):
    organization_name: str = Field(..., min_length=2, max_length=200)
    industry: str = Field(..., min_length=2, max_length=100)
    framework: str = Field(..., regex="^(ISO_27001|ESSENTIAL_8|SOC_2|NIST_CSF|PCI_DSS)$")
    assessment_type: str = Field(default="initial")
    description: Optional[str] = Field(None, max_length=1000)

class AssessmentResponse(BaseModel):
    assessment_id: str
    status: str
    message: str
    estimated_completion: datetime
    organization_name: str
    framework: str

class ProcessingStatus(BaseModel):
    assessment_id: str
    status: str
    progress: float
    current_phase: str
    phase_details: Dict[str, Any]
    estimated_completion: Optional[datetime]
    errors: List[str]
    warnings: List[str]
    controls_processed: int
    total_controls: int
    ai_confidence: float
    last_update: datetime

class ControlAssessmentSummary(BaseModel):
    control_id: str
    control_name: str
    implementation_status: str
    ai_confidence: float
    risk_rating: str
    requires_validation: bool

class AssessmentSummary(BaseModel):
    assessment_id: str
    organization_name: str
    framework: str
    status: str
    overall_score: float
    total_controls: int
    controls_implemented: int
    controls_partial: int
    controls_not_implemented: int
    ai_confidence_score: float
    created_at: datetime
    completed_at: Optional[datetime]
    control_summaries: List[ControlAssessmentSummary]


# WebSocket connection manager for real-time updates
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.assessment_subscriptions: Dict[str, List[str]] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"WebSocket client {client_id} connected")
    
    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        # Remove from all assessment subscriptions
        for assessment_id, clients in self.assessment_subscriptions.items():
            if client_id in clients:
                clients.remove(client_id)
        logger.info(f"WebSocket client {client_id} disconnected")
    
    def subscribe_to_assessment(self, client_id: str, assessment_id: str):
        if assessment_id not in self.assessment_subscriptions:
            self.assessment_subscriptions[assessment_id] = []
        if client_id not in self.assessment_subscriptions[assessment_id]:
            self.assessment_subscriptions[assessment_id].append(client_id)
    
    async def send_personal_message(self, message: str, client_id: str):
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_text(message)
            except:
                self.disconnect(client_id)
    
    async def broadcast_assessment_update(self, assessment_id: str, message: Dict):
        if assessment_id in self.assessment_subscriptions:
            clients = self.assessment_subscriptions[assessment_id][:]
            for client_id in clients:
                await self.send_personal_message(json.dumps(message), client_id)

manager = ConnectionManager()


# API Authentication (basic implementation)
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    # For now, just return a basic user object
    # In production, implement proper JWT validation
    if credentials is None and config.DEBUG:
        return {"user_id": "demo_user", "role": "admin"}
    return {"user_id": "demo_user", "role": "admin"}


# Main web interface route
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve main web interface"""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "title": "TitanAI Compliance Assessment Platform",
        "config": {
            "max_file_size": config.MAX_DOCUMENT_SIZE_MB,
            "supported_formats": config.SUPPORTED_FORMATS,
            "frameworks": config.ENABLED_FRAMEWORKS
        }
    })


@app.get("/auditor", response_class=HTMLResponse)
async def auditor_dashboard(request: Request, assessment_id: str = "demo-assessment"):
    """Professional auditor dashboard with AI-powered query and edit capabilities"""
    return templates.TemplateResponse("auditor_dashboard.html", {
        "request": request,
        "title": "TitanAI - Professional Auditor Dashboard",
        "assessment_id": assessment_id
    })


# Assessment creation endpoint
@app.post("/api/assessments", response_model=AssessmentResponse)
async def create_assessment(
    assessment_request: AssessmentRequest,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    current_user = Depends(get_current_user)
):
    """Create new AI-powered compliance assessment"""
    
    if not files:
        raise HTTPException(status_code=400, detail="At least one document is required")
    
    # Validate files
    total_size = 0
    for file in files:
        if not file.filename:
            raise HTTPException(status_code=400, detail="File must have a name")
        
        # Check file extension
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in config.SUPPORTED_FORMATS:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file format: {file_ext}. Supported: {config.SUPPORTED_FORMATS}"
            )
        
        # Check individual file size (estimate)
        if hasattr(file, 'size') and file.size:
            if file.size > config.MAX_DOCUMENT_SIZE_MB * 1024 * 1024:
                raise HTTPException(
                    status_code=400,
                    detail=f"File {file.filename} exceeds maximum size of {config.MAX_DOCUMENT_SIZE_MB}MB"
                )
            total_size += file.size
    
    # Check total upload size
    if total_size > config.MAX_DOCUMENT_SIZE_MB * 1024 * 1024 * len(files):
        raise HTTPException(status_code=400, detail="Total file size too large")
    
    try:
        # Create assessment in database
        assessment_id = await infrastructure["db"].create_assessment(
            organization_name=assessment_request.organization_name,
            framework=assessment_request.framework,
            industry=assessment_request.industry
        )
        
        # Store uploaded files temporarily
        uploaded_files = []
        for file in files:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix)
            content = await file.read()
            temp_file.write(content)
            temp_file.close()
            
            uploaded_files.append({
                "original_name": file.filename,
                "temp_path": temp_file.name,
                "content": content
            })
        
        # Start background processing
        background_tasks.add_task(
            process_assessment_background,
            assessment_id,
            assessment_request,
            uploaded_files
        )
        
        # Estimate completion time based on file count and size
        estimated_minutes = max(10, len(files) * 2)  # Minimum 10 minutes, 2 min per file
        estimated_completion = datetime.now() + timedelta(minutes=estimated_minutes)
        
        return AssessmentResponse(
            assessment_id=assessment_id,
            status="processing",
            message="Assessment started successfully. AI analysis in progress.",
            estimated_completion=estimated_completion,
            organization_name=assessment_request.organization_name,
            framework=assessment_request.framework
        )
        
    except Exception as e:
        logger.error(f"Error creating assessment: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create assessment: {str(e)}")


# Assessment status endpoint
@app.get("/api/assessments/{assessment_id}/status", response_model=ProcessingStatus)
async def get_assessment_status(assessment_id: str, current_user = Depends(get_current_user)):
    """Get real-time assessment processing status"""
    
    # Get assessment from database
    assessment_data = await get_assessment_from_db(assessment_id)
    if not assessment_data:
        raise HTTPException(status_code=404, detail="Assessment not found")
    
    # Get processing details
    processing_details = await get_processing_details(assessment_id)
    
    return ProcessingStatus(
        assessment_id=assessment_id,
        status=assessment_data.get('status', 'unknown'),
        progress=min(1.0, max(0.0, processing_details.get('progress', 0.0))),
        current_phase=processing_details.get('current_phase', 'initializing'),
        phase_details=processing_details.get('phase_details', {}),
        estimated_completion=processing_details.get('estimated_completion'),
        errors=processing_details.get('errors', []),
        warnings=processing_details.get('warnings', []),
        controls_processed=processing_details.get('controls_processed', 0),
        total_controls=assessment_data.get('total_controls', 0),
        ai_confidence=assessment_data.get('ai_confidence_score', 0.0),
        last_update=datetime.now()
    )


# Assessment summary endpoint
@app.get("/api/assessments/{assessment_id}", response_model=AssessmentSummary)
async def get_assessment_summary(assessment_id: str, current_user = Depends(get_current_user)):
    """Get complete assessment summary"""
    
    assessment_data = await get_assessment_from_db(assessment_id)
    if not assessment_data:
        raise HTTPException(status_code=404, detail="Assessment not found")
    
    # Get control assessments
    control_assessments = await get_control_assessments_from_db(assessment_id)
    
    control_summaries = [
        ControlAssessmentSummary(
            control_id=ca.get('control_id', ''),
            control_name=ca.get('control_name', ''),
            implementation_status=ca.get('implementation_status', 'unknown'),
            ai_confidence=ca.get('ai_confidence', 0.0),
            risk_rating=ca.get('risk_rating', 'unknown'),
            requires_validation=ca.get('requires_validation', False)
        ) for ca in control_assessments
    ]
    
    return AssessmentSummary(
        assessment_id=assessment_id,
        organization_name=assessment_data.get('organization_name', ''),
        framework=assessment_data.get('framework', ''),
        status=assessment_data.get('status', ''),
        overall_score=assessment_data.get('overall_score', 0.0),
        total_controls=assessment_data.get('total_controls', 0),
        controls_implemented=assessment_data.get('controls_implemented', 0),
        controls_partial=assessment_data.get('controls_partial', 0),
        controls_not_implemented=assessment_data.get('controls_not_implemented', 0),
        ai_confidence_score=assessment_data.get('ai_confidence_score', 0.0),
        created_at=assessment_data.get('created_at', datetime.now()),
        completed_at=assessment_data.get('completed_at'),
        control_summaries=control_summaries
    )


# Report generation endpoint
@app.post("/api/assessments/{assessment_id}/reports/{report_type}")
async def generate_report(
    assessment_id: str,
    report_type: str,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user)
):
    """Generate professional compliance report"""
    
    if report_type not in ["full", "executive", "detailed", "remediation"]:
        raise HTTPException(status_code=400, detail="Invalid report type")
    
    assessment_data = await get_assessment_from_db(assessment_id)
    if not assessment_data:
        raise HTTPException(status_code=404, detail="Assessment not found")
    
    if assessment_data.get('status') != 'completed':
        raise HTTPException(status_code=400, detail="Assessment must be completed before generating reports")
    
    # Start report generation in background
    background_tasks.add_task(
        generate_report_background,
        assessment_id,
        report_type
    )
    
    return {"message": f"Report generation started for {report_type} report", "assessment_id": assessment_id}


# Report download endpoint
@app.get("/api/assessments/{assessment_id}/reports/{report_type}/download")
async def download_report(
    assessment_id: str,
    report_type: str,
    current_user = Depends(get_current_user)
):
    """Download generated report"""
    
    # Find the report file
    report_files = list(config.REPORTS_DIR.glob(f"*{assessment_id}*.pdf"))
    
    if not report_files:
        raise HTTPException(status_code=404, detail="Report not found. Please generate report first.")
    
    # Get the most recent report file
    report_file = max(report_files, key=lambda p: p.stat().st_mtime)
    
    if not report_file.exists():
        raise HTTPException(status_code=404, detail="Report file not found")
    
    # Determine filename for download
    assessment_data = await get_assessment_from_db(assessment_id)
    org_name = assessment_data.get('organization_name', 'Organization').replace(' ', '_')
    framework = assessment_data.get('framework', 'Framework')
    timestamp = datetime.now().strftime("%Y%m%d")
    
    filename = f"TitanAI_{report_type}_{org_name}_{framework}_{timestamp}.pdf"
    
    return FileResponse(
        path=report_file,
        filename=filename,
        media_type="application/pdf"
    )


# WebSocket endpoint for real-time updates
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for real-time assessment updates"""
    
    await manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get('type') == 'subscribe_assessment':
                assessment_id = message.get('assessment_id')
                if assessment_id:
                    manager.subscribe_to_assessment(client_id, assessment_id)
                    await manager.send_personal_message(
                        json.dumps({
                            "type": "subscribed", 
                            "assessment_id": assessment_id,
                            "timestamp": datetime.now().isoformat()
                        }),
                        client_id
                    )
            
            elif message.get('type') == 'ping':
                await manager.send_personal_message(
                    json.dumps({
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    }),
                    client_id
                )
    
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}")
        manager.disconnect(client_id)


# Dashboard endpoint
@app.get("/api/dashboard")
async def get_dashboard_data(current_user = Depends(get_current_user)):
    """Get dashboard overview data"""
    
    with infrastructure["db"].get_connection() as conn:
        cursor = conn.cursor()
        
        # Get recent assessments
        cursor.execute("""
            SELECT a.id, a.framework, a.status, a.overall_score, a.created_at,
                   o.name as organization_name, o.industry
            FROM assessments a
            JOIN organizations o ON a.organization_id = o.id
            ORDER BY a.created_at DESC
            LIMIT 10
        """)
        
        recent_assessments = []
        for row in cursor.fetchall():
            columns = [desc[0] for desc in cursor.description]
            recent_assessments.append(dict(zip(columns, row)))
        
        # Get summary statistics
        cursor.execute("""
            SELECT 
                COUNT(*) as total_assessments,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_assessments,
                AVG(CASE WHEN status = 'completed' THEN overall_score END) as avg_score,
                AVG(CASE WHEN status = 'completed' THEN ai_confidence_score END) as avg_ai_confidence
            FROM assessments
        """)
        
        stats = cursor.fetchone()
        stats_dict = dict(zip([desc[0] for desc in cursor.description], stats))
        
        # Get framework distribution
        cursor.execute("""
            SELECT framework, COUNT(*) as count
            FROM assessments
            GROUP BY framework
            ORDER BY count DESC
        """)
        
        framework_distribution = []
        for row in cursor.fetchall():
            framework_distribution.append({
                "framework": row[0],
                "count": row[1]
            })
    
    return {
        "recent_assessments": recent_assessments,
        "statistics": stats_dict,
        "framework_distribution": framework_distribution,
        "system_status": {
            "ollama_available": await check_ollama_status(),
            "database_connected": True,
            "vector_store_connected": True
        },
        "last_updated": datetime.now().isoformat()
    }


# Health check endpoint
@app.get("/api/health")
async def health_check():
    """System health check endpoint"""
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "components": {}
    }
    
    # Check database
    try:
        with infrastructure["db"].get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            health_status["components"]["database"] = {"status": "healthy", "type": "PostgreSQL (Neon)"}
    except Exception as e:
        health_status["components"]["database"] = {"status": "unhealthy", "error": str(e)}
        health_status["status"] = "degraded"
    
    # Check vector store
    try:
        # Test vector store connection
        test_embedding = infrastructure["vectors"].generate_embeddings(["test"])
        if test_embedding:
            health_status["components"]["vector_store"] = {"status": "healthy", "type": "Upstash Vector"}
        else:
            health_status["components"]["vector_store"] = {"status": "degraded"}
    except Exception as e:
        health_status["components"]["vector_store"] = {"status": "unhealthy", "error": str(e)}
        health_status["status"] = "degraded"
    
    # Check LLM availability
    ollama_status = await check_ollama_status()
    health_status["components"]["llm"] = {
        "status": "healthy" if ollama_status else "unhealthy",
        "type": "Ollama (Local)",
        "models": config.LLM_MODELS
    }
    
    if not ollama_status:
        health_status["status"] = "degraded"
    
    return health_status


# Background processing functions

async def process_assessment_background(
    assessment_id: str,
    assessment_request: AssessmentRequest,
    uploaded_files: List[Dict]
):
    """Background task for processing assessment with AI"""
    
    try:
        logger.info(f"Starting background processing for assessment {assessment_id}")
        
        # Phase 1: Document Processing (20% progress)
        await broadcast_progress(assessment_id, 0.1, "Document Processing", "Processing uploaded documents...")
        
        processed_documents = []
        for i, file_info in enumerate(uploaded_files):
            try:
                result = await infrastructure["processor"].process_document(
                    file_content=file_info["content"],
                    filename=file_info["original_name"],
                    assessment_id=assessment_id,
                    framework=assessment_request.framework
                )
                processed_documents.append(result)
                
                progress = 0.1 + (i + 1) / len(uploaded_files) * 0.1
                await broadcast_progress(
                    assessment_id, progress, "Document Processing",
                    f"Processed {i+1}/{len(uploaded_files)}: {file_info['original_name']}"
                )
                
            except Exception as e:
                logger.error(f"Error processing document {file_info['original_name']}: {e}")
                await broadcast_progress(
                    assessment_id, progress, "Document Processing",
                    f"Error processing {file_info['original_name']}: {str(e)}",
                    error=True
                )
            finally:
                # Clean up temp file
                try:
                    Path(file_info["temp_path"]).unlink(missing_ok=True)
                except:
                    pass
        
        # Phase 2: AI Analysis (60% progress)
        await broadcast_progress(assessment_id, 0.2, "AI Analysis", "Starting AI-powered control analysis...")
        
        # Run comprehensive framework assessment
        assessment_results = await assessment_engine.assess_full_framework(
            assessment_id=assessment_id,
            framework=assessment_request.framework,
            organization_context={
                "organization_name": assessment_request.organization_name,
                "industry": assessment_request.industry
            }
        )
        
        await broadcast_progress(assessment_id, 0.8, "AI Analysis", 
                               f"Completed analysis of {assessment_results['total_controls']} controls")
        
        # Phase 3: Report Preparation (90% progress)
        await broadcast_progress(assessment_id, 0.9, "Report Preparation", "Finalizing assessment results...")
        
        # Final completion
        await broadcast_progress(assessment_id, 1.0, "Completed", 
                               f"Assessment completed successfully. Overall score: {assessment_results.get('summary', {}).get('overall_score', 0):.1f}%")
        
        logger.info(f"Successfully completed assessment {assessment_id}")
        
    except Exception as e:
        logger.error(f"Error in background processing for {assessment_id}: {e}")
        await broadcast_progress(assessment_id, -1, "Error", f"Processing failed: {str(e)}", error=True)


async def generate_report_background(assessment_id: str, report_type: str):
    """Background task for report generation"""
    
    try:
        logger.info(f"Starting report generation for assessment {assessment_id}, type: {report_type}")
        
        await broadcast_progress(assessment_id, 0.0, "Report Generation", f"Starting {report_type} report generation...")
        
        # Generate the report
        report_path = await report_generator.generate_comprehensive_report(assessment_id, report_type)
        
        await broadcast_progress(assessment_id, 1.0, "Report Generation", f"Report generated successfully: {Path(report_path).name}")
        
        # Notify via WebSocket
        await manager.broadcast_assessment_update(assessment_id, {
            "type": "report_ready",
            "report_type": report_type,
            "report_path": report_path,
            "timestamp": datetime.now().isoformat()
        })
        
        logger.info(f"Report generation completed for {assessment_id}")
        
    except Exception as e:
        logger.error(f"Error generating report for {assessment_id}: {e}")
        await broadcast_progress(assessment_id, -1, "Report Generation", f"Report generation failed: {str(e)}", error=True)


# Helper functions

async def broadcast_progress(
    assessment_id: str,
    progress: float,
    phase: str,
    message: str,
    error: bool = False
):
    """Broadcast progress update via WebSocket"""
    
    update_message = {
        "type": "progress_update",
        "assessment_id": assessment_id,
        "progress": progress,
        "phase": phase,
        "message": message,
        "error": error,
        "timestamp": datetime.now().isoformat()
    }
    
    await manager.broadcast_assessment_update(assessment_id, update_message)


async def get_assessment_from_db(assessment_id: str) -> Optional[Dict]:
    """Get assessment data from database"""
    
    with infrastructure["db"].get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.*, o.name as organization_name, o.industry
            FROM assessments a
            JOIN organizations o ON a.organization_id = o.id
            WHERE a.id = %s
        """, (assessment_id,))
        
        result = cursor.fetchone()
        if result:
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, result))
    
    return None


async def get_control_assessments_from_db(assessment_id: str) -> List[Dict]:
    """Get control assessments from database"""
    
    with infrastructure["db"].get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM control_assessments
            WHERE assessment_id = %s
            ORDER BY control_id
        """, (assessment_id,))
        
        results = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        assessments = []
        for result in results:
            assessment_dict = dict(zip(columns, result))
            
            # Parse JSON fields
            for json_field in ['ai_analysis', 'ai_gaps_identified', 'ai_recommendations', 'ai_questions']:
                if assessment_dict.get(json_field):
                    try:
                        if isinstance(assessment_dict[json_field], str):
                            assessment_dict[json_field] = json.loads(assessment_dict[json_field])
                    except:
                        pass
            
            assessments.append(assessment_dict)
        
        return assessments


async def get_processing_details(assessment_id: str) -> Dict:
    """Get detailed processing information"""
    
    # This would query processing queue and status tables
    # For now, return basic information
    return {
        "progress": 1.0,
        "current_phase": "completed",
        "phase_details": {},
        "estimated_completion": None,
        "errors": [],
        "warnings": [],
        "controls_processed": 0
    }


async def check_ollama_status() -> bool:
    """Check if Ollama service is available"""
    
    try:
        models = llm_manager.client.list()
        return len(models.get('models', [])) > 0
    except:
        return False


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "timestamp": datetime.now().isoformat()}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "timestamp": datetime.now().isoformat()}
    )


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    
    logger.info("TitanAI Professional Web Interface starting...")
    
    # Create necessary directories
    config.UPLOAD_DIR.mkdir(exist_ok=True, parents=True)
    config.REPORTS_DIR.mkdir(exist_ok=True, parents=True)
    config.TEMP_DIR.mkdir(exist_ok=True, parents=True)
    
    # Verify core components
    try:
        # Test database connection
        with infrastructure["db"].get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT version()")
            db_version = cursor.fetchone()[0]
            logger.info(f"Database connected: {db_version[:50]}...")
        
        # Test vector store
        test_embeddings = infrastructure["vectors"].generate_embeddings(["startup test"])
        logger.info(f"Vector store ready: {len(test_embeddings[0])} dimensions")
        
        # Test LLM
        ollama_available = await check_ollama_status()
        logger.info(f"LLM available: {ollama_available}")
        
        logger.info("✅ All components initialized successfully")
        
    except Exception as e:
        logger.error(f"❌ Startup error: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown"""
    
    logger.info("TitanAI shutting down...")
    
    # Close database connections
    if hasattr(infrastructure["db"], 'pool'):
        infrastructure["db"].pool.closeall()
    
    # Clean up temporary files
    try:
        import shutil
        if config.TEMP_DIR.exists():
            shutil.rmtree(config.TEMP_DIR)
    except:
        pass
    
    logger.info("Shutdown complete")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "phase4_enhanced.web_interface:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG,
        log_level="info" if config.DEBUG else "warning"
    )