#!/usr/bin/env python3
"""
PROPER APOLLO REASONER IMPLEMENTATION
This generates actual strategic business insights using local AI models.
"""

import requests
import json
from typing import Dict, List, Any
from dataclasses import dataclass

@dataclass
class StrategicInsight:
    question: str
    analysis: str
    recommendations: List[str]
    business_impact: str
    implementation_priority: str
    estimated_cost: str
    estimated_timeline: str
    confidence_score: float

class ProperApolloReasoner:
    """Strategic reasoning using local Ollama models"""
    
    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_url = ollama_url
        self.model = "llama3.2"
    
    def query_ollama(self, prompt: str) -> str:
        """Query local Ollama model for strategic analysis"""
        try:
            response = requests.post(f"{self.ollama_url}/api/generate", json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "max_tokens": 2000
                }
            }, timeout=30)
            
            if response.status_code == 200:
                return response.json().get('response', '')
            else:
                return f"Error: {response.status_code}"
        
        except Exception as e:
            return f"Failed to connect to Ollama: {str(e)}"
    
    def analyze_strategic_question(self, 
                                   question: str, 
                                   organization: str,
                                   assessment_data: Dict,
                                   evidence_summary: List[str]) -> StrategicInsight:
        """
        Generate strategic analysis using local AI model.
        This replaces the broken template-based approach.
        """
        
        # Build context-rich prompt
        context_prompt = f"""
You are a senior information security consultant analyzing ISO 27001 compliance for {organization}.

ASSESSMENT CONTEXT:
- Organization: {organization}
- Total controls assessed: {assessment_data.get('total_controls', 'Unknown')}
- Overall maturity: {assessment_data.get('overall_maturity', 0):.1%}
- Critical gaps: {assessment_data.get('total_gaps', 'Unknown')}

EVIDENCE SUMMARY:
{chr(10).join(evidence_summary[:5])}

STRATEGIC QUESTION: {question}

Please provide a detailed strategic analysis including:
1. Current situation assessment
2. Business impact analysis  
3. Specific recommendations
4. Implementation priority (Critical/High/Medium/Low)
5. Estimated cost range
6. Implementation timeline
7. Success metrics

Format your response as structured analysis focusing on business value and practical implementation.
"""

        # Get AI analysis
        ai_response = self.query_ollama(context_prompt)
        
        # Parse the response (simple approach - could be enhanced with structured output)
        recommendations = self._extract_recommendations(ai_response)
        business_impact = self._extract_business_impact(ai_response)
        priority = self._extract_priority(ai_response)
        cost = self._extract_cost_estimate(ai_response)
        timeline = self._extract_timeline(ai_response)
        
        return StrategicInsight(
            question=question,
            analysis=ai_response,
            recommendations=recommendations,
            business_impact=business_impact,
            implementation_priority=priority,
            estimated_cost=cost,
            estimated_timeline=timeline,
            confidence_score=0.85  # Could be calculated based on evidence quality
        )
    
    def _extract_recommendations(self, response: str) -> List[str]:
        """Extract specific recommendations from AI response"""
        recommendations = []
        lines = response.split('\n')
        
        in_recommendations = False
        for line in lines:
            line = line.strip()
            if any(word in line.lower() for word in ['recommend', 'suggestion', 'action']):
                in_recommendations = True
            elif in_recommendations and (line.startswith('-') or line.startswith('•') or line.startswith('1.')):
                recommendations.append(line.lstrip('-•1234567890. '))
            elif in_recommendations and line == '':
                break
        
        return recommendations[:5]  # Top 5 recommendations
    
    def _extract_business_impact(self, response: str) -> str:
        """Extract business impact from AI response"""
        impact_keywords = ['business impact', 'financial impact', 'risk reduction', 'roi', 'value']
        lines = response.split('\n')
        
        for i, line in enumerate(lines):
            if any(keyword in line.lower() for keyword in impact_keywords):
                # Return this line and next few lines
                impact_lines = []
                for j in range(i, min(i+3, len(lines))):
                    if lines[j].strip():
                        impact_lines.append(lines[j].strip())
                return ' '.join(impact_lines)
        
        return "Business impact analysis not available"
    
    def _extract_priority(self, response: str) -> str:
        """Extract implementation priority"""
        if any(word in response.lower() for word in ['critical', 'urgent', 'immediate']):
            return "Critical"
        elif any(word in response.lower() for word in ['high priority', 'high', 'important']):
            return "High"
        elif any(word in response.lower() for word in ['medium', 'moderate']):
            return "Medium"
        else:
            return "Low"
    
    def _extract_cost_estimate(self, response: str) -> str:
        """Extract cost estimates from response"""
        cost_patterns = ['$', 'cost', 'budget', 'investment', 'funding']
        lines = response.split('\n')
        
        for line in lines:
            if any(pattern in line.lower() for pattern in cost_patterns):
                if '$' in line:
                    return line.strip()
                elif any(word in line.lower() for word in ['low cost', 'minimal', 'inexpensive']):
                    return "Low cost (<$50K)"
                elif any(word in line.lower() for word in ['high cost', 'expensive', 'significant']):
                    return "High cost (>$200K)"
        
        return "Cost estimate not provided"
    
    def _extract_timeline(self, response: str) -> str:
        """Extract timeline estimates"""
        timeline_keywords = ['month', 'week', 'timeline', 'duration', 'time']
        lines = response.split('\n')
        
        for line in lines:
            if any(keyword in line.lower() for keyword in timeline_keywords):
                if any(word in line.lower() for word in ['6 month', 'six month']):
                    return "6 months"
                elif any(word in line.lower() for word in ['3 month', 'three month', 'quarter']):
                    return "3 months"
                elif any(word in line.lower() for word in ['1 month', 'one month', '30 day']):
                    return "1 month"
        
        return "Timeline not specified"

def test_apollo_reasoner():
    """Test the Apollo Reasoner with real strategic questions"""
    reasoner = ProperApolloReasoner()
    
    # Test with sample data
    sample_assessment = {
        'total_controls': 33,
        'overall_maturity': 0.65,
        'total_gaps': 8
    }
    
    sample_evidence = [
        "Security policy exists but lacks management approval documentation",
        "Access control procedures documented but not regularly reviewed", 
        "Training program exists but effectiveness not measured",
        "Incident response plan identified but testing not documented"
    ]
    
    strategic_questions = [
        "What is the optimal implementation sequence to achieve ISO 27001 certification within 12 months?",
        "What are the top 5 quick wins that will provide highest ROI for security investment?",
        "How should the organization prioritize security investments to minimize business risk?"
    ]
    
    print("Testing Proper Apollo Reasoner...")
    
    for i, question in enumerate(strategic_questions[:1]):  # Test first question only
        print(f"\n=== Strategic Analysis {i+1} ===")
        print(f"Question: {question}")
        
        insight = reasoner.analyze_strategic_question(
            question=question,
            organization="Brunel University London",
            assessment_data=sample_assessment,
            evidence_summary=sample_evidence
        )
        
        print(f"\nPriority: {insight.implementation_priority}")
        print(f"Cost: {insight.estimated_cost}")
        print(f"Timeline: {insight.estimated_timeline}")
        print(f"\nRecommendations:")
        for rec in insight.recommendations[:3]:
            print(f"  • {rec}")
        
        print(f"\nFull Analysis Preview:")
        print(insight.analysis[:300] + "..." if len(insight.analysis) > 300 else insight.analysis)

if __name__ == "__main__":
    test_apollo_reasoner()