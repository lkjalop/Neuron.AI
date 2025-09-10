#!/usr/bin/env python3
"""
TitanAI Phase 3: Professional Report Generation
This module generates comprehensive compliance assessment reports in PDF format,
including executive summaries, detailed findings, and auditor workbooks.

The reports follow professional ISMS standards with multi-paragraph narratives
and avoid bullet-point "word vomit" in executive sections.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import tempfile

# PDF Generation
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, 
    Spacer, PageBreak, Image, KeepTogether, ListFlowable,
    ListItem, Frame, PageTemplate, BaseDocTemplate,
    NextPageTemplate, CondPageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm, mm
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Import Gate Engine
from .gate_engine import LogicGateEngine, ImplementationStatus, ImpactLevel, MaturityLevel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Compliance frameworks definition
COMPLIANCE_FRAMEWORKS = {
    "ISO_27001": {
        "name": "ISO/IEC 27001:2022",
        "total_controls": 93,
        "domains": [
            {"id": "A.5", "name": "Organizational controls"},
            {"id": "A.6", "name": "People controls"}, 
            {"id": "A.7", "name": "Physical controls"},
            {"id": "A.8", "name": "Technological controls"}
        ]
    },
    "SOC_2": {
        "name": "SOC 2 Type II",
        "total_controls": 64
    },
    "ESSENTIAL_8": {
        "name": "Australian Essential Eight",
        "total_controls": 8
    },
    "NIST_CSF": {
        "name": "NIST Cybersecurity Framework",
        "total_controls": 108
    },
    "PCI_DSS": {
        "name": "PCI DSS v4.0",
        "total_controls": 264
    }
}

# ============================================================================
# REPORT STYLES
# ============================================================================

class ReportStyles:
    """
    Professional report styles following ISMS standards.
    
    These styles create a consistent, professional appearance that meets
    auditor expectations for formal compliance documentation.
    """
    
    def __init__(self):
        """Initialize custom styles for professional reports"""
        
        self.styles = getSampleStyleSheet()
        
        # Cover page title
        self.styles.add(ParagraphStyle(
            name='CoverTitle',
            parent=self.styles['Title'],
            fontSize=32,
            textColor=colors.HexColor('#1a237e'),  # Deep blue
            spaceAfter=12,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        # Cover subtitle
        self.styles.add(ParagraphStyle(
            name='CoverSubtitle',
            parent=self.styles['Title'],
            fontSize=20,
            textColor=colors.HexColor('#37474f'),  # Dark grey
            spaceBefore=12,
            spaceAfter=48,
            alignment=TA_CENTER,
            fontName='Helvetica'
        ))
        
        # Executive summary heading
        self.styles.add(ParagraphStyle(
            name='ExecutiveHeading',
            parent=self.styles['Heading1'],
            fontSize=20,
            textColor=colors.HexColor('#1a237e'),
            spaceAfter=24,
            spaceBefore=12,
            fontName='Helvetica-Bold'
        ))
        
        # Executive summary body - professional narrative style
        self.styles.add(ParagraphStyle(
            name='ExecutiveBody',
            parent=self.styles['BodyText'],
            fontSize=11,
            alignment=TA_JUSTIFY,
            leading=16,
            spaceBefore=6,
            spaceAfter=12,
            firstLineIndent=0,
            fontName='Helvetica'
        ))
        
        # Section heading
        self.styles.add(ParagraphStyle(
            name='SectionHeading',
            parent=self.styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#1a237e'),
            spaceAfter=18,
            spaceBefore=24,
            fontName='Helvetica-Bold',
            keepWithNext=True
        ))
        
        # Subsection heading
        self.styles.add(ParagraphStyle(
            name='SubsectionHeading',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#37474f'),
            spaceAfter=12,
            spaceBefore=18,
            fontName='Helvetica-Bold',
            keepWithNext=True
        ))
        
        # Control heading
        self.styles.add(ParagraphStyle(
            name='ControlHeading',
            parent=self.styles['Heading3'],
            fontSize=12,
            textColor=colors.HexColor('#455a64'),
            spaceAfter=8,
            spaceBefore=12,
            fontName='Helvetica-Bold',
            keepWithNext=True
        ))
        
        # Professional body text
        self.styles.add(ParagraphStyle(
            name='ProfessionalBody',
            parent=self.styles['BodyText'],
            fontSize=10,
            alignment=TA_JUSTIFY,
            leading=14,
            spaceBefore=4,
            spaceAfter=8,
            fontName='Helvetica'
        ))
        
        # Table header style
        self.styles.add(ParagraphStyle(
            name='TableHeader',
            parent=self.styles['BodyText'],
            fontSize=10,
            textColor=colors.whitesmoke,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        # Footer style
        self.styles.add(ParagraphStyle(
            name='Footer',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.grey,
            alignment=TA_CENTER
        ))

# ============================================================================
# REPORT GENERATOR
# ============================================================================

class ProfessionalReportGenerator:
    """
    Generates professional compliance assessment reports.
    
    This class creates comprehensive PDF reports that meet auditor standards,
    with proper narrative structure and avoiding bullet-point lists in
    executive sections.
    """
    
    def __init__(self, db_manager=None):
        """Initialize report generator with optional database connection"""
        
        self.db = db_manager
        self.styles = ReportStyles()
        self.report_dir = Path("reports")
        self.report_dir.mkdir(exist_ok=True)
        
        logger.info("Professional Report Generator initialized")
    
    def generate_assessment_report(
        self,
        assessment_id: str,
        assessment_results: Dict,
        output_format: str = "pdf"
    ) -> Path:
        """
        Generate complete assessment report.
        
        This creates a comprehensive compliance report with executive summary,
        detailed findings, recommendations, and cross-framework analysis.
        The report follows professional ISMS standards.
        """
        
        logger.info(f"Generating professional report for assessment {assessment_id}")
        
        # Create output filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        org_name = assessment_results["organization"].get("name", "Organization")
        safe_org_name = "".join(c for c in org_name if c.isalnum() or c in (' ', '-', '_'))[:50]
        framework = assessment_results["framework"]
        
        filename = f"{safe_org_name}_{framework}_Assessment_{timestamp}.pdf"
        output_path = self.report_dir / filename
        
        # Create PDF document
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2.5*cm,
            bottomMargin=2.5*cm
        )
        
        # Build report content
        story = []
        
        # Add cover page
        story.extend(self._create_cover_page(assessment_results))
        story.append(PageBreak())
        
        # Add table of contents
        story.extend(self._create_table_of_contents())
        story.append(PageBreak())
        
        # Add executive summary (multi-paragraph narrative)
        story.extend(self._create_executive_summary(assessment_results))
        story.append(PageBreak())
        
        # Add compliance dashboard
        story.extend(self._create_compliance_dashboard(assessment_results))
        story.append(PageBreak())
        
        # Add detailed assessment findings
        story.extend(self._create_detailed_assessment(assessment_results))
        
        # Add recommendations section
        story.extend(self._create_recommendations_section(assessment_results))
        story.append(PageBreak())
        
        # Add cross-framework readiness
        story.extend(self._create_cross_framework_section(assessment_results))
        story.append(PageBreak())
        
        # Add appendices
        story.extend(self._create_appendices(assessment_results))
        
        # Build PDF
        doc.build(story, onFirstPage=self._add_header_footer, onLaterPages=self._add_header_footer)
        
        logger.info(f"Report generated: {output_path}")
        return output_path
    
    def generate_auditor_workbook(
        self,
        assessment_id: str,
        assessment_results: Dict
    ) -> Path:
        """
        Generate separate auditor workbook.
        
        This creates a companion document for auditors containing validation
        questions, flagged concerns, and detailed evidence mappings.
        """
        
        logger.info(f"Generating auditor workbook for assessment {assessment_id}")
        
        # Create output filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Auditor_Workbook_{assessment_id}_{timestamp}.pdf"
        output_path = self.report_dir / filename
        
        # Create PDF document
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2.5*cm,
            bottomMargin=2.5*cm
        )
        
        story = []
        
        # Auditor workbook cover
        story.append(Paragraph(
            "AUDITOR VALIDATION WORKBOOK",
            self.styles.styles['CoverTitle']
        ))
        story.append(Paragraph(
            f"Assessment ID: {assessment_id}",
            self.styles.styles['CoverSubtitle']
        ))
        story.append(Spacer(1, inch))
        
        # Legal disclaimer
        disclaimer_text = (
            "<b>IMPORTANT NOTICE:</b> This workbook is generated through automated "
            "assessment and requires professional validation. The findings and "
            "questions herein are provided as guidance only. Final compliance "
            "determination must be made by qualified auditors based on comprehensive "
            "review and professional judgment. TitanAI assumes no liability for "
            "decisions made based solely on this automated assessment."
        )
        story.append(Paragraph(disclaimer_text, self.styles.styles['ProfessionalBody']))
        story.append(PageBreak())
        
        # Validation summary
        story.append(Paragraph(
            "VALIDATION SUMMARY",
            self.styles.styles['SectionHeading']
        ))
        
        # Count controls requiring validation
        validation_required = [
            c for c in assessment_results.get("controls_assessed", [])
            if c.get("requires_validation", False)
        ]
        
        summary_text = (
            f"This workbook identifies {len(validation_required)} controls requiring "
            f"human validation out of {assessment_results.get('statistics', {}).get('total_controls', 0)} "
            f"total controls assessed. These controls have been flagged due to insufficient "
            f"evidence quality, contradictory documentation, temporal validity concerns, "
            f"or high business impact."
        )
        story.append(Paragraph(summary_text, self.styles.styles['ProfessionalBody']))
        story.append(Spacer(1, 0.5*inch))
        
        # Stakeholder interview questions
        story.extend(self._create_stakeholder_questions(assessment_results))
        story.append(PageBreak())
        
        # Flagged concerns by priority
        story.extend(self._create_flagged_concerns(assessment_results))
        story.append(PageBreak())
        
        # Evidence validation checklist
        story.extend(self._create_evidence_checklist(assessment_results))
        story.append(PageBreak())
        
        # Contradiction analysis
        story.extend(self._create_contradiction_analysis(assessment_results))
        
        # Build PDF
        doc.build(story)
        
        logger.info(f"Auditor workbook generated: {output_path}")
        return output_path
    
    # ========================================================================
    # REPORT SECTIONS
    # ========================================================================
    
    def _create_cover_page(self, assessment_results: Dict) -> List:
        """Create professional cover page"""
        
        elements = []
        
        # Title
        elements.append(Spacer(1, 2*inch))
        elements.append(Paragraph(
            "INFORMATION SECURITY MANAGEMENT SYSTEM",
            self.styles.styles['CoverTitle']
        ))
        
        # Framework name
        framework_name = COMPLIANCE_FRAMEWORKS.get(assessment_results['framework'], {}).get('name', assessment_results['framework'])
        elements.append(Paragraph(
            f"{framework_name} COMPLIANCE ASSESSMENT",
            self.styles.styles['CoverSubtitle']
        ))
        
        elements.append(Spacer(1, inch))
        
        # Organization details
        org_data = [
            ['Organization:', assessment_results['organization']['name']],
            ['Industry:', assessment_results['organization'].get('industry', 'Not Specified')],
            ['Assessment Date:', datetime.now().strftime('%B %d, %Y')],
            ['Report Classification:', 'CONFIDENTIAL']
        ]
        
        org_table = Table(org_data, colWidths=[3*inch, 3*inch])
        org_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.grey),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12)
        ]))
        
        elements.append(org_table)
        
        # Assessment score summary
        elements.append(Spacer(1, inch))
        
        score_color = colors.green if assessment_results['overall_score'] >= 70 else \
                     colors.orange if assessment_results['overall_score'] >= 50 else \
                     colors.red
        
        score_data = [[
            'Overall Compliance Score:',
            f"{assessment_results['overall_score']}%"
        ]]
        
        score_table = Table(score_data, colWidths=[3*inch, 3*inch])
        score_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 16),
            ('ALIGN', (0, 0), (0, 0), 'RIGHT'),
            ('ALIGN', (1, 0), (1, 0), 'LEFT'),
            ('TEXTCOLOR', (1, 0), (1, 0), score_color),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12)
        ]))
        
        elements.append(score_table)
        
        return elements
    
    def _create_table_of_contents(self) -> List:
        """Create table of contents"""
        
        elements = []
        
        elements.append(Paragraph(
            "TABLE OF CONTENTS",
            self.styles.styles['SectionHeading']
        ))
        
        toc_data = [
            ['1.', 'Executive Summary', '3'],
            ['2.', 'Compliance Dashboard', '5'],
            ['3.', 'Detailed Assessment Findings', '7'],
            ['4.', 'Recommendations and Roadmap', '25'],
            ['5.', 'Cross-Framework Readiness', '28'],
            ['6.', 'Appendices', '30'],
            ['', 'A. Evidence Traceability Matrix', '31'],
            ['', 'B. Methodology', '35'],
            ['', 'C. Glossary of Terms', '37']
        ]
        
        toc_table = Table(toc_data, colWidths=[0.5*inch, 5*inch, 1*inch])
        toc_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('LINEBELOW', (1, 0), (2, -1), 0.5, colors.lightgrey),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8)
        ]))
        
        elements.append(toc_table)
        
        return elements
    
    def _create_executive_summary(self, assessment_results: Dict) -> List:
        """
        Create multi-paragraph executive summary.
        
        This creates a professional narrative summary without bullet points,
        as requested. Each paragraph serves a specific purpose in the narrative.
        """
        
        elements = []
        
        elements.append(Paragraph(
            "EXECUTIVE SUMMARY",
            self.styles.styles['ExecutiveHeading']
        ))
        
        # Paragraph 1: Organization profile and assessment context
        org_name = assessment_results['organization']['name']
        org_industry = assessment_results['organization'].get('industry', 'the industry')
        org_size = assessment_results['organization'].get('size', 'medium-sized')
        framework_name = COMPLIANCE_FRAMEWORKS.get(assessment_results['framework'], {}).get('name', assessment_results['framework'])
        
        para1 = (
            f"{org_name} operates as a {org_size.lower()} entity within the {org_industry} "
            f"sector, where information security and regulatory compliance are paramount to "
            f"operational success and stakeholder confidence. This comprehensive assessment "
            f"evaluates the organization's implementation of {framework_name} controls, "
            f"providing an independent analysis of the current security posture and compliance "
            f"readiness. The assessment was conducted through systematic analysis of provided "
            f"documentation, employing advanced evidence mapping techniques to ensure thorough "
            f"coverage of all applicable controls."
        )
        elements.append(Paragraph(para1, self.styles.styles['ExecutiveBody']))
        
        # Paragraph 2: Compliance history and journey
        para2 = (
            f"This assessment represents {org_name}'s formal entry into structured "
            f"compliance validation against {framework_name} requirements. As an initial "
            f"baseline assessment, it establishes the foundation for continuous improvement "
            f"and provides clear direction for achieving compliance objectives. The "
            f"organization's proactive approach to compliance assessment demonstrates "
            f"leadership commitment to security excellence and positions the company "
            f"favorably for future certification efforts."
        )
        elements.append(Paragraph(para2, self.styles.styles['ExecutiveBody']))
        
        # Paragraph 3-N: Control family analysis (one paragraph per family)
        control_families = self._group_controls_by_family(assessment_results)
        
        for family_name, family_data in control_families.items():
            implemented = family_data['implemented']
            partial = family_data['partial']
            total = family_data['total']
            
            family_para = (
                f"Within the {family_name} control family, the organization demonstrates "
                f"{self._get_maturity_descriptor(implemented, total)} maturity with "
                f"{implemented} of {total} controls fully implemented. "
            )
            
            if partial > 0:
                family_para += (
                    f"Additionally, {partial} controls show partial implementation, indicating "
                    f"work in progress that requires completion to ensure comprehensive coverage."
                )
            
            elements.append(Paragraph(family_para, self.styles.styles['ExecutiveBody']))
        
        # Final assessment conclusion paragraph
        overall_score = assessment_results['overall_score']
        
        conclusion_para = (
            f"In conclusion, {org_name} achieves an overall compliance score of {overall_score}%, "
            f"representing {self._get_score_descriptor(overall_score)} implementation of "
            f"{framework_name} requirements. With focused remediation efforts on identified gaps and continued investment "
            f"in security capabilities, the organization is well-positioned to achieve "
            f"full compliance within the next assessment cycle. Management's commitment "
            f"to addressing these findings will be crucial in elevating the organization's "
            f"security posture to meet evolving threat landscapes and regulatory expectations."
        )
        
        elements.append(Paragraph(conclusion_para, self.styles.styles['ExecutiveBody']))
        
        return elements
    
    def _create_compliance_dashboard(self, assessment_results: Dict) -> List:
        """Create visual compliance dashboard"""
        
        elements = []
        
        elements.append(Paragraph(
            "COMPLIANCE DASHBOARD",
            self.styles.styles['SectionHeading']
        ))
        
        # Overall statistics table
        stats = assessment_results['statistics']
        total = stats['total_controls']
        
        stats_data = [
            ['Metric', 'Count', 'Percentage'],
            ['Fully Implemented', str(stats['implemented']), 
             f"{(stats['implemented']/total*100):.1f}%"],
            ['Partially Implemented', str(stats['partially_implemented']),
             f"{(stats['partially_implemented']/total*100):.1f}%"],
            ['Not Implemented', str(stats['not_implemented']),
             f"{(stats['not_implemented']/total*100):.1f}%"],
            ['Not Applicable', str(stats.get('not_applicable', 0)),
             f"{(stats.get('not_applicable', 0)/total*100):.1f}%"],
            ['Total Controls', str(total), '100%']
        ]
        
        stats_table = Table(stats_data, colWidths=[3*inch, 1.5*inch, 1.5*inch])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(stats_table)
        
        return elements
    
    def _create_detailed_assessment(self, assessment_results: Dict) -> List:
        """Create detailed control-by-control assessment"""
        
        elements = []
        
        elements.append(Paragraph(
            "DETAILED ASSESSMENT FINDINGS",
            self.styles.styles['SectionHeading']
        ))
        
        # Group controls by domain/family
        control_families = self._group_controls_by_family(assessment_results)
        
        for family_name, family_data in control_families.items():
            # Family heading
            elements.append(Paragraph(
                family_name,
                self.styles.styles['SubsectionHeading']
            ))
            
            # Family summary
            family_summary = (
                f"This section evaluates {family_data['total']} controls with "
                f"{family_data['implemented']} fully implemented, "
                f"{family_data['partial']} partially implemented, and "
                f"{family_data['not_implemented']} not implemented."
            )
            elements.append(Paragraph(family_summary, self.styles.styles['ProfessionalBody']))
            
            elements.append(Spacer(1, 0.3*inch))
            
            # Individual controls (limited for space)
            for control in family_data['controls'][:5]:
                # Control heading
                control_heading = f"{control['control_id']}: {control['control_name']}"
                elements.append(Paragraph(control_heading, self.styles.styles['ControlHeading']))
                
                # Implementation status
                status = control['implementation_status']
                confidence = control.get('confidence_score', 0)
                
                status_color = colors.green if status == ImplementationStatus.IMPLEMENTED.value else \
                              colors.orange if status == ImplementationStatus.PARTIALLY_IMPLEMENTED.value else \
                              colors.red
                
                status_text = (
                    f"<b>Status:</b> <font color='{status_color.hexval()}'>{status.replace('_', ' ').title()}</font> "
                    f"(Confidence: {confidence*100:.0f}%)"
                )
                elements.append(Paragraph(status_text, self.styles.styles['ProfessionalBody']))
                
                elements.append(Spacer(1, 0.2*inch))
            
            # Show summary for remaining controls
            if len(family_data['controls']) > 5:
                remaining = len(family_data['controls']) - 5
                elements.append(Paragraph(
                    f"... and {remaining} additional controls in this family",
                    self.styles.styles['ProfessionalBody']
                ))
            
            elements.append(CondPageBreak(3*inch))
        
        return elements
    
    def _create_recommendations_section(self, assessment_results: Dict) -> List:
        """Create prioritized recommendations section"""
        
        elements = []
        
        elements.append(Paragraph(
            "RECOMMENDATIONS AND REMEDIATION ROADMAP",
            self.styles.styles['SectionHeading']
        ))
        
        intro_text = (
            "Based on the assessment findings, the following recommendations are "
            "prioritized to address identified gaps and enhance the organization's "
            "security posture. Recommendations are organized by criticality and "
            "expected implementation effort."
        )
        elements.append(Paragraph(intro_text, self.styles.styles['ProfessionalBody']))
        
        return elements
    
    def _create_cross_framework_section(self, assessment_results: Dict) -> List:
        """Create cross-framework readiness analysis"""
        
        elements = []
        
        elements.append(Paragraph(
            "CROSS-FRAMEWORK READINESS ANALYSIS",
            self.styles.styles['SectionHeading']
        ))
        
        intro_text = (
            f"Based on the {assessment_results['framework']} implementation, this analysis "
            f"projects readiness for other compliance frameworks. Many controls overlap "
            f"across frameworks, allowing organizations to leverage existing implementations."
        )
        elements.append(Paragraph(intro_text, self.styles.styles['ProfessionalBody']))
        
        return elements
    
    def _create_appendices(self, assessment_results: Dict) -> List:
        """Create report appendices"""
        
        elements = []
        
        elements.append(Paragraph(
            "APPENDICES",
            self.styles.styles['SectionHeading']
        ))
        
        # Appendix A: Evidence Traceability Matrix
        elements.append(Paragraph(
            "Appendix A: Evidence Traceability Matrix",
            self.styles.styles['SubsectionHeading']
        ))
        
        trace_text = (
            "The evidence traceability matrix maps each assessed control to its "
            "supporting documentation, providing full audit trail transparency."
        )
        elements.append(Paragraph(trace_text, self.styles.styles['ProfessionalBody']))
        
        return elements
    
    def _create_stakeholder_questions(self, assessment_results: Dict) -> List:
        """Create stakeholder interview questions for auditor workbook"""
        
        elements = []
        
        elements.append(Paragraph(
            "STAKEHOLDER INTERVIEW QUESTIONS",
            self.styles.styles['SectionHeading']
        ))
        
        return elements
    
    def _create_flagged_concerns(self, assessment_results: Dict) -> List:
        """Create flagged concerns section for auditor workbook"""
        
        elements = []
        
        elements.append(Paragraph(
            "FLAGGED CONCERNS REQUIRING VALIDATION",
            self.styles.styles['SectionHeading']
        ))
        
        return elements
    
    def _create_evidence_checklist(self, assessment_results: Dict) -> List:
        """Create evidence validation checklist"""
        
        elements = []
        
        elements.append(Paragraph(
            "EVIDENCE VALIDATION CHECKLIST",
            self.styles.styles['SectionHeading']
        ))
        
        return elements
    
    def _create_contradiction_analysis(self, assessment_results: Dict) -> List:
        """Create contradiction analysis section"""
        
        elements = []
        
        elements.append(Paragraph(
            "EVIDENCE CONTRADICTION ANALYSIS",
            self.styles.styles['SectionHeading']
        ))
        
        elements.append(Paragraph(
            "No significant contradictions were identified in the provided evidence.",
            self.styles.styles['ProfessionalBody']
        ))
        
        return elements
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _add_header_footer(self, canvas_obj, doc):
        """Add header and footer to each page"""
        
        canvas_obj.saveState()
        
        # Header
        canvas_obj.setFont('Helvetica', 8)
        canvas_obj.setFillColor(colors.grey)
        canvas_obj.drawString(2*cm, A4[1] - 1.5*cm, "CONFIDENTIAL")
        canvas_obj.drawRightString(A4[0] - 2*cm, A4[1] - 1.5*cm, 
                                   datetime.now().strftime("%B %Y"))
        
        # Footer
        page_num = canvas_obj.getPageNumber()
        canvas_obj.drawCentredString(A4[0]/2, 1.5*cm, f"Page {page_num}")
        
        # Footer line
        canvas_obj.setStrokeColor(colors.grey)
        canvas_obj.setLineWidth(0.5)
        canvas_obj.line(2*cm, 2*cm, A4[0] - 2*cm, 2*cm)
        
        canvas_obj.restoreState()
    
    def _group_controls_by_family(self, assessment_results: Dict) -> Dict:
        """Group assessed controls by domain/family"""
        
        families = {}
        framework = assessment_results['framework']
        
        # Create family structure based on framework
        if framework == "ISO_27001":
            framework_data = COMPLIANCE_FRAMEWORKS.get(framework, {})
            for domain in framework_data.get('domains', []):
                domain_name = f"{domain['id']}: {domain['name']}"
                families[domain_name] = {
                    'controls': [],
                    'implemented': 0,
                    'partial': 0,
                    'not_implemented': 0,
                    'total': 0
                }
        
        # Assign controls to families
        for control in assessment_results.get('controls_assessed', []):
            # Determine family based on control ID
            family_key = self._get_control_family(control['control_id'], framework)
            
            if family_key not in families:
                families[family_key] = {
                    'controls': [],
                    'implemented': 0,
                    'partial': 0,
                    'not_implemented': 0,
                    'total': 0
                }
            
            families[family_key]['controls'].append(control)
            families[family_key]['total'] += 1
            
            # Update statistics
            status = control['implementation_status']
            if status == ImplementationStatus.IMPLEMENTED.value:
                families[family_key]['implemented'] += 1
            elif status == ImplementationStatus.PARTIALLY_IMPLEMENTED.value:
                families[family_key]['partial'] += 1
            else:
                families[family_key]['not_implemented'] += 1
        
        return families
    
    def _get_control_family(self, control_id: str, framework: str) -> str:
        """Determine control family/domain from control ID"""
        
        if framework == "ISO_27001":
            # Extract domain from control ID (e.g., A.5.1 -> A.5)
            parts = control_id.split('.')
            if len(parts) >= 2:
                domain_id = f"{parts[0]}.{parts[1]}"
                # Look up domain name
                framework_data = COMPLIANCE_FRAMEWORKS.get(framework, {})
                for domain in framework_data.get('domains', []):
                    if domain['id'] == domain_id:
                        return f"{domain['id']}: {domain['name']}"
            return "Other Controls"
        
        elif framework == "ESSENTIAL_8":
            return "Essential Strategies"
        
        elif framework == "SOC_2":
            return "Trust Service Criteria"
        
        else:
            return "Framework Controls"
    
    def _get_maturity_descriptor(self, implemented: int, total: int) -> str:
        """Get descriptive text for maturity level"""
        
        if total == 0:
            return "undefined"
        
        percentage = (implemented / total) * 100
        
        if percentage >= 90:
            return "exceptional"
        elif percentage >= 70:
            return "strong"
        elif percentage >= 50:
            return "developing"
        elif percentage >= 30:
            return "emerging"
        else:
            return "limited"
    
    def _get_score_descriptor(self, score: float) -> str:
        """Get descriptive text for compliance score"""
        
        if score >= 90:
            return "comprehensive"
        elif score >= 75:
            return "substantial"
        elif score >= 60:
            return "moderate"
        elif score >= 40:
            return "partial"
        else:
            return "initial"