#!/usr/bin/env python3
"""
TitanAI Phase 2: Logic Gate Assessment Engine
This module implements the sequential decision tree logic for control assessment,
building on the infrastructure from Phase 1.

The architecture uses multi-gate evaluation to determine control implementation
status, generate contextual questions, and perform impact analysis.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import re
from functools import lru_cache

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# ASSESSMENT ENUMS AND CONSTANTS
# ============================================================================

class ImplementationStatus(Enum):
    """Standardized implementation status values"""
    IMPLEMENTED = "implemented"
    PARTIALLY_IMPLEMENTED = "partially_implemented"
    NOT_IMPLEMENTED = "not_implemented"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"

class ImpactLevel(Enum):
    """Impact severity levels for risk assessment"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"

class MaturityLevel(Enum):
    """Maturity levels for control implementation"""
    OPTIMIZING = 5  # Continuous improvement
    QUANTITATIVELY_MANAGED = 4  # Measured and controlled
    DEFINED = 3  # Standardized processes
    MANAGED = 2  # Basic processes
    INITIAL = 1  # Ad-hoc
    NONE = 0  # Not implemented

# Industry-specific risk weightings for impact analysis
INDUSTRY_RISK_PROFILES = {
    "Financial Services": {
        "data_protection": 1.5,
        "access_control": 1.4,
        "incident_response": 1.3,
        "business_continuity": 1.5
    },
    "Healthcare": {
        "data_protection": 1.6,
        "physical_security": 1.2,
        "access_control": 1.4,
        "audit_logging": 1.3
    },
    "Technology": {
        "development_security": 1.4,
        "vulnerability_management": 1.5,
        "change_management": 1.3,
        "access_control": 1.2
    },
    "Government": {
        "classification": 1.5,
        "physical_security": 1.4,
        "personnel_security": 1.4,
        "audit_logging": 1.5
    },
    "Retail": {
        "payment_security": 1.6,
        "customer_data": 1.4,
        "availability": 1.3,
        "third_party_risk": 1.2
    }
}

# Control mappings for cross-framework analysis
CONTROL_MAPPINGS = {
    "access_control": {
        "ISO27001": ["A.9.1", "A.9.2", "A.9.3", "A.9.4"],
        "SOC2": ["CC6.1", "CC6.2", "CC6.3"],
        "NIST": ["AC-1", "AC-2", "AC-3"],
        "Essential8": ["E8.1", "E8.2"]
    },
    "data_protection": {
        "ISO27001": ["A.8.2", "A.10.1"],
        "SOC2": ["CC6.7", "CC7.1"],
        "NIST": ["SC-8", "SC-13", "SC-28"],
        "Essential8": ["E8.5"]
    }
}

# ============================================================================
# LOGIC GATE ENGINE
# ============================================================================

class LogicGateEngine:
    """
    Implements the multi-gate decision tree for control assessment.
    
    Each control passes through sequential gates that evaluate different
    aspects of implementation, building a comprehensive assessment profile.
    """
    
    def __init__(self, db_manager=None):
        """Initialize the logic gate engine with optional database connection"""
        self.db = db_manager
        self.gates = [
            self._gate1_evidence_existence,
            self._gate2_evidence_quality,
            self._gate3_temporal_validity,
            self._gate4_contradiction_detection,
            self._gate5_impact_analysis
        ]
        
        logger.info("Logic Gate Engine initialized with 5 gates")
    
    async def evaluate_control(
        self,
        control_id: str,
        framework: str,
        evidence_list: List[Dict],
        organization_context: Dict
    ) -> Dict:
        """
        Run a control through all logic gates to determine its status.
        
        This function processes evidence through sequential decision points,
        accumulating findings at each gate. The result is a comprehensive
        assessment that includes implementation status, confidence scores,
        gaps identified, and recommendations.
        """
        
        # Initialize the assessment result structure
        assessment_result = {
            "control_id": control_id,
            "framework": framework,
            "timestamp": datetime.utcnow().isoformat(),
            "organization_context": organization_context,
            "evidence_provided": len(evidence_list),
            "gates_passed": [],
            "implementation_status": ImplementationStatus.UNKNOWN.value,
            "confidence_score": 0.0,
            "maturity_level": MaturityLevel.NONE.value,
            "gaps_identified": [],
            "recommendations": [],
            "stakeholder_questions": [],
            "business_impact": None,
            "security_impact": None,
            "brand_impact": None,
            "requires_validation": False,
            "validation_reason": None,
            "related_controls": []
        }
        
        # Get control details from knowledge graph or use provided data
        control_details = self._get_control_details(framework, control_id)
        assessment_result["control_name"] = control_details.get("name", "Unknown Control")
        assessment_result["control_description"] = control_details.get("description", "")
        assessment_result["evidence_required"] = control_details.get("evidence_required", [])
        
        # Process through each gate sequentially
        gate_context = {
            "control_details": control_details,
            "organization": organization_context,
            "evidence": evidence_list,
            "assessment": assessment_result
        }
        
        for gate_func in self.gates:
            gate_name = gate_func.__name__.replace("_", " ").title()
            logger.info(f"Processing {control_id} through {gate_name}")
            
            # Execute gate logic
            gate_result = await gate_func(gate_context)
            
            # Update assessment based on gate result
            assessment_result["gates_passed"].append({
                "gate": gate_name,
                "passed": gate_result.get("passed", False),
                "findings": gate_result.get("findings", [])
            })
            
            # Early exit conditions - if a gate determines we can't proceed
            if gate_result.get("stop_processing", False):
                logger.info(f"Stopping at {gate_name} for {control_id}")
                break
        
        # Final status determination based on all gates
        assessment_result = self._determine_final_status(assessment_result)
        
        # Generate cross-framework mapping
        assessment_result["related_controls"] = self._get_related_controls(
            framework, control_id
        )
        
        return assessment_result
    
    async def _gate1_evidence_existence(self, context: Dict) -> Dict:
        """
        Gate 1: Check if any evidence exists for the control.
        
        This is the fundamental gate - without evidence, we cannot assess
        implementation. When evidence is missing, we generate discovery
        questions to help auditors know what to look for.
        """
        
        evidence_list = context["evidence"]
        control_details = context["control_details"]
        assessment = context["assessment"]
        
        gate_result = {
            "passed": False,
            "findings": [],
            "stop_processing": False
        }
        
        if not evidence_list:
            # No evidence provided
            gate_result["findings"].append("No evidence provided for this control")
            
            # Generate discovery questions based on what's typically required
            discovery_questions = self._generate_discovery_questions(
                control_details,
                context["organization"]
            )
            assessment["stakeholder_questions"].extend(discovery_questions)
            
            # Determine if this is a mandatory control
            is_mandatory = self._check_if_mandatory(
                control_details,
                context["organization"].get("industry", "General")
            )
            
            if is_mandatory:
                assessment["gaps_identified"].append(
                    f"Critical gap: No evidence for mandatory control {control_details.get('name')}"
                )
                assessment["requires_validation"] = True
                assessment["validation_reason"] = "Mandatory control with no evidence"
                assessment["recommendations"].append({
                    "priority": "critical",
                    "action": f"Immediately provide evidence for {control_details.get('name')}",
                    "rationale": "This control is mandatory for your industry/framework"
                })
            
            assessment["implementation_status"] = ImplementationStatus.NOT_IMPLEMENTED.value
            gate_result["stop_processing"] = True  # Can't assess further without evidence
            
        else:
            # Evidence exists, can proceed to quality assessment
            gate_result["passed"] = True
            gate_result["findings"].append(f"Found {len(evidence_list)} evidence items")
            
            # Store evidence metadata for later gates
            context["evidence_metadata"] = {
                "count": len(evidence_list),
                "types": list(set(e.get("document_type", "unknown") for e in evidence_list)),
                "dates": [e.get("document_date") for e in evidence_list if e.get("document_date")]
            }
        
        return gate_result
    
    async def _gate2_evidence_quality(self, context: Dict) -> Dict:
        """
        Gate 2: Assess the quality and completeness of evidence.
        
        Not all evidence is created equal. This gate evaluates whether
        the evidence is authoritative, complete, and directly addresses
        the control requirements.
        """
        
        evidence_list = context["evidence"]
        control_details = context["control_details"]
        assessment = context["assessment"]
        
        gate_result = {
            "passed": False,
            "findings": [],
            "stop_processing": False
        }
        
        # Calculate evidence quality score
        quality_scores = []
        for evidence in evidence_list:
            score = self._calculate_evidence_quality(evidence, control_details)
            quality_scores.append(score)
            
            # Document-specific findings
            if score < 0.3:
                gate_result["findings"].append(
                    f"Low quality evidence: {evidence.get('filename', 'Unknown document')} "
                    f"(confidence: {score:.2f})"
                )
        
        # Overall quality assessment
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
        max_quality = max(quality_scores) if quality_scores else 0
        
        assessment["confidence_score"] = max_quality  # Use best evidence
        
        if max_quality >= 0.7:
            gate_result["passed"] = True
            gate_result["findings"].append(f"High quality evidence found (confidence: {max_quality:.2f})")
            assessment["implementation_status"] = ImplementationStatus.IMPLEMENTED.value
            
        elif max_quality >= 0.4:
            gate_result["passed"] = True  # Can continue but with caveats
            gate_result["findings"].append(f"Moderate quality evidence (confidence: {max_quality:.2f})")
            assessment["implementation_status"] = ImplementationStatus.PARTIALLY_IMPLEMENTED.value
            
            # Generate clarification questions
            clarification_questions = self._generate_clarification_questions(
                control_details,
                evidence_list
            )
            assessment["stakeholder_questions"].extend(clarification_questions)
            
            # Identify what's missing
            missing_elements = self._identify_missing_evidence(
                control_details,
                evidence_list
            )
            assessment["gaps_identified"].extend(missing_elements)
            
        else:
            gate_result["findings"].append(f"Insufficient evidence quality (confidence: {max_quality:.2f})")
            assessment["implementation_status"] = ImplementationStatus.NOT_IMPLEMENTED.value
            assessment["requires_validation"] = True
            assessment["validation_reason"] = "Evidence quality below acceptable threshold"
            
            # Provide specific guidance on improving evidence
            assessment["recommendations"].append({
                "priority": "high",
                "action": "Provide authoritative documentation",
                "rationale": f"Current evidence has low confidence ({max_quality:.2f}). "
                          f"Need: {', '.join(control_details.get('evidence_required', ['formal documentation'])[:3])}"
            })
        
        return gate_result
    
    async def _gate3_temporal_validity(self, context: Dict) -> Dict:
        """
        Gate 3: Check if evidence is current and valid.
        
        Compliance evidence can become stale. This gate checks document
        dates and determines if evidence needs to be refreshed.
        """
        
        evidence_list = context["evidence"]
        assessment = context["assessment"]
        
        gate_result = {
            "passed": True,
            "findings": [],
            "stop_processing": False
        }
        
        current_date = datetime.utcnow()
        
        for evidence in evidence_list:
            doc_date = evidence.get("document_date")
            if not doc_date:
                continue  # Skip if no date available
            
            # Parse date if string
            if isinstance(doc_date, str):
                try:
                    doc_date = datetime.fromisoformat(doc_date.replace('Z', '+00:00'))
                except:
                    continue
            
            age_days = (current_date - doc_date).days
            
            # Apply temporal validity rules
            if age_days > 730:  # More than 2 years old
                gate_result["findings"].append(
                    f"Evidence outdated: {evidence.get('filename', 'Document')} "
                    f"is {age_days} days old"
                )
                
                # Downgrade confidence significantly
                assessment["confidence_score"] *= 0.5
                
                assessment["gaps_identified"].append(
                    f"Outdated evidence: {evidence.get('filename')} needs refresh"
                )
                
                assessment["recommendations"].append({
                    "priority": "medium",
                    "action": f"Update {evidence.get('document_type', 'documentation')}",
                    "rationale": f"Evidence is {age_days//30} months old, exceeds 24-month threshold"
                })
                
                assessment["requires_validation"] = True
                assessment["validation_reason"] = "Evidence exceeds age threshold"
                
            elif age_days > 540:  # More than 18 months
                gate_result["findings"].append(
                    f"Evidence aging: {evidence.get('filename')} should be reviewed"
                )
                
                # Minor confidence downgrade
                assessment["confidence_score"] *= 0.8
                
                assessment["stakeholder_questions"].append(
                    f"Has {evidence.get('document_type', 'this documentation')} "
                    f"been reviewed or updated since {doc_date.strftime('%B %Y')}?"
                )
        
        # Check for evidence refresh patterns
        if context.get("evidence_metadata", {}).get("dates"):
            dates = context["evidence_metadata"]["dates"]
            if dates:
                # Check if there's a pattern of regular updates
                sorted_dates = sorted(dates)
                if len(sorted_dates) > 1:
                    update_frequency = (sorted_dates[-1] - sorted_dates[0]).days / len(sorted_dates)
                    if update_frequency < 180:  # Updates more frequent than 6 months
                        gate_result["findings"].append(
                            "Evidence shows regular update pattern"
                        )
                        assessment["maturity_level"] = max(
                            assessment["maturity_level"],
                            MaturityLevel.DEFINED.value
                        )
        
        return gate_result
    
    async def _gate4_contradiction_detection(self, context: Dict) -> Dict:
        """
        Gate 4: Detect and resolve contradictions in evidence.
        
        When multiple documents provide conflicting information, this gate
        identifies the contradictions and flags them for human review.
        """
        
        evidence_list = context["evidence"]
        assessment = context["assessment"]
        
        gate_result = {
            "passed": True,
            "findings": [],
            "stop_processing": False
        }
        
        if len(evidence_list) < 2:
            gate_result["findings"].append("Single evidence source - no contradictions possible")
            return gate_result
        
        # Group evidence by type to check for contradictions
        evidence_by_type = {}
        for evidence in evidence_list:
            doc_type = evidence.get("document_type", "unknown")
            if doc_type not in evidence_by_type:
                evidence_by_type[doc_type] = []
            evidence_by_type[doc_type].append(evidence)
        
        # Check for contradictions within same document type
        contradictions_found = []
        
        for doc_type, docs in evidence_by_type.items():
            if len(docs) > 1:
                # Compare key attributes
                for i, doc1 in enumerate(docs):
                    for doc2 in docs[i+1:]:
                        contradictions = self._compare_evidence(doc1, doc2)
                        if contradictions:
                            contradictions_found.extend(contradictions)
        
        if contradictions_found:
            gate_result["findings"].append(
                f"Found {len(contradictions_found)} contradictions in evidence"
            )
            
            assessment["requires_validation"] = True
            assessment["validation_reason"] = "Contradictory evidence requires human review"
            
            # Add specific questions about contradictions
            for contradiction in contradictions_found[:3]:  # Limit to top 3
                assessment["stakeholder_questions"].append(
                    f"Please clarify: {contradiction['description']}"
                )
                
                assessment["gaps_identified"].append(
                    f"Contradiction: {contradiction['summary']}"
                )
            
            # Provide both perspectives
            assessment["recommendations"].append({
                "priority": "high",
                "action": "Resolve contradictory evidence",
                "rationale": "Multiple documents provide conflicting information. "
                           "Human review required to determine authoritative source."
            })
            
            # Downgrade confidence when contradictions exist
            assessment["confidence_score"] *= 0.7
        
        return gate_result
    
    async def _gate5_impact_analysis(self, context: Dict) -> Dict:
        """
        Gate 5: Analyze business, security, and brand impacts.
        
        This gate evaluates the real-world implications of the control's
        implementation status, considering industry-specific factors.
        """
        
        assessment = context["assessment"]
        control_details = context["control_details"]
        organization = context["organization"]
        
        gate_result = {
            "passed": True,
            "findings": [],
            "stop_processing": False
        }
        
        # Get industry-specific risk profile
        industry = organization.get("industry", "General")
        risk_profile = INDUSTRY_RISK_PROFILES.get(
            industry, 
            {"general": 1.0}  # Default multiplier
        )
        
        # Determine control category for risk weighting
        control_category = self._determine_control_category(control_details)
        risk_multiplier = risk_profile.get(control_category, 1.0)
        
        # Calculate base impacts based on implementation status
        implementation = assessment["implementation_status"]
        
        if implementation == ImplementationStatus.NOT_IMPLEMENTED.value:
            base_business = ImpactLevel.HIGH
            base_security = ImpactLevel.HIGH
            base_brand = ImpactLevel.MEDIUM
            
        elif implementation == ImplementationStatus.PARTIALLY_IMPLEMENTED.value:
            base_business = ImpactLevel.MEDIUM
            base_security = ImpactLevel.MEDIUM
            base_brand = ImpactLevel.LOW
            
        else:  # Implemented
            base_business = ImpactLevel.LOW
            base_security = ImpactLevel.LOW
            base_brand = ImpactLevel.NONE
        
        # Apply industry multiplier
        assessment["business_impact"] = self._adjust_impact_level(
            base_business, risk_multiplier
        )
        assessment["security_impact"] = self._adjust_impact_level(
            base_security, risk_multiplier * 1.1  # Security slightly higher weight
        )
        assessment["brand_impact"] = self._adjust_impact_level(
            base_brand, risk_multiplier * 0.9  # Brand slightly lower weight
        )
        
        # Generate impact-based insights
        if assessment["business_impact"] in [ImpactLevel.CRITICAL.value, ImpactLevel.HIGH.value]:
            gate_result["findings"].append(
                f"High business impact identified for {industry} industry"
            )
            
            # Add specific business impact context
            business_impact_desc = self._get_business_impact_description(
                control_category, industry, implementation
            )
            assessment["recommendations"].append({
                "priority": "critical",
                "action": f"Address {control_details.get('name')} immediately",
                "rationale": business_impact_desc
            })
        
        # Check for related vulnerabilities or threats
        if control_category in ["vulnerability_management", "patch_management", "access_control"]:
            # This would integrate with threat intelligence in production
            gate_result["findings"].append(
                "Control relates to active threat vectors"
            )
            
            assessment["stakeholder_questions"].append(
                f"Have you reviewed recent threat intelligence related to {control_category}?"
            )
        
        # Cross-framework impact analysis
        related_controls = assessment.get("related_controls", [])
        if related_controls:
            gate_result["findings"].append(
                f"This control impacts {len(related_controls)} related controls across frameworks"
            )
            
            # If this is a foundational control, increase impact
            if len(related_controls) > 3:
                assessment["business_impact"] = self._increase_impact_level(
                    assessment["business_impact"]
                )
                assessment["recommendations"].append({
                    "priority": "high",
                    "action": "Prioritize this foundational control",
                    "rationale": f"Affects {len(related_controls)} controls across multiple frameworks"
                })
        
        return gate_result
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _get_control_details(self, framework: str, control_id: str) -> Dict:
        """Retrieve control details from the knowledge graph or use defaults"""
        
        # In production, this would query the database
        # For now, return a structured default
        return {
            "name": control_id,
            "description": f"Control {control_id} for {framework}",
            "evidence_required": [
                "Policy documentation",
                "Implementation evidence",
                "Review records"
            ]
        }
    
    def _calculate_evidence_quality(self, evidence: Dict, control_details: Dict) -> float:
        """
        Calculate quality score for a piece of evidence.
        
        This considers multiple factors including document type, approval status,
        relevance to the control, and confidence from the AI analysis.
        """
        
        quality_score = 0.0
        
        # Base score from AI confidence
        quality_score = evidence.get("confidence_score", 0.5)
        
        # Adjust based on document type
        doc_type = evidence.get("document_type", "").lower()
        if "policy" in doc_type and evidence.get("is_approved", False):
            quality_score *= 1.3  # Approved policies are high quality
        elif "procedure" in doc_type:
            quality_score *= 1.1
        elif "email" in doc_type or "draft" in doc_type:
            quality_score *= 0.7  # Informal evidence is lower quality
        
        # Check if evidence addresses required elements
        required_evidence = control_details.get("evidence_required", [])
        if required_evidence:
            evidence_text = evidence.get("extracted_text", "").lower()
            matched_requirements = 0
            
            for requirement in required_evidence:
                # Simple keyword matching - could be enhanced with NLP
                keywords = requirement.lower().split()
                if any(keyword in evidence_text for keyword in keywords):
                    matched_requirements += 1
            
            if required_evidence:
                coverage = matched_requirements / len(required_evidence)
                quality_score *= (0.5 + 0.5 * coverage)  # 50% penalty if no coverage
        
        # Cap at 1.0
        return min(quality_score, 1.0)
    
    def _check_if_mandatory(self, control_details: Dict, industry: str) -> bool:
        """Determine if a control is mandatory for the given industry"""
        
        # Industry-specific mandatory controls
        mandatory_controls = {
            "Financial Services": ["access_control", "audit_logging", "encryption"],
            "Healthcare": ["access_control", "audit_logging", "data_protection"],
            "Government": ["classification", "personnel_security", "physical_security"]
        }
        
        control_category = self._determine_control_category(control_details)
        industry_mandatory = mandatory_controls.get(industry, [])
        
        return control_category in industry_mandatory
    
    def _generate_discovery_questions(
        self, 
        control_details: Dict, 
        organization: Dict
    ) -> List[str]:
        """
        Generate specific questions to help discover missing evidence.
        
        These questions are tailored to the control and organization context,
        making them more actionable than generic queries.
        """
        
        questions = []
        control_name = control_details.get("name", "this control")
        evidence_required = control_details.get("evidence_required", [])
        
        # Start with specific evidence requirements
        for requirement in evidence_required[:3]:  # Limit to top 3
            questions.append(
                f"Can you provide {requirement} for {control_name}?"
            )
        
        # Add context-specific questions
        org_size = organization.get("size", "Medium")
        if org_size == "Large":
            questions.append(
                f"Which department or team is responsible for {control_name}?"
            )
            questions.append(
                f"Is {control_name} documented in your enterprise policy framework?"
            )
        else:
            questions.append(
                f"Who in your organization handles {control_name}?"
            )
        
        # Add implementation-focused questions
        questions.append(
            f"What tools or systems do you use to implement {control_name}?"
        )
        questions.append(
            f"When was {control_name} last reviewed or tested?"
        )
        
        return questions
    
    def _generate_clarification_questions(
        self, 
        control_details: Dict, 
        evidence_list: List[Dict]
    ) -> List[str]:
        """Generate questions to clarify partial evidence"""
        
        questions = []
        
        # Identify what we have vs. what we need
        evidence_types = set(e.get("document_type", "") for e in evidence_list)
        required_types = set(control_details.get("evidence_required", []))
        
        missing = required_types - evidence_types
        
        for missing_type in list(missing)[:2]:  # Limit questions
            questions.append(
                f"The provided evidence doesn't clearly show {missing_type}. "
                f"Can you provide additional documentation or clarification?"
            )
        
        # Check for incomplete evidence
        for evidence in evidence_list:
            if evidence.get("confidence_score", 0) < 0.5:
                questions.append(
                    f"The {evidence.get('document_type', 'document')} "
                    f"'{evidence.get('filename', 'provided')}' only partially addresses "
                    f"the control. Can you provide more detailed information?"
                )
                break  # One question about incomplete evidence is enough
        
        return questions
    
    def _identify_missing_evidence(
        self, 
        control_details: Dict, 
        evidence_list: List[Dict]
    ) -> List[str]:
        """Identify specific gaps in evidence"""
        
        gaps = []
        required = control_details.get("evidence_required", [])
        
        # Check each requirement
        for requirement in required:
            requirement_found = False
            requirement_keywords = requirement.lower().split()
            
            for evidence in evidence_list:
                evidence_text = evidence.get("extracted_text", "").lower()
                if any(keyword in evidence_text for keyword in requirement_keywords):
                    requirement_found = True
                    break
            
            if not requirement_found:
                gaps.append(f"Missing: {requirement}")
        
        return gaps
    
    def _compare_evidence(self, doc1: Dict, doc2: Dict) -> List[Dict]:
        """Compare two evidence documents for contradictions"""
        
        contradictions = []
        
        # Compare key fields that shouldn't differ
        if doc1.get("is_approved") != doc2.get("is_approved"):
            contradictions.append({
                "description": f"Approval status differs between "
                              f"{doc1.get('filename')} and {doc2.get('filename')}",
                "summary": "Conflicting approval status"
            })
        
        # More sophisticated contradiction detection would go here
        # This is simplified for the example
        
        return contradictions
    
    def _determine_control_category(self, control_details: Dict) -> str:
        """Categorize a control for risk analysis"""
        
        control_name = control_details.get("name", "").lower()
        control_desc = control_details.get("description", "").lower()
        combined_text = f"{control_name} {control_desc}"
        
        # Map controls to categories based on keywords
        category_keywords = {
            "access_control": ["access", "authentication", "authorization", "privilege"],
            "data_protection": ["encryption", "cryptograph", "data protection", "confidential"],
            "incident_response": ["incident", "breach", "response", "forensic"],
            "business_continuity": ["continuity", "disaster", "recovery", "backup"],
            "audit_logging": ["audit", "log", "monitor", "track"],
            "physical_security": ["physical", "facility", "perimeter", "badge"],
            "vulnerability_management": ["vulnerabil", "patch", "update", "scan"],
            "change_management": ["change", "configuration", "baseline"],
            "development_security": ["develop", "code", "sdlc", "devops"],
            "personnel_security": ["personnel", "screening", "training", "awareness"]
        }
        
        for category, keywords in category_keywords.items():
            if any(keyword in combined_text for keyword in keywords):
                return category
        
        return "general"
    
    def _adjust_impact_level(self, base_level: ImpactLevel, multiplier: float) -> str:
        """Adjust impact level based on multiplier"""
        
        # Convert to numeric for calculation
        level_values = {
            ImpactLevel.NONE: 0,
            ImpactLevel.LOW: 1,
            ImpactLevel.MEDIUM: 2,
            ImpactLevel.HIGH: 3,
            ImpactLevel.CRITICAL: 4
        }
        
        value_levels = {v: k for k, v in level_values.items()}
        
        current_value = level_values[base_level]
        adjusted_value = min(4, int(current_value * multiplier))
        
        return value_levels[adjusted_value].value
    
    def _increase_impact_level(self, current_level: str) -> str:
        """Increase impact level by one step"""
        
        progression = {
            ImpactLevel.NONE.value: ImpactLevel.LOW.value,
            ImpactLevel.LOW.value: ImpactLevel.MEDIUM.value,
            ImpactLevel.MEDIUM.value: ImpactLevel.HIGH.value,
            ImpactLevel.HIGH.value: ImpactLevel.CRITICAL.value,
            ImpactLevel.CRITICAL.value: ImpactLevel.CRITICAL.value
        }
        
        return progression.get(current_level, current_level)
    
    def _get_business_impact_description(
        self, 
        control_category: str, 
        industry: str, 
        implementation_status: str
    ) -> str:
        """Generate specific business impact description"""
        
        impact_templates = {
            "access_control": {
                "Financial Services": "Unauthorized access could lead to financial fraud, "
                                    "regulatory penalties, and loss of customer trust",
                "Healthcare": "Improper access controls violate HIPAA requirements and "
                            "could result in significant fines and lawsuits",
                "default": "Weak access controls expose sensitive data to unauthorized users"
            },
            "data_protection": {
                "Financial Services": "Unencrypted data violates PCI DSS and could result "
                                    "in loss of payment processing capabilities",
                "Healthcare": "Patient data breaches average $10.93M in costs for "
                            "healthcare organizations",
                "default": "Data breaches result in significant financial and reputational damage"
            }
        }
        
        category_impacts = impact_templates.get(control_category, {})
        impact_desc = category_impacts.get(
            industry, 
            category_impacts.get("default", "Control gap poses business risk")
        )
        
        if implementation_status == ImplementationStatus.NOT_IMPLEMENTED.value:
            return f"CRITICAL: {impact_desc}"
        elif implementation_status == ImplementationStatus.PARTIALLY_IMPLEMENTED.value:
            return f"RISK: Partial implementation - {impact_desc}"
        else:
            return f"Monitor: {impact_desc}"
    
    def _get_related_controls(self, framework: str, control_id: str) -> List[Dict]:
        """Get controls from other frameworks that relate to this one"""
        
        related = []
        
        # Check control mappings
        for concept, mappings in CONTROL_MAPPINGS.items():
            framework_controls = mappings.get(framework, [])
            if control_id in framework_controls:
                # Found the concept this control belongs to
                for other_framework, other_controls in mappings.items():
                    if other_framework != framework:
                        for other_control in other_controls:
                            related.append({
                                "framework": other_framework,
                                "control_id": other_control,
                                "relationship": concept
                            })
        
        return related
    
    def _determine_final_status(self, assessment_result: Dict) -> Dict:
        """
        Determine final implementation status based on all gate results.
        
        This synthesizes findings from all gates to reach a conclusion.
        """
        
        # If we already determined status in early gates, keep it
        if assessment_result["implementation_status"] != ImplementationStatus.UNKNOWN.value:
            return assessment_result
        
        # Analyze gate results
        gates_passed = assessment_result["gates_passed"]
        all_passed = all(gate["passed"] for gate in gates_passed)
        
        if all_passed and assessment_result["confidence_score"] >= 0.7:
            assessment_result["implementation_status"] = ImplementationStatus.IMPLEMENTED.value
            assessment_result["maturity_level"] = MaturityLevel.DEFINED.value
            
        elif assessment_result["confidence_score"] >= 0.4:
            assessment_result["implementation_status"] = ImplementationStatus.PARTIALLY_IMPLEMENTED.value
            assessment_result["maturity_level"] = MaturityLevel.MANAGED.value
            
        else:
            assessment_result["implementation_status"] = ImplementationStatus.NOT_IMPLEMENTED.value
            assessment_result["maturity_level"] = MaturityLevel.INITIAL.value
        
        return assessment_result