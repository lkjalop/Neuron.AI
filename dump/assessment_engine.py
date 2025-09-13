"""
TitanAI Phase 2 Enhanced: AI-Powered Assessment Engine
Implements intelligent compliance assessment using local LLMs.
Zero API costs with professional-grade analysis capabilities.
"""

import logging
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import statistics
import re

from ..phase1_enhanced.infrastructure import get_infrastructure
from ..local_llm.llm_manager import get_llm_manager
from ..config_enhanced import config

logger = logging.getLogger(__name__)


class ImplementationStatus(Enum):
    """Implementation status levels"""
    IMPLEMENTED = "implemented"
    PARTIALLY_IMPLEMENTED = "partially_implemented"
    NOT_IMPLEMENTED = "not_implemented"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class MaturityLevel(Enum):
    """Maturity assessment levels"""
    OPTIMIZING = 5
    MANAGED = 4
    DEFINED = 3
    DEVELOPING = 2
    INITIAL = 1
    NONE = 0


class ImpactLevel(Enum):
    """Risk impact levels"""
    CRITICAL = "critical"
    HIGH = "high"  
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


@dataclass
class ControlAssessment:
    """Complete AI-powered control assessment"""
    control_id: str
    control_name: str
    framework: str
    
    # AI Analysis Results
    implementation_status: ImplementationStatus
    ai_confidence: float
    ai_reasoning: str
    
    # Evidence Analysis
    evidence_count: int
    evidence_quality: str
    evidence_summary: str
    
    # AI-Generated Content
    gaps_identified: List[str]
    recommendations: List[str]
    stakeholder_questions: List[str]
    
    # Risk Assessment
    business_impact: ImpactLevel
    security_impact: ImpactLevel
    brand_impact: ImpactLevel
    risk_rating: str
    
    # Maturity Assessment
    maturity_level: MaturityLevel
    maturity_reasoning: str
    
    # Validation Requirements
    requires_validation: bool
    validation_reason: str
    
    # Metadata
    assessed_at: datetime
    processing_time: float
    model_used: str


class EnhancedAssessmentEngine:
    """
    AI-powered compliance assessment engine using local LLMs.
    Provides intelligent analysis without API costs.
    """
    
    def __init__(self):
        """Initialize assessment engine"""
        
        self.infrastructure = get_infrastructure()
        self.llm = get_llm_manager()
        
        # Load compliance frameworks knowledge
        self.frameworks_knowledge = self._load_frameworks_knowledge()
        
        # Assessment configuration
        self.confidence_thresholds = {
            "high": 0.8,
            "medium": 0.6, 
            "low": 0.4
        }
        
        logger.info("Enhanced Assessment Engine initialized with AI capabilities")
    
    async def assess_control(
        self,
        assessment_id: str,
        control_id: str,
        framework: str,
        organization_context: Dict[str, Any] = None
    ) -> ControlAssessment:
        """
        Perform AI-powered control assessment.
        Uses local LLM for intelligent analysis.
        """
        
        start_time = datetime.now()
        logger.info(f"Starting AI assessment for control {control_id}")
        
        # Get control details from knowledge graph
        control_details = self._get_control_details(framework, control_id)
        
        # Find relevant evidence using vector search
        evidence_results = await self._find_evidence(
            assessment_id, control_id, framework, control_details
        )
        
        # Perform AI analysis of evidence
        ai_analysis = await self._ai_analyze_evidence(
            control_details, evidence_results, framework
        )
        
        # Generate AI insights
        gaps_and_recommendations = await self._ai_generate_insights(
            control_details, ai_analysis, evidence_results
        )
        
        # Generate stakeholder questions using AI
        questions = await self._ai_generate_questions(
            control_id, control_details, ai_analysis, gaps_and_recommendations
        )
        
        # Assess impacts and risks
        impact_assessment = await self._ai_assess_impacts(
            control_details, ai_analysis, organization_context or {}
        )
        
        # Determine maturity level
        maturity_assessment = self._assess_maturity(ai_analysis, evidence_results)
        
        # Determine validation requirements
        validation_needed, validation_reason = self._determine_validation(
            ai_analysis, evidence_results, control_details
        )
        
        # Create comprehensive assessment result
        assessment = ControlAssessment(
            control_id=control_id,
            control_name=control_details.get("name", "Unknown Control"),
            framework=framework,
            
            # AI Analysis
            implementation_status=ImplementationStatus(ai_analysis["implementation_status"]),
            ai_confidence=ai_analysis["confidence_score"],
            ai_reasoning=ai_analysis["reasoning"],
            
            # Evidence
            evidence_count=len(evidence_results),
            evidence_quality=ai_analysis["evidence_quality"],
            evidence_summary=self._summarize_evidence(evidence_results),
            
            # AI-Generated Insights
            gaps_identified=gaps_and_recommendations["gaps"],
            recommendations=gaps_and_recommendations["recommendations"],
            stakeholder_questions=questions,
            
            # Risk Assessment
            business_impact=ImpactLevel(impact_assessment["business_impact"]),
            security_impact=ImpactLevel(impact_assessment["security_impact"]),
            brand_impact=ImpactLevel(impact_assessment["brand_impact"]),
            risk_rating=impact_assessment["risk_rating"],
            
            # Maturity
            maturity_level=MaturityLevel(maturity_assessment["level"]),
            maturity_reasoning=maturity_assessment["reasoning"],
            
            # Validation
            requires_validation=validation_needed,
            validation_reason=validation_reason,
            
            # Metadata
            assessed_at=start_time,
            processing_time=(datetime.now() - start_time).total_seconds(),
            model_used=config.get_llm_model("analysis")
        )
        
        # Store assessment in database
        await self._store_assessment(assessment_id, assessment)
        
        logger.info(f"Completed AI assessment for {control_id} in {assessment.processing_time:.2f}s")
        return assessment
    
    async def _find_evidence(
        self,
        assessment_id: str,
        control_id: str,
        framework: str,
        control_details: Dict
    ) -> List[Dict]:
        """Find relevant evidence using vector similarity search"""
        
        # Create search queries based on control details
        search_queries = [
            control_details.get("name", ""),
            control_details.get("description", ""),
            f"{framework} {control_id}",
            *control_details.get("keywords", [])
        ]
        
        all_evidence = []
        
        # Search for each query
        for query in search_queries:
            if query.strip():
                results = await self.infrastructure["vectors"].search_similar(
                    query=query,
                    framework=framework,
                    top_k=5
                )
                all_evidence.extend(results)
        
        # Remove duplicates and rank by relevance
        unique_evidence = self._deduplicate_evidence(all_evidence)
        
        # Filter by minimum relevance threshold
        relevant_evidence = [
            e for e in unique_evidence 
            if e["score"] > 0.3  # Minimum similarity threshold
        ]
        
        return relevant_evidence[:10]  # Top 10 most relevant pieces
    
    async def _ai_analyze_evidence(
        self,
        control_details: Dict,
        evidence_results: List[Dict],
        framework: str
    ) -> Dict[str, Any]:
        """Use AI to analyze evidence against control requirements"""
        
        if not evidence_results:
            return {
                "implementation_status": "unknown",
                "confidence_score": 0.1,
                "evidence_quality": "none",
                "reasoning": "No evidence found for this control",
                "key_findings": []
            }
        
        # Combine evidence texts
        evidence_text = "\n\n---\n\n".join([
            e["chunk_text"] for e in evidence_results[:5]  # Top 5 pieces
            if e.get("chunk_text")
        ])
        
        # Use AI to analyze evidence
        analysis = await self.llm.analyze_evidence(
            evidence_text=evidence_text,
            control_description=control_details.get("description", ""),
            framework=framework
        )
        
        return analysis
    
    async def _ai_generate_insights(
        self,
        control_details: Dict,
        ai_analysis: Dict,
        evidence_results: List[Dict]
    ) -> Dict[str, List[str]]:
        """Generate AI-powered gaps and recommendations"""
        
        # Prepare context for AI
        context = {
            "control_name": control_details.get("name", ""),
            "control_description": control_details.get("description", ""),
            "implementation_status": ai_analysis.get("implementation_status", "unknown"),
            "confidence": ai_analysis.get("confidence_score", 0),
            "evidence_count": len(evidence_results),
            "evidence_quality": ai_analysis.get("evidence_quality", "unknown")
        }
        
        # Use LLM to generate contextual recommendations
        prompt = f"""Based on the control assessment analysis, provide specific gaps and recommendations.

Control: {context['control_name']}
Description: {context['control_description']}
Implementation Status: {context['implementation_status']}
Evidence Quality: {context['evidence_quality']}
Evidence Count: {context['evidence_count']}

Provide response in JSON format:
{{
    "gaps_identified": ["specific gap 1", "specific gap 2"],
    "recommendations": ["actionable recommendation 1", "actionable recommendation 2"]
}}"""

        try:
            response = self.llm.client.generate(
                model=config.get_llm_model("analysis"),
                prompt=prompt,
                options={"temperature": 0.7, "num_predict": 500}
            )
            
            # Parse JSON response
            result_text = response['response']
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            
            if json_match:
                result = json.loads(json_match.group())
                return {
                    "gaps": result.get("gaps_identified", []),
                    "recommendations": result.get("recommendations", [])
                }
            
        except Exception as e:
            logger.error(f"Error generating AI insights: {e}")
        
        # Fallback to rule-based insights
        return self._generate_fallback_insights(ai_analysis, context)
    
    async def _ai_generate_questions(
        self,
        control_id: str,
        control_details: Dict,
        ai_analysis: Dict,
        gaps_recommendations: Dict
    ) -> List[str]:
        """Generate intelligent stakeholder questions using AI"""
        
        evidence_gaps = gaps_recommendations.get("gaps", [])
        
        questions = await self.llm.generate_questions(
            control_id=control_id,
            control_description=control_details.get("description", ""),
            current_evidence=[],  # Could pass evidence summaries
            gaps_identified=evidence_gaps
        )
        
        return questions
    
    async def _ai_assess_impacts(
        self,
        control_details: Dict,
        ai_analysis: Dict,
        organization_context: Dict
    ) -> Dict[str, str]:
        """AI-powered impact assessment"""
        
        implementation_status = ai_analysis.get("implementation_status", "unknown")
        industry = organization_context.get("industry", "general")
        
        # Use AI to assess impacts based on context
        prompt = f"""Assess the business, security, and brand impact of this compliance gap.

Control: {control_details.get('name', 'Unknown')}
Description: {control_details.get('description', '')}
Current Status: {implementation_status}
Organization Industry: {industry}

Provide assessment in JSON format:
{{
    "business_impact": "critical|high|medium|low|none",
    "security_impact": "critical|high|medium|low|none", 
    "brand_impact": "critical|high|medium|low|none",
    "risk_rating": "Critical|High|Medium|Low",
    "reasoning": "explanation of impact assessment"
}}"""

        try:
            response = self.llm.client.generate(
                model=config.get_llm_model("analysis"),
                prompt=prompt,
                options={"temperature": 0.6, "num_predict": 400}
            )
            
            result_text = response['response']
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            
            if json_match:
                result = json.loads(json_match.group())
                return {
                    "business_impact": result.get("business_impact", "medium"),
                    "security_impact": result.get("security_impact", "medium"),
                    "brand_impact": result.get("brand_impact", "medium"),
                    "risk_rating": result.get("risk_rating", "Medium")
                }
                
        except Exception as e:
            logger.error(f"Error in AI impact assessment: {e}")
        
        # Fallback impact assessment
        return self._fallback_impact_assessment(implementation_status, industry)
    
    def _assess_maturity(
        self,
        ai_analysis: Dict,
        evidence_results: List[Dict]
    ) -> Dict[str, Any]:
        """Assess maturity level based on AI analysis and evidence"""
        
        implementation_status = ai_analysis.get("implementation_status", "unknown")
        confidence = ai_analysis.get("confidence_score", 0)
        evidence_count = len(evidence_results)
        evidence_quality = ai_analysis.get("evidence_quality", "low")
        
        # Maturity assessment logic
        if implementation_status == "implemented":
            if evidence_quality == "high" and evidence_count >= 3 and confidence > 0.8:
                level = MaturityLevel.OPTIMIZING.value
                reasoning = "Fully implemented with high-quality evidence and monitoring"
            elif evidence_quality in ["high", "medium"] and confidence > 0.7:
                level = MaturityLevel.MANAGED.value
                reasoning = "Implemented with good evidence and some measurement"
            else:
                level = MaturityLevel.DEFINED.value
                reasoning = "Implemented with basic evidence"
        elif implementation_status == "partially_implemented":
            level = MaturityLevel.DEVELOPING.value
            reasoning = "Partially implemented, needs completion"
        elif implementation_status == "not_implemented":
            level = MaturityLevel.INITIAL.value
            reasoning = "Not implemented or ad-hoc processes only"
        else:
            level = MaturityLevel.NONE.value
            reasoning = "Implementation status unclear"
        
        return {
            "level": level,
            "reasoning": reasoning
        }
    
    def _determine_validation(
        self,
        ai_analysis: Dict,
        evidence_results: List[Dict],
        control_details: Dict
    ) -> Tuple[bool, str]:
        """Determine if manual validation is required"""
        
        confidence = ai_analysis.get("confidence_score", 0)
        implementation_status = ai_analysis.get("implementation_status", "unknown")
        evidence_count = len(evidence_results)
        
        # Validation required conditions
        if confidence < self.confidence_thresholds["medium"]:
            return True, f"Low AI confidence ({confidence:.2f}) requires validation"
        
        if implementation_status == "unknown":
            return True, "Implementation status unclear, needs validation"
        
        if evidence_count == 0:
            return True, "No evidence found, requires stakeholder input"
        
        if implementation_status == "partially_implemented":
            return True, "Partial implementation needs clarification"
        
        return False, "Assessment confidence sufficient"
    
    async def assess_full_framework(
        self,
        assessment_id: str,
        framework: str,
        organization_context: Dict = None
    ) -> Dict[str, Any]:
        """Assess all controls in a framework using AI"""
        
        logger.info(f"Starting AI-powered framework assessment: {framework}")
        start_time = datetime.now()
        
        # Get all controls for framework
        controls = self._get_framework_controls(framework)
        
        # Initialize results
        results = {
            "framework": framework,
            "assessment_id": assessment_id,
            "total_controls": len(controls),
            "assessments": [],
            "summary": {
                "implemented": 0,
                "partially_implemented": 0,
                "not_implemented": 0,
                "not_applicable": 0,
                "unknown": 0
            },
            "ai_metrics": {
                "average_confidence": 0.0,
                "high_confidence_assessments": 0,
                "validation_required": 0,
                "processing_time": 0.0
            }
        }
        
        # Process controls in batches to manage memory
        batch_size = 5
        confidences = []
        
        for i in range(0, len(controls), batch_size):
            batch = controls[i:i + batch_size]
            
            # Process batch concurrently
            batch_tasks = [
                self.assess_control(
                    assessment_id, 
                    control["id"], 
                    framework,
                    organization_context
                )
                for control in batch
            ]
            
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Process batch results
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Error assessing control {batch[j]['id']}: {result}")
                    continue
                
                assessment = result
                results["assessments"].append(assessment)
                
                # Update summary
                status = assessment.implementation_status.value
                if status in results["summary"]:
                    results["summary"][status] += 1
                
                # Update AI metrics
                confidences.append(assessment.ai_confidence)
                
                if assessment.ai_confidence > self.confidence_thresholds["high"]:
                    results["ai_metrics"]["high_confidence_assessments"] += 1
                
                if assessment.requires_validation:
                    results["ai_metrics"]["validation_required"] += 1
            
            # Brief pause between batches
            await asyncio.sleep(0.1)
        
        # Calculate final metrics
        if confidences:
            results["ai_metrics"]["average_confidence"] = statistics.mean(confidences)
        
        total_time = (datetime.now() - start_time).total_seconds()
        results["ai_metrics"]["processing_time"] = total_time
        
        # Generate AI summary
        ai_summary = await self._generate_framework_summary(results, organization_context)
        results["ai_summary"] = ai_summary
        
        # Update assessment record
        await self._update_assessment_summary(assessment_id, results)
        
        logger.info(f"Completed framework assessment in {total_time:.2f}s")
        return results
    
    async def _generate_framework_summary(
        self,
        results: Dict,
        organization_context: Dict
    ) -> str:
        """Generate AI-powered executive summary"""
        
        org_name = organization_context.get("organization_name", "Organization")
        
        summary = await self.llm.summarize_assessment(
            assessment_results=[
                {
                    "implementation_status": a.implementation_status.value,
                    "confidence_score": a.ai_confidence
                }
                for a in results["assessments"]
            ],
            organization_name=org_name,
            framework=results["framework"]
        )
        
        return summary
    
    # Helper methods
    
    def _load_frameworks_knowledge(self) -> Dict:
        """Load compliance frameworks knowledge"""
        # This would load from your knowledge graph
        # For now, return basic structure
        return {
            "ISO_27001": {"total_controls": 93},
            "ESSENTIAL_8": {"total_controls": 8},
            "SOC_2": {"total_controls": 64},
            "NIST_CSF": {"total_controls": 108},
            "PCI_DSS": {"total_controls": 78}
        }
    
    def _get_control_details(self, framework: str, control_id: str) -> Dict:
        """Get control details from knowledge graph"""
        # This would query your Neon database
        # For now, return mock data
        return {
            "id": control_id,
            "name": f"Control {control_id}",
            "description": f"Description for {framework} control {control_id}",
            "keywords": [framework.lower(), control_id.lower(), "compliance"]
        }
    
    def _get_framework_controls(self, framework: str) -> List[Dict]:
        """Get all controls for a framework"""
        # This would query your knowledge graph
        # Mock some controls for testing
        if framework == "ISO_27001":
            return [{"id": f"A.{i}.{j}"} for i in range(5, 9) for j in range(1, 4)]
        elif framework == "ESSENTIAL_8":
            return [{"id": f"E{i}"} for i in range(1, 9)]
        else:
            return [{"id": f"{framework}_CTRL_{i}"} for i in range(1, 11)]
    
    def _deduplicate_evidence(self, evidence_list: List[Dict]) -> List[Dict]:
        """Remove duplicate evidence entries"""
        seen = set()
        unique = []
        
        for evidence in evidence_list:
            key = evidence.get("id", "") + evidence.get("document_id", "")
            if key not in seen:
                seen.add(key)
                unique.append(evidence)
        
        # Sort by relevance score
        return sorted(unique, key=lambda x: x.get("score", 0), reverse=True)
    
    def _summarize_evidence(self, evidence_results: List[Dict]) -> str:
        """Create summary of evidence found"""
        if not evidence_results:
            return "No relevant evidence found"
        
        summaries = []
        for evidence in evidence_results[:3]:
            text = evidence.get("chunk_text", "")
            if text:
                summaries.append(text[:100] + "..." if len(text) > 100 else text)
        
        return " | ".join(summaries)
    
    def _generate_fallback_insights(
        self,
        ai_analysis: Dict,
        context: Dict
    ) -> Dict[str, List[str]]:
        """Generate basic insights when AI fails"""
        
        gaps = []
        recommendations = []
        
        if context["evidence_count"] == 0:
            gaps.append("No evidence documentation found")
            recommendations.append("Provide documentation demonstrating control implementation")
        
        if ai_analysis.get("confidence_score", 0) < 0.5:
            gaps.append("Insufficient evidence quality")
            recommendations.append("Improve documentation quality and detail")
        
        return {"gaps": gaps, "recommendations": recommendations}
    
    def _fallback_impact_assessment(
        self,
        implementation_status: str,
        industry: str
    ) -> Dict[str, str]:
        """Fallback impact assessment without AI"""
        
        if implementation_status == "not_implemented":
            return {
                "business_impact": "high",
                "security_impact": "high",
                "brand_impact": "medium",
                "risk_rating": "High"
            }
        elif implementation_status == "partially_implemented":
            return {
                "business_impact": "medium",
                "security_impact": "medium",
                "brand_impact": "low",
                "risk_rating": "Medium"
            }
        else:
            return {
                "business_impact": "low",
                "security_impact": "low",
                "brand_impact": "low",
                "risk_rating": "Low"
            }
    
    async def _store_assessment(
        self,
        assessment_id: str,
        assessment: ControlAssessment
    ):
        """Store control assessment in database"""
        
        with self.infrastructure["db"].get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO control_assessments (
                    assessment_id, control_id, control_name, control_description,
                    implementation_status, maturity_level, confidence_score,
                    ai_analysis, ai_evidence_quality, ai_confidence, ai_reasoning,
                    evidence_count, evidence_summary,
                    ai_gaps_identified, ai_recommendations, ai_questions,
                    business_impact, security_impact, brand_impact, risk_rating,
                    requires_validation, validation_reason,
                    assessed_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """, (
                assessment_id, assessment.control_id, assessment.control_name, "",
                assessment.implementation_status.value, assessment.maturity_level.value,
                assessment.ai_confidence,
                json.dumps({"model": assessment.model_used, "processing_time": assessment.processing_time}),
                assessment.evidence_quality, assessment.ai_confidence, assessment.ai_reasoning,
                assessment.evidence_count, assessment.evidence_summary,
                json.dumps(assessment.gaps_identified), json.dumps(assessment.recommendations),
                json.dumps(assessment.stakeholder_questions),
                assessment.business_impact.value, assessment.security_impact.value,
                assessment.brand_impact.value, assessment.risk_rating,
                assessment.requires_validation, assessment.validation_reason,
                assessment.assessed_at
            ))
            
            conn.commit()
    
    async def _update_assessment_summary(
        self,
        assessment_id: str,
        results: Dict
    ):
        """Update main assessment with summary data"""
        
        summary = results["summary"]
        ai_metrics = results["ai_metrics"]
        
        # Calculate overall score
        total_applicable = results["total_controls"] - summary.get("not_applicable", 0)
        if total_applicable > 0:
            score = (summary["implemented"] + 0.5 * summary["partially_implemented"]) / total_applicable * 100
        else:
            score = 0
        
        with self.infrastructure["db"].get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE assessments SET
                    status = 'completed',
                    total_controls = %s,
                    controls_implemented = %s,
                    controls_partial = %s,
                    controls_not_implemented = %s,
                    controls_not_applicable = %s,
                    overall_score = %s,
                    ai_confidence_score = %s,
                    ai_analysis_summary = %s,
                    ai_recommendations = %s,
                    completed_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (
                results["total_controls"],
                summary["implemented"],
                summary["partially_implemented"], 
                summary["not_implemented"],
                summary.get("not_applicable", 0),
                round(score, 2),
                round(ai_metrics["average_confidence"], 3),
                results.get("ai_summary", ""),
                json.dumps({
                    "high_confidence_assessments": ai_metrics["high_confidence_assessments"],
                    "validation_required": ai_metrics["validation_required"],
                    "processing_time": ai_metrics["processing_time"]
                }),
                assessment_id
            ))
            
            conn.commit()


# Singleton instance
_assessment_engine = None

def get_assessment_engine() -> EnhancedAssessmentEngine:
    """Get or create assessment engine instance"""
    global _assessment_engine
    if _assessment_engine is None:
        _assessment_engine = EnhancedAssessmentEngine()
    return _assessment_engine