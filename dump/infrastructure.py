"""
TitanAI Phase 1 Enhanced: Infrastructure with Local AI
Uses your existing Neon PostgreSQL and Upstash Vector with local LLM processing.
Zero AI costs while maintaining professional infrastructure.
"""

import logging
import json
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from contextlib import contextmanager
import asyncio

# Database
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from psycopg2.pool import ThreadedConnectionPool
from sqlalchemy import create_engine, text

# Vector operations
from upstash_vector import Index, Vector
from sentence_transformers import SentenceTransformer
import numpy as np

# Document processing
import pypdf
from docx import Document as DocxDocument
from PIL import Image
import pytesseract

# Local LLM
from ..local_llm.llm_manager import LocalLLMManager, get_llm_manager
from ..config_enhanced import config

logger = logging.getLogger(__name__)


class EnhancedDatabaseManager:
    """
    Enhanced database manager using your existing Neon PostgreSQL.
    Includes complete schema with knowledge graph support.
    """
    
    def __init__(self):
        """Initialize with your Neon PostgreSQL"""
        self.connection_string = config.NEON_CONNECTION_STRING
        
        # Create connection pool for concurrent access
        self.pool = ThreadedConnectionPool(
            config.DB_MIN_CONNECTIONS,
            config.DB_MAX_CONNECTIONS,
            self.connection_string
        )
        
        # SQLAlchemy engine for complex queries
        self.engine = create_engine(self.connection_string, echo=False)
        
        # Initialize schema
        self._initialize_schema()
        
        logger.info("Enhanced Database Manager initialized with Neon PostgreSQL")
    
    @contextmanager
    def get_connection(self):
        """Get connection from pool"""
        conn = self.pool.getconn()
        try:
            yield conn
        finally:
            self.pool.putconn(conn)
    
    def _initialize_schema(self):
        """Create all required tables with enhanced schema"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Enable extensions
            cursor.execute("""
                CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
                CREATE EXTENSION IF NOT EXISTS "pg_trgm";
            """)
            
            # Organizations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS organizations (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    name VARCHAR(255) NOT NULL UNIQUE,
                    industry VARCHAR(100),
                    size VARCHAR(50),
                    country VARCHAR(100) DEFAULT 'Australia',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata JSONB DEFAULT '{}'
                );
                
                CREATE INDEX IF NOT EXISTS idx_org_name 
                ON organizations USING gin (name gin_trgm_ops);
            """)
            
            # Enhanced assessments table with AI fields
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS assessments (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
                    framework VARCHAR(50) NOT NULL,
                    assessment_type VARCHAR(50) DEFAULT 'initial',
                    status VARCHAR(50) DEFAULT 'draft',
                    
                    -- Statistics
                    total_controls INTEGER DEFAULT 0,
                    controls_implemented INTEGER DEFAULT 0,
                    controls_partial INTEGER DEFAULT 0,
                    controls_not_implemented INTEGER DEFAULT 0,
                    controls_not_applicable INTEGER DEFAULT 0,
                    overall_score DECIMAL(5,2) DEFAULT 0.0,
                    maturity_level VARCHAR(50),
                    
                    -- AI Analysis Fields
                    ai_confidence_score DECIMAL(3,2),
                    ai_analysis_summary TEXT,
                    ai_recommendations JSONB,
                    ai_risk_assessment JSONB,
                    
                    -- Timestamps
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    
                    metadata JSONB DEFAULT '{}'
                );
                
                CREATE INDEX IF NOT EXISTS idx_assessment_org 
                ON assessments(organization_id);
            """)
            
            # Enhanced evidence documents with AI processing
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS evidence_documents (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    assessment_id UUID REFERENCES assessments(id) ON DELETE CASCADE,
                    
                    -- Document details
                    filename VARCHAR(255) NOT NULL,
                    file_hash VARCHAR(64) NOT NULL,
                    file_size_bytes BIGINT,
                    mime_type VARCHAR(100),
                    
                    -- Extracted content
                    extracted_text TEXT,
                    extraction_method VARCHAR(50),
                    extraction_confidence DECIMAL(3,2),
                    
                    -- AI Classification
                    ai_document_type VARCHAR(100),
                    ai_relevance_score DECIMAL(3,2),
                    ai_key_topics JSONB,
                    ai_applicable_controls JSONB,
                    
                    -- Embeddings metadata
                    embedding_generated BOOLEAN DEFAULT FALSE,
                    embedding_model VARCHAR(100),
                    vector_ids JSONB,  -- Store Upstash vector IDs
                    
                    -- Timestamps
                    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_at TIMESTAMP,
                    
                    metadata JSONB DEFAULT '{}',
                    
                    CONSTRAINT unique_file_per_assessment 
                    UNIQUE(assessment_id, file_hash)
                );
            """)
            
            # Enhanced control assessments with AI insights
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS control_assessments (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    assessment_id UUID REFERENCES assessments(id) ON DELETE CASCADE,
                    
                    -- Control identification
                    control_id VARCHAR(50) NOT NULL,
                    control_name VARCHAR(255),
                    control_description TEXT,
                    domain_id VARCHAR(50),
                    domain_name VARCHAR(255),
                    
                    -- Implementation assessment
                    implementation_status VARCHAR(50),
                    maturity_level VARCHAR(50),
                    confidence_score DECIMAL(3,2),
                    
                    -- AI Analysis
                    ai_analysis JSONB,
                    ai_evidence_quality VARCHAR(50),
                    ai_confidence DECIMAL(3,2),
                    ai_reasoning TEXT,
                    
                    -- Evidence linkage
                    evidence_count INTEGER DEFAULT 0,
                    evidence_documents JSONB,
                    evidence_summary TEXT,
                    
                    -- AI-Generated Content
                    ai_gaps_identified JSONB,
                    ai_recommendations JSONB,
                    ai_questions JSONB,
                    
                    -- Impact analysis
                    business_impact VARCHAR(50),
                    security_impact VARCHAR(50),
                    brand_impact VARCHAR(50),
                    risk_rating VARCHAR(50),
                    
                    -- Validation
                    requires_validation BOOLEAN DEFAULT FALSE,
                    validation_reason TEXT,
                    auditor_notes TEXT,
                    stakeholder_owner VARCHAR(255),
                    
                    assessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Knowledge graph for frameworks
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kg_nodes (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    node_type VARCHAR(50) NOT NULL,
                    node_key VARCHAR(100) UNIQUE NOT NULL,
                    framework VARCHAR(50),
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    parent_node_id UUID REFERENCES kg_nodes(id),
                    hierarchy_level INTEGER DEFAULT 0,
                    properties JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_kg_node_key ON kg_nodes(node_key);
                CREATE INDEX IF NOT EXISTS idx_kg_framework ON kg_nodes(framework);
            """)
            
            # Knowledge graph edges
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kg_edges (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    source_node_id UUID REFERENCES kg_nodes(id) ON DELETE CASCADE,
                    target_node_id UUID REFERENCES kg_nodes(id) ON DELETE CASCADE,
                    relationship_type VARCHAR(50) NOT NULL,
                    weight DECIMAL(3,2) DEFAULT 1.0,
                    properties JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    CONSTRAINT unique_edge 
                    UNIQUE(source_node_id, target_node_id, relationship_type)
                );
            """)
            
            # AI Processing Queue
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_processing_queue (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    assessment_id UUID REFERENCES assessments(id),
                    document_id UUID REFERENCES evidence_documents(id),
                    task_type VARCHAR(50) NOT NULL,
                    priority INTEGER DEFAULT 5,
                    status VARCHAR(50) DEFAULT 'pending',
                    payload JSONB,
                    result JSONB,
                    error TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_queue_status 
                ON ai_processing_queue(status, priority DESC);
            """)
            
            conn.commit()
            logger.info("Database schema initialized successfully")
    
    async def create_assessment(
        self,
        organization_name: str,
        framework: str,
        industry: str = None
    ) -> str:
        """Create new assessment with AI capabilities"""
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get or create organization
            cursor.execute("""
                INSERT INTO organizations (name, industry)
                VALUES (%s, %s)
                ON CONFLICT (name) DO UPDATE
                SET industry = COALESCE(EXCLUDED.industry, organizations.industry)
                RETURNING id
            """, (organization_name, industry))
            
            org_id = cursor.fetchone()[0]
            
            # Create assessment
            cursor.execute("""
                INSERT INTO assessments (organization_id, framework)
                VALUES (%s, %s)
                RETURNING id
            """, (org_id, framework))
            
            assessment_id = cursor.fetchone()[0]
            conn.commit()
            
            logger.info(f"Created assessment {assessment_id} for {organization_name}")
            return str(assessment_id)


class EnhancedVectorManager:
    """
    Enhanced vector manager using your existing Upstash Vector
    with local embedding generation for zero AI costs.
    """
    
    def __init__(self):
        """Initialize with Upstash Vector and local embeddings"""
        
        # Upstash Vector for storage
        self.index = Index(
            url=config.UPSTASH_URL,
            token=config.UPSTASH_TOKEN
        )
        
        # Local embedding model (no API costs!)
        self.embedding_model = SentenceTransformer(config.EMBEDDING_MODEL)
        self.embedding_dimension = config.EMBEDDING_DIMENSION
        
        logger.info("Enhanced Vector Manager initialized with Upstash + local embeddings")
    
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings locally using sentence-transformers"""
        
        if not texts:
            return []
        
        # Generate embeddings locally (FREE!)
        embeddings = self.embedding_model.encode(
            texts,
            convert_to_numpy=True,
            batch_size=config.EMBEDDING_BATCH_SIZE,
            show_progress_bar=len(texts) > 10
        )
        
        return embeddings.tolist()
    
    async def index_document(
        self,
        document_id: str,
        text_chunks: List[str],
        metadata: Dict[str, Any]
    ) -> List[str]:
        """Index document chunks in Upstash Vector"""
        
        # Generate embeddings locally
        embeddings = self.generate_embeddings(text_chunks)
        
        # Create vectors for Upstash
        vectors = []
        vector_ids = []
        
        for i, (chunk, embedding) in enumerate(zip(text_chunks, embeddings)):
            vector_id = f"{document_id}_chunk_{i}"
            vector_ids.append(vector_id)
            
            vectors.append(Vector(
                id=vector_id,
                vector=embedding,
                metadata={
                    **metadata,
                    "document_id": document_id,
                    "chunk_index": i,
                    "chunk_text": chunk[:500]  # Store preview
                }
            ))
        
        # Batch upsert to Upstash
        if vectors:
            self.index.upsert(vectors=vectors)
            logger.info(f"Indexed {len(vectors)} chunks for document {document_id}")
        
        return vector_ids
    
    async def search_similar(
        self,
        query: str,
        framework: str = None,
        top_k: int = 10
    ) -> List[Dict]:
        """Search for similar content using local embeddings + Upstash"""
        
        # Generate query embedding locally
        query_embedding = self.generate_embeddings([query])[0]
        
        # Build filter for Upstash
        filter_dict = {}
        if framework:
            filter_dict["framework"] = framework
        
        # Search in Upstash
        results = self.index.query(
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True,
            filter=filter_dict if filter_dict else None
        )
        
        # Format results
        similar_items = []
        for result in results:
            similar_items.append({
                "id": result.id,
                "score": result.score,
                "document_id": result.metadata.get("document_id"),
                "chunk_text": result.metadata.get("chunk_text"),
                "metadata": result.metadata
            })
        
        return similar_items


class EnhancedDocumentProcessor:
    """
    Enhanced document processor with AI classification and analysis.
    Uses local LLM for intelligent processing.
    """
    
    def __init__(self, db_manager: EnhancedDatabaseManager, 
                 vector_manager: EnhancedVectorManager):
        """Initialize with database and vector managers"""
        
        self.db = db_manager
        self.vectors = vector_manager
        self.llm = get_llm_manager()
        
        logger.info("Enhanced Document Processor initialized with AI capabilities")
    
    async def process_document(
        self,
        file_content: bytes,
        filename: str,
        assessment_id: str,
        framework: str
    ) -> Dict[str, Any]:
        """Process document with AI enhancement"""
        
        # Extract text
        extraction_result = self._extract_text(file_content, filename)
        
        if not extraction_result["success"]:
            return extraction_result
        
        extracted_text = extraction_result["text"]
        
        # AI Classification using local LLM
        classification = await self.llm.classify_document(extracted_text, framework)
        
        # Create text chunks for indexing
        chunks = self._create_chunks(extracted_text)
        
        # Store in database
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Calculate file hash
            file_hash = hashlib.sha256(file_content).hexdigest()
            
            cursor.execute("""
                INSERT INTO evidence_documents (
                    assessment_id, filename, file_hash, file_size_bytes,
                    mime_type, extracted_text, extraction_method,
                    extraction_confidence, ai_document_type, ai_relevance_score,
                    ai_key_topics, ai_applicable_controls
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                assessment_id, filename, file_hash, len(file_content),
                extraction_result.get("mime_type"), extracted_text,
                extraction_result.get("method"), extraction_result.get("confidence"),
                classification.get("document_type"), classification.get("relevance_score"),
                Json(classification.get("key_topics", [])),
                Json(classification.get("applicable_controls", []))
            ))
            
            document_id = str(cursor.fetchone()[0])
            
            # Index in vector database
            vector_ids = await self.vectors.index_document(
                document_id, 
                [chunk["text"] for chunk in chunks],
                {
                    "assessment_id": assessment_id,
                    "framework": framework,
                    "document_type": classification.get("document_type")
                }
            )
            
            # Update document with vector IDs
            cursor.execute("""
                UPDATE evidence_documents
                SET embedding_generated = true,
                    embedding_model = %s,
                    vector_ids = %s,
                    processed_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (config.EMBEDDING_MODEL, Json(vector_ids), document_id))
            
            conn.commit()
        
        return {
            "success": True,
            "document_id": document_id,
            "filename": filename,
            "chunks_created": len(chunks),
            "classification": classification,
            "extraction_confidence": extraction_result.get("confidence")
        }
    
    def _extract_text(self, content: bytes, filename: str) -> Dict[str, Any]:
        """Extract text from various file formats"""
        
        file_ext = filename.lower().split('.')[-1]
        
        try:
            if file_ext == 'pdf':
                return self._extract_pdf(content)
            elif file_ext in ['docx', 'doc']:
                return self._extract_docx(content)
            elif file_ext in ['txt', 'csv']:
                return self._extract_text_file(content)
            elif file_ext in ['png', 'jpg', 'jpeg']:
                return self._extract_image_ocr(content)
            else:
                return {
                    "success": False,
                    "error": f"Unsupported file type: {file_ext}"
                }
        except Exception as e:
            logger.error(f"Error extracting text from {filename}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _extract_pdf(self, content: bytes) -> Dict[str, Any]:
        """Extract text from PDF"""
        import io
        
        pdf_file = io.BytesIO(content)
        pdf_reader = pypdf.PdfReader(pdf_file)
        
        text_parts = []
        for page in pdf_reader.pages:
            text_parts.append(page.extract_text())
        
        return {
            "success": True,
            "text": "\n\n".join(text_parts),
            "method": "pdf_extraction",
            "confidence": 0.9,
            "mime_type": "application/pdf"
        }
    
    def _extract_docx(self, content: bytes) -> Dict[str, Any]:
        """Extract text from Word document"""
        import io
        
        doc = DocxDocument(io.BytesIO(content))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        
        return {
            "success": True,
            "text": "\n\n".join(paragraphs),
            "method": "docx_extraction",
            "confidence": 0.95,
            "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        }
    
    def _extract_text_file(self, content: bytes) -> Dict[str, Any]:
        """Extract text from plain text files"""
        
        try:
            text = content.decode('utf-8')
        except:
            text = content.decode('latin-1', errors='ignore')
        
        return {
            "success": True,
            "text": text,
            "method": "text_extraction",
            "confidence": 1.0,
            "mime_type": "text/plain"
        }
    
    def _extract_image_ocr(self, content: bytes) -> Dict[str, Any]:
        """Extract text from image using OCR"""
        import io
        
        image = Image.open(io.BytesIO(content))
        text = pytesseract.image_to_string(image)
        
        confidence = 0.7 if len(text) > 50 else 0.5
        
        return {
            "success": True,
            "text": text,
            "method": "ocr_extraction",
            "confidence": confidence,
            "mime_type": "image/*"
        }
    
    def _create_chunks(self, text: str, chunk_size: int = 1000) -> List[Dict]:
        """Create overlapping text chunks"""
        
        chunks = []
        sentences = text.split('. ')
        current_chunk = []
        current_size = 0
        
        for sentence in sentences:
            sentence_size = len(sentence)
            
            if current_size + sentence_size > chunk_size and current_chunk:
                chunks.append({
                    "text": '. '.join(current_chunk) + '.',
                    "index": len(chunks)
                })
                
                # Keep last 2 sentences for overlap
                current_chunk = current_chunk[-2:] if len(current_chunk) > 2 else current_chunk[-1:]
                current_size = sum(len(s) for s in current_chunk)
            
            current_chunk.append(sentence)
            current_size += sentence_size
        
        # Add final chunk
        if current_chunk:
            chunks.append({
                "text": '. '.join(current_chunk) + '.',
                "index": len(chunks)
            })
        
        return chunks


# Singleton instances
_db_manager = None
_vector_manager = None
_doc_processor = None

def get_infrastructure():
    """Get or create infrastructure instances"""
    global _db_manager, _vector_manager, _doc_processor
    
    if _db_manager is None:
        _db_manager = EnhancedDatabaseManager()
        _vector_manager = EnhancedVectorManager()
        _doc_processor = EnhancedDocumentProcessor(_db_manager, _vector_manager)
    
    return {
        "db": _db_manager,
        "vectors": _vector_manager,
        "processor": _doc_processor
    }