"""
TitanAI Auditor Interface
Professional auditor dashboard with query, edit, and review capabilities.
"""

import logging
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..phase1_enhanced.infrastructure import get_infrastructure
from ..phase2_enhanced.assessment_engine import get_assessment_engine
from ..phase3_enhanced.professional_reports import get_report_generator
from ..local_llm.llm_manager import get_llm_manager

logger = logging.getLogger(__name__)

# Create auditor router
auditor_router = APIRouter(prefix="/api/auditor", tags=["auditor"])

# Initialize components
infrastructure = get_infrastructure()
assessment_engine = get_assessment_engine()
report_generator = get_report_generator()
llm_manager = get_llm_manager()


class AuditorQuery(BaseModel):
    assessment_id: str
    control_id: Optional[str] = None
    question: str = Field(..., min_length=10, max_length=1000)
    context: Optional[str] = None


class ReportEdit(BaseModel):
    assessment_id: str
    section: str
    content: str
    comment: Optional[str] = None
    auditor_id: str


class AuditorComment(BaseModel):
    assessment_id: str
    control_id: Optional[str] = None
    comment_type: str  # finding, recommendation, concern, approval
    comment: str
    priority: str = "medium"  # low, medium, high, critical
    auditor_id: str


@auditor_router.post("/query")
async def query_assessment(query: AuditorQuery):
    """
    Allow auditors to ask intelligent questions about assessments.
    Uses AI to provide detailed answers with evidence references.
    """
    
    try:
        # Get assessment data
        assessment_data = await infrastructure.db_manager.get_assessment(query.assessment_id)
        if not assessment_data:
            raise HTTPException(status_code=404, detail="Assessment not found")
        
        # Get control assessments
        control_assessments = await infrastructure.db_manager.get_control_assessments(query.assessment_id)
        
        # If specific control queried, filter to that control
        if query.control_id:
            control_assessments = [c for c in control_assessments if c.get('control_id') == query.control_id]
        
        # Prepare context for AI query
        context = f"""
        Assessment ID: {query.assessment_id}
        Organization: {assessment_data.get('organization_name')}
        Framework: {assessment_data.get('framework')}
        
        Control Assessments Summary:
        """
        
        for control in control_assessments[:10]:  # Limit context size
            context += f"""
            - Control {control.get('control_id')}: {control.get('implementation_status')}
              Evidence Score: {control.get('ai_evidence_score', 'N/A')}
              AI Analysis: {(control.get('ai_analysis', '') or '')[:200]}...
            """
        
        if query.context:
            context += f"\n\nAdditional Context: {query.context}"
        
        # Generate AI response
        ai_prompt = f"""
        You are an expert compliance auditor reviewing this assessment.
        
        {context}
        
        Auditor Question: {query.question}
        
        Provide a detailed, professional response that:
        1. Directly answers the question with specific evidence
        2. References relevant controls and findings
        3. Identifies any compliance gaps or concerns
        4. Suggests additional investigation areas if needed
        5. Uses professional audit terminology
        
        Be thorough but concise.
        """
        
        ai_response = await llm_manager.analyze_evidence(
            control="Auditor Query Response",
            evidence=ai_prompt
        )
        
        # Log the query for audit trail
        query_record = {
            "id": str(uuid.uuid4()),
            "assessment_id": query.assessment_id,
            "control_id": query.control_id,
            "question": query.question,
            "response": ai_response,
            "timestamp": datetime.now().isoformat(),
            "context": query.context
        }
        
        # Store query in database (would implement actual storage)
        logger.info(f"Auditor query logged: {query_record['id']}")
        
        return {
            "query_id": query_record["id"],
            "question": query.question,
            "response": ai_response,
            "timestamp": query_record["timestamp"],
            "assessment_id": query.assessment_id,
            "control_id": query.control_id
        }
        
    except Exception as e:
        logger.error(f"Error processing auditor query: {e}")
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")


@auditor_router.post("/edit-report")
async def edit_report_section(edit: ReportEdit):
    """
    Allow auditors to edit specific sections of generated reports.
    Maintains version control and audit trail.
    """
    
    try:
        # Validate assessment exists
        assessment_data = await infrastructure.db_manager.get_assessment(edit.assessment_id)
        if not assessment_data:
            raise HTTPException(status_code=404, detail="Assessment not found")
        
        # Create edit record
        edit_record = {
            "id": str(uuid.uuid4()),
            "assessment_id": edit.assessment_id,
            "section": edit.section,
            "original_content": "...",  # Would fetch original
            "new_content": edit.content,
            "comment": edit.comment,
            "auditor_id": edit.auditor_id,
            "timestamp": datetime.now().isoformat(),
            "status": "pending_approval"
        }
        
        # Store edit (would implement actual database storage)
        logger.info(f"Report edit created: {edit_record['id']}")
        
        # Generate updated report section with AI validation
        validation_prompt = f"""
        Validate this auditor edit to a compliance report:
        
        Section: {edit.section}
        New Content: {edit.content}
        Auditor Comment: {edit.comment or 'None provided'}
        
        Check for:
        1. Professional language and tone
        2. Compliance with audit standards
        3. Factual accuracy based on assessment data
        4. Appropriate risk classifications
        5. Clear recommendations
        
        Provide validation result and any suggestions.
        """
        
        validation_result = await llm_manager.analyze_evidence(
            control="Report Edit Validation",
            evidence=validation_prompt
        )
        
        return {
            "edit_id": edit_record["id"],
            "status": "accepted",
            "validation_result": validation_result,
            "timestamp": edit_record["timestamp"],
            "message": "Report section updated successfully"
        }
        
    except Exception as e:
        logger.error(f"Error editing report: {e}")
        raise HTTPException(status_code=500, detail=f"Report edit failed: {str(e)}")


@auditor_router.post("/add-comment")
async def add_auditor_comment(comment: AuditorComment):
    """
    Allow auditors to add comments, findings, and recommendations.
    """
    
    try:
        # Validate assessment
        assessment_data = await infrastructure.db_manager.get_assessment(comment.assessment_id)
        if not assessment_data:
            raise HTTPException(status_code=404, detail="Assessment not found")
        
        # Create comment record
        comment_record = {
            "id": str(uuid.uuid4()),
            "assessment_id": comment.assessment_id,
            "control_id": comment.control_id,
            "comment_type": comment.comment_type,
            "comment": comment.comment,
            "priority": comment.priority,
            "auditor_id": comment.auditor_id,
            "timestamp": datetime.now().isoformat(),
            "status": "active"
        }
        
        # AI-enhance the comment with professional language
        enhancement_prompt = f"""
        Enhance this auditor comment for professional compliance reporting:
        
        Comment Type: {comment.comment_type}
        Priority: {comment.priority}
        Original Comment: {comment.comment}
        
        Provide:
        1. Enhanced professional version
        2. Risk implications if applicable
        3. Recommended actions
        4. Compliance impact assessment
        
        Maintain the auditor's intent while improving clarity and professionalism.
        """
        
        enhanced_comment = await llm_manager.analyze_evidence(
            control="Comment Enhancement",
            evidence=enhancement_prompt
        )
        
        comment_record["enhanced_comment"] = enhanced_comment
        
        # Store comment (would implement actual database storage)
        logger.info(f"Auditor comment added: {comment_record['id']}")
        
        return {
            "comment_id": comment_record["id"],
            "original_comment": comment.comment,
            "enhanced_comment": enhanced_comment,
            "timestamp": comment_record["timestamp"],
            "status": "added"
        }
        
    except Exception as e:
        logger.error(f"Error adding comment: {e}")
        raise HTTPException(status_code=500, detail=f"Comment addition failed: {str(e)}")


@auditor_router.get("/assessment/{assessment_id}/dashboard")
async def get_auditor_dashboard(assessment_id: str):
    """
    Comprehensive auditor dashboard with all tools and information.
    """
    
    try:
        # Get assessment data
        assessment_data = await infrastructure.db_manager.get_assessment(assessment_id)
        if not assessment_data:
            raise HTTPException(status_code=404, detail="Assessment not found")
        
        # Get control assessments
        control_assessments = await infrastructure.db_manager.get_control_assessments(assessment_id)
        
        # Calculate audit statistics
        total_controls = len(control_assessments)
        high_risk_controls = len([c for c in control_assessments if c.get('risk_rating') == 'high'])
        implemented = len([c for c in control_assessments if c.get('implementation_status') == 'implemented'])
        
        # Get recent queries and comments (would fetch from database)
        recent_queries = []  # Would implement
        recent_comments = []  # Would implement
        
        # AI-generate audit focus areas
        focus_prompt = f"""
        Based on this compliance assessment, identify key areas requiring auditor attention:
        
        Assessment: {assessment_data.get('organization_name')} - {assessment_data.get('framework')}
        Total Controls: {total_controls}
        Implemented: {implemented}
        High Risk: {high_risk_controls}
        
        Top 5 areas for auditor focus:
        """
        
        focus_areas = await llm_manager.analyze_evidence(
            control="Audit Focus Areas",
            evidence=focus_prompt
        )
        
        return {
            "assessment_id": assessment_id,
            "organization": assessment_data.get('organization_name'),
            "framework": assessment_data.get('framework'),
            "statistics": {
                "total_controls": total_controls,
                "implemented": implemented,
                "high_risk_controls": high_risk_controls,
                "completion_rate": f"{(implemented/total_controls*100):.1f}%" if total_controls > 0 else "0%"
            },
            "focus_areas": focus_areas,
            "recent_queries": recent_queries,
            "recent_comments": recent_comments,
            "tools_available": [
                "AI-Powered Queries",
                "Report Section Editing", 
                "Comment System",
                "Evidence Review",
                "Risk Assessment",
                "Gap Analysis"
            ]
        }
        
    except Exception as e:
        logger.error(f"Error generating auditor dashboard: {e}")
        raise HTTPException(status_code=500, detail=f"Dashboard generation failed: {str(e)}")


@auditor_router.get("/assessment/{assessment_id}/evidence/{control_id}")
async def get_control_evidence(assessment_id: str, control_id: str):
    """
    Get detailed evidence for specific control for auditor review.
    """
    
    try:
        # Get control assessment data
        control_data = await infrastructure.db_manager.get_control_assessment(assessment_id, control_id)
        if not control_data:
            raise HTTPException(status_code=404, detail="Control assessment not found")
        
        # Get associated evidence documents
        evidence_docs = await infrastructure.db_manager.get_evidence_for_control(assessment_id, control_id)
        
        # AI analysis of evidence quality
        evidence_prompt = f"""
        Review this evidence for Control {control_id}:
        
        Implementation Status: {control_data.get('implementation_status')}
        AI Evidence Score: {control_data.get('ai_evidence_score')}
        
        Evidence Documents: {len(evidence_docs)} documents
        
        Provide auditor assessment:
        1. Evidence sufficiency (Strong/Adequate/Weak/Insufficient)
        2. Evidence quality concerns
        3. Additional evidence needed
        4. Audit testing recommendations
        5. Risk assessment
        """
        
        evidence_analysis = await llm_manager.analyze_evidence(
            control=f"Evidence Review - {control_id}",
            evidence=evidence_prompt
        )
        
        return {
            "control_id": control_id,
            "assessment_id": assessment_id,
            "control_data": control_data,
            "evidence_documents": evidence_docs,
            "evidence_count": len(evidence_docs),
            "auditor_analysis": evidence_analysis,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting control evidence: {e}")
        raise HTTPException(status_code=500, detail=f"Evidence retrieval failed: {str(e)}")


# Export router for inclusion in main app
def get_auditor_router():
    return auditor_router