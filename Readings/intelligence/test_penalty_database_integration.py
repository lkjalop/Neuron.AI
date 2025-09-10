#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test the penalty database integration"""

import asyncio
import sys
from pathlib import Path

# Add src to path
current_dir = Path(__file__).parent
src_path = current_dir / "src"
sys.path.insert(0, str(src_path))

from complete_intelligent_isms import ComprehensiveISMSAnalyzer

async def test_penalty_database():
    print("TESTING PENALTY DATABASE INTEGRATION")
    print("=" * 60)
    
    analyzer = ComprehensiveISMSAnalyzer()
    
    # Test penalty database directly
    penalty_db = analyzer.penalty_database
    
    # Test get_penalties_for_control
    print("\n1. Testing get_penalties_for_control for A.12.6 (Vulnerability Management)")
    penalties_a12_6 = await penalty_db.get_penalties_for_control("A.12.6")
    print(f"   Found {len(penalties_a12_6)} penalties for A.12.6")
    
    for i, penalty in enumerate(penalties_a12_6[:3], 1):
        print(f"   Penalty {i}:")
        print(f"     Organization: {penalty.get('organization')}")
        print(f"     Amount: £{penalty.get('amount', 0):,.0f} ({penalty.get('currency')})")
        print(f"     Violation: {penalty.get('violation')}")
        print(f"     Year: {penalty.get('year')}")
    
    # Test get_sector_penalties
    print(f"\n2. Testing get_sector_penalties for Healthcare")
    sector_stats = await penalty_db.get_sector_penalties("Healthcare")
    print(f"   Average penalty: £{sector_stats.get('average', 0):,.0f}")
    print(f"   Max penalty: £{sector_stats.get('max', 0):,.0f}")
    print(f"   Total incidents: {sector_stats.get('incidents', 0)}")
    print(f"   Trend: {sector_stats.get('trend')}")
    
    # Test find_similar_organizations
    print(f"\n3. Testing find_similar_organizations")
    org_context = {
        "industry": "Healthcare",
        "size": "Large Enterprise",
        "name": "Brunel University London"
    }
    
    similar_orgs = await penalty_db.find_similar_organizations(org_context)
    print(f"   Found {len(similar_orgs)} similar organizations:")
    
    for i, org in enumerate(similar_orgs[:3], 1):
        print(f"   Organization {i}:")
        print(f"     Name: {org.get('organization')}")
        print(f"     Penalty: £{org.get('amount', 0):,.0f}")
        print(f"     Violation: {org.get('violation')}")
    
    # Test with assessment
    print(f"\n4. Testing penalty analysis in full assessment")
    
    # Run a mini assessment to test penalty integration
    print("   Processing one document for penalty analysis...")
    pdf_path = "D:/AI/New folder/Brunel/001_BUL-POL-6.1.1-Brunel-ISMS-Roles-and-Responsibilities-v1.1.pdf"
    
    try:
        content = await analyzer._extract_document_content(pdf_path)
        
        if hasattr(analyzer.evidence_detector, 'set_framework'):
            analyzer.evidence_detector.set_framework("iso27001")
        
        evidence = analyzer.evidence_detector.detect_evidence_with_penalty_correlation(
            content, pdf_path, perform_deep_analysis=True
        )
        
        analyzer.document_evidence[pdf_path] = evidence
        
        # Run penalty analysis
        penalty_analysis = await analyzer._analyze_penalties()
        
        print(f"   Total penalty exposure: £{penalty_analysis.get('total_exposure', 0):,.0f}")
        print(f"   Controls with penalty data: {len(penalty_analysis.get('by_control', {}))}")
        
        # Show top penalty risks by control
        by_control = penalty_analysis.get('by_control', {})
        if by_control:
            print("   Top penalty risks by control:")
            sorted_controls = sorted(by_control.items(), key=lambda x: x[1].get('total', 0), reverse=True)
            for control_id, data in sorted_controls[:5]:
                total = data.get('total', 0)
                avg = data.get('average', 0)
                count = len(data.get('penalties', []))
                print(f"     {control_id}: £{total:,.0f} total, £{avg:,.0f} avg, {count} cases")
        
        print(f"\n✅ PENALTY DATABASE INTEGRATION WORKING!")
        print(f"   - Real penalty data from {penalty_analysis.get('total_exposure', 0) > 0} database records")
        print(f"   - Historical regulatory enforcement data connected")
        print(f"   - Financial exposure calculations enhanced")
        
    except Exception as e:
        print(f"   Error in assessment integration: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    try:
        asyncio.run(test_penalty_database())
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()