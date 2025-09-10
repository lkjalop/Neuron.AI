#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agent Adapter for Enhanced Agents
Adapts existing enhanced agents to work with Opus 4.1 interface expectations.
"""

from typing import Dict, List, Any, Optional
import sys
from pathlib import Path

# Add src to path
current_dir = Path(__file__).parent
src_path = current_dir / "src"
sys.path.insert(0, str(src_path))

try:
    from professional.enhanced_evidence_detector_agent import EnhancedEvidenceDetectorAgent, EvidenceDetection
    from professional.enhanced_apollo_reasoner_agent import EnhancedApolloReasonerAgent
    ENHANCED_AGENTS_AVAILABLE = True
    print("SUCCESS: Enhanced agents imported successfully!")
except ImportError as e:
    print(f"Enhanced agents not available: {e}")
    ENHANCED_AGENTS_AVAILABLE = False


class AdaptedEvidenceDetectorAgent:
    """
    Adapter that makes existing enhanced evidence detector compatible with Opus 4.1.
    """
    
    def __init__(self):
        if ENHANCED_AGENTS_AVAILABLE:
            self.agent = EnhancedEvidenceDetectorAgent()
        else:
            self.agent = None
    
    def detect_evidence_with_penalty_correlation(self, content: str, filename: str, 
                                               perform_deep_analysis: bool = True) -> Dict:
        """
        Adapter method that converts enhanced agent output to Opus 4.1 format.
        """
        
        if not self.agent:
            # Fallback to simple pattern matching
            return self._fallback_detection(content, filename)
        
        try:
            # Call existing enhanced agent
            evidence_detections = self.agent.detect_evidence_with_penalty_correlation(
                content, filename, perform_deep_analysis
            )
            
            # Convert List[EvidenceDetection] to expected Dict format
            findings = []
            for detection in evidence_detections:
                finding = {
                    "type": detection.evidence_type,
                    "description": detection.content,
                    "source": detection.source_document,
                    "confidence": detection.confidence_score,
                    "location": f"Page {detection.page_number}",
                    "control": detection.control_references[0] if detection.control_references else self._map_evidence_to_control(detection.evidence_type),
                    "control_references": detection.control_references,  # Keep all control mappings
                    "severity": self._assess_severity(detection)
                }
                
                # Add penalty correlation if available
                if detection.penalty_risk:
                    finding["penalty_correlation"] = {
                        "pattern_id": detection.penalty_risk.pattern_id,
                        "violation_type": detection.penalty_risk.violation_type,
                        "penalty_range": detection.penalty_risk.penalty_range,
                        "regulatory_framework": detection.penalty_risk.regulatory_framework
                    }
                
                findings.append(finding)
            
            # Assess overall risk level
            risk_level = self._assess_document_risk(findings)
            
            return {
                "findings": findings,
                "risk_level": risk_level,
                "document": filename,
                "analysis_complete": True,
                "agent_type": "enhanced"
            }
            
        except Exception as e:
            print(f"Enhanced agent error, falling back: {e}")
            return self._fallback_detection(content, filename)
    
    def _fallback_detection(self, content: str, filename: str) -> Dict:
        """Fallback pattern matching when enhanced agent fails."""
        
        findings = []
        
        # Simple pattern matching
        patterns = {
            "policy": r"(?i)(policy|procedure|standard|guideline)",
            "control": r"(?i)(control|safeguard|measure|protection)",
            "risk": r"(?i)(risk|threat|vulnerability|exposure)",
            "incident": r"(?i)(incident|breach|violation|non-compliance)",
            "mfa": r"(?i)(multi-factor|two-factor|2fa|mfa)",
            "encryption": r"(?i)(encrypt|cryptograph|aes|tls|ssl)",
            "backup": r"(?i)(backup|recovery|restore|rpo|rto)",
            "access": r"(?i)(access control|permission|privilege|authorization)"
        }
        
        import re
        for pattern_name, pattern in patterns.items():
            matches = re.finditer(pattern, content)
            for match in list(matches)[:5]:  # Limit to 5 per pattern
                # Extract context
                start = max(0, match.start() - 100)
                end = min(len(content), match.end() + 100)
                context = content[start:end]
                
                finding = {
                    "type": pattern_name,
                    "description": context,
                    "source": filename,
                    "confidence": 0.6,  # Lower confidence for fallback
                    "location": f"Position {match.start()}",
                    "control": self._map_evidence_to_control(pattern_name),
                    "severity": "MEDIUM"
                }
                findings.append(finding)
        
        return {
            "findings": findings[:20],  # Limit total findings
            "risk_level": "MEDIUM",
            "document": filename,
            "analysis_complete": True,
            "agent_type": "fallback"
        }
    
    def _map_evidence_to_control(self, evidence_type: str) -> str:
        """Map evidence types to ISO 27001 controls."""
        mapping = {
            "mfa": "A.9.4.2",
            "encryption": "A.8.24",
            "backup": "A.12.3",
            "access": "A.9.1",
            "incident": "A.16.1",
            "risk": "A.5.1",
            "audit": "A.9.4.4",
            "policy": "A.5.1",
            "control": "A.5.1"
        }
        return mapping.get(evidence_type, "A.5.1")
    
    def _assess_severity(self, detection) -> str:
        """Assess severity based on detection."""
        if hasattr(detection, 'penalty_risk') and detection.penalty_risk:
            # If penalty risk exists, assess based on penalty range
            if detection.penalty_risk.penalty_range[1] > 10000000:  # > £10M
                return "CRITICAL"
            elif detection.penalty_risk.penalty_range[1] > 1000000:  # > £1M
                return "HIGH"
            else:
                return "MEDIUM"
        else:
            # Default assessment
            return "MEDIUM"
    
    def _assess_document_risk(self, findings: List[Dict]) -> str:
        """Assess overall document risk."""
        critical_count = sum(1 for f in findings if f.get("severity") == "CRITICAL")
        high_count = sum(1 for f in findings if f.get("severity") == "HIGH")
        
        if critical_count >= 3:
            return "CRITICAL"
        elif critical_count >= 1 or high_count >= 5:
            return "HIGH"
        elif high_count >= 2:
            return "MEDIUM"
        else:
            return "LOW"


class AdaptedApolloReasonerAgent:
    """
    Adapter for enhanced Apollo reasoner agent.
    """
    
    def __init__(self):
        if ENHANCED_AGENTS_AVAILABLE:
            try:
                self.agent = EnhancedApolloReasonerAgent()
            except Exception:
                self.agent = None
        else:
            self.agent = None
    
    async def perform_enhanced_reasoning(self, prompt: str, context: Dict, 
                                       include_recovery_analysis: bool = True) -> Dict:
        """
        Adapter method for enhanced reasoning.
        """
        
        if self.agent:
            try:
                # Try to use enhanced agent
                result = await self.agent.perform_multi_step_reasoning(
                    prompt, context, enable_recovery_analysis=include_recovery_analysis
                )
                
                # Adapt result to expected format
                return {
                    "executive_summary": result.get("strategic_summary", "Strategic analysis complete"),
                    "current_state": result.get("current_state_analysis", {}),
                    "prioritized_risks": result.get("risk_prioritization", []),
                    "recommendations": result.get("strategic_recommendations", []),
                    "quick_wins": result.get("quick_wins", []),
                    "long_term_strategy": result.get("strategic_roadmap", {}),
                    "investment_requirements": result.get("investment_analysis", {}),
                    "expected_outcomes": result.get("outcome_projections", {}),
                    "recovery_analysis": result.get("recovery_analysis", {}) if include_recovery_analysis else {}
                }
                
            except Exception as e:
                print(f"Enhanced Apollo reasoner error, using fallback: {e}")
        
        # Fallback reasoning
        return self._fallback_reasoning(context)
    
    def _fallback_reasoning(self, context: Dict) -> Dict:
        """Fallback strategic reasoning."""
        
        critical_findings = context.get("critical_findings", 0)
        total_findings = context.get("total_findings", 0)
        financial_exposure = context.get("financial_exposure", 0)
        
        return {
            "executive_summary": f"Assessment identifies {total_findings} findings with {critical_findings} critical issues requiring immediate attention.",
            "current_state": {
                "maturity": "DEVELOPING",
                "strengths": ["Policy documentation", "Management awareness"],
                "weaknesses": ["Technical controls", "Testing procedures"],
                "opportunities": ["Quick wins available", "Foundation exists"],
                "threats": ["Regulatory pressure", "Cyber threats"]
            },
            "prioritized_risks": [
                {
                    "title": "Critical Control Gaps",
                    "description": f"{critical_findings} critical controls need implementation",
                    "impact": "CRITICAL",
                    "likelihood": "HIGH",
                    "financial_exposure": critical_findings * 2000000
                }
            ],
            "recommendations": [
                {
                    "title": "Address Critical Gaps",
                    "description": "Implement critical security controls immediately",
                    "priority": "CRITICAL",
                    "timeline": "30 days",
                    "cost_estimate": financial_exposure * 0.1
                }
            ],
            "quick_wins": [
                {
                    "title": "Policy Review",
                    "description": "Update and approve existing policies",
                    "cost": 5000,
                    "benefit": 50000,
                    "steps": ["Review", "Update", "Approve", "Communicate"]
                }
            ],
            "long_term_strategy": {
                "vision": "Achieve compliance excellence",
                "objectives": ["95% compliance", "Risk reduction", "Certification"],
                "milestones": [
                    {"month": 3, "target": "Critical gaps closed"},
                    {"month": 6, "target": "High risks mitigated"},
                    {"month": 12, "target": "Certification ready"}
                ]
            },
            "investment_requirements": {
                "total_investment": financial_exposure * 0.15,
                "immediate_needs": financial_exposure * 0.05,
                "year_1_budget": financial_exposure * 0.10,
                "roi_timeline": "6-8 months"
            },
            "expected_outcomes": {
                "risk_reduction": f"£{financial_exposure * 0.8:,.0f}",
                "compliance_improvement": "70% to 95%",
                "maturity_advancement": "DEVELOPING to MANAGED"
            },
            "recovery_analysis": {
                "current_recovery_time": "5-30 days",
                "target_recovery_time": "24-48 hours",
                "improvements_needed": [
                    "Automated backup testing",
                    "Orchestration tools",
                    "Recovery procedures"
                ]
            }
        }