#!/usr/bin/env python3
"""
Open Neuron-AI Frontend Interfaces
Shows all the existing UI components including NLP/RAG chat
"""

import webbrowser
import time
import requests
import json

def main():
    print("="*60)
    print("NEURON-AI FRONTEND INTERFACES")
    print("="*60)
    
    # Base URLs
    frontend_base = "http://localhost:5000"
    api_base = "http://localhost:8000"
    
    print(f"\nFrontend served from: {frontend_base}")
    print(f"API backend running at: {api_base}")
    
    # Check servers
    try:
        requests.get(frontend_base, timeout=2)
        print("✅ Frontend server: ONLINE")
    except:
        print("❌ Frontend server: OFFLINE")
        print("   Run: python -m http.server 5000 --directory frontend")
        return
        
    try:
        requests.get(f"{api_base}/docs", timeout=2)
        print("✅ API server: ONLINE") 
    except:
        print("❌ API server: OFFLINE")
        print("   Run: cd src && python -m uvicorn core.main:app --reload")
        return
    
    print(f"\n🌐 OPENING FRONTEND INTERFACES...")
    print("-"*50)
    
    # Main interfaces
    interfaces = [
        ("Main NLP Chat Interface", f"{frontend_base}/index.html"),
        ("SOC Analyst Chat (Specialized)", f"{frontend_base}/soc.html"), 
        ("Dashboard", f"{frontend_base}/dashboard.html"),
        ("Vulnerability Management", f"{frontend_base}/vuln.html"),
        ("Forensics Interface", f"{frontend_base}/forensics.html"),
        ("Threat Hunting & IOCs", f"{frontend_base}/hunt.html"),
        ("System Diagnostics", f"{frontend_base}/diagnostics.html"),
        ("API Documentation", f"{api_base}/docs")
    ]
    
    for name, url in interfaces:
        print(f"   🔗 {name}")
        print(f"      {url}")
        webbrowser.open(url)
        time.sleep(0.5)  # Stagger to avoid browser issues
    
    print(f"\n🤖 TESTING NLP/RAG CAPABILITIES...")
    print("-"*50)
    
    # Test queries for the NLP system
    sample_queries = [
        "What is CVE-2021-44228?",
        "Show me critical vulnerabilities",
        "How do I respond to ransomware?",
        "Find APT indicators",
        "List recent security events"
    ]
    
    print(f"\n📝 Try these sample queries in the chat interface:")
    for i, query in enumerate(sample_queries, 1):
        print(f"   {i}. {query}")
    
    # Test semantic search endpoint
    try:
        print(f"\n🔍 Testing semantic search API...")
        response = requests.get(f"{api_base}/semantic/search?q=vulnerability management&limit=3")
        if response.status_code == 200:
            results = response.json()
            print(f"   ✅ Semantic search working - found {results.get('count', 0)} results")
        else:
            print(f"   ⚠️  Semantic search returned: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Semantic search error: {e}")
    
    # Test knowledge search
    try:
        print(f"\n📚 Testing knowledge search API...")
        response = requests.get(f"{api_base}/knowledge/search?q=security&limit=3")
        if response.status_code == 200:
            results = response.json()
            print(f"   ✅ Knowledge search working - found {results.get('count', 0)} articles")
        else:
            print(f"   ⚠️  Knowledge search returned: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Knowledge search error: {e}")
    
    print(f"\n" + "="*60)
    print("HOW TO TEST NLP/RAG SYSTEM")
    print("="*60)
    
    print(f"""
🎯 MAIN CHAT INTERFACE ({frontend_base}/index.html):
   • Natural language queries about vulnerabilities
   • Context-aware responses with citations
   • Real-time RAG document retrieval
   • Confidence scoring for answers

🎯 SOC ANALYST CHAT ({frontend_base}/soc.html):
   • Specialized for SOC workflows
   • Playbook recommendations
   • IOC enrichment queries
   • Threat hunting assistance

🔧 FEATURES TO TEST:
   1. Ask: "What is Log4Shell?"
   2. Query: "Show me ransomware indicators"
   3. Request: "How to investigate data exfiltration?"
   4. Search: "MITRE ATT&CK techniques for persistence"
   5. Ask: "What are the top critical vulnerabilities?"

📊 DASHBOARD FEATURES:
   • Real-time security metrics
   • Vulnerability trend analysis  
   • Asset exposure scoring
   • Executive reporting

🔍 THREAT HUNTING:
   • IOC correlation engine
   • Advanced query builder
   • Timeline analysis
   • Behavioral detection patterns

🧪 FORENSIC ANALYSIS:
   • Digital evidence processing
   • Memory dump analysis
   • Network traffic analysis
   • Chain of custody tracking
""")
    
    print(f"\n💡 The system includes:")
    print("   • RAG (Retrieval-Augmented Generation)")
    print("   • Semantic vector search")
    print("   • Knowledge graph navigation")
    print("   • Real-time confidence scoring")
    print("   • Multi-modal security analysis")
    
    print(f"\n🚀 All interfaces are now open in your browser!")
    print("   Start with the main chat to test NLP capabilities.")

if __name__ == "__main__":
    main()