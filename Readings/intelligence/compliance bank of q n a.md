# Auditor Question Bank – ISO 27001, Essential 8, NIST CSF, GDPR

This file contains a comprehensive list of **auditor-style questions** with rationale and notes.  
Use this to train AI agents to extract evidence from PDFs, anticipate permutations, and assist human auditors.  
⚠️ **Note:** AI assists, but auditor judgment remains critical.  

---

## 1. ISO 27001 (Information Security Management System)

### Scope & Context
- **Q1:** What is the defined scope of the ISMS (systems, departments, locations)?  
  - *Logic:* Ensures boundaries are defined, avoids gaps.  
  - *AI Role:* Can extract from “Scope of ISMS” or “Policy” sections.  
  - *Human Needed:* Confirm alignment with actual operations.  

- **Q2:** Who are the interested parties and their information security requirements?  
  - *Logic:* Clauses 4.2 & 4.3 require stakeholder analysis.  
  - *AI Role:* Identify stakeholders listed.  
  - *Human Needed:* Validate accuracy and completeness.  

### Leadership
- **Q3:** Is there a documented Information Security Policy signed by top management?  
  - *Logic:* Clause 5.2. Shows leadership commitment.  
  - *AI Role:* Locate signed policy PDF.  
  - *Human Needed:* Confirm current version and approval.  

- **Q4:** How is leadership commitment to ISMS demonstrated?  
  - *Logic:* Required by ISO 27001 for accountability.  
  - *AI Role:* Look for management review records.  
  - *Human Needed:* Interview executives for evidence.  

### Risk Management
- **Q5:** What is the documented risk assessment methodology?  
  - *Logic:* Clause 6.1.2 requires a formal method.  
  - *AI Role:* Extract from Risk Policy/Risk Register.  
  - *Human Needed:* Verify if actually followed.  

- **Q6:** Are risk treatment plans documented and monitored?  
  - *Logic:* Required to show mitigation.  
  - *AI Role:* Extract treatment plan references.  
  - *Human Needed:* Verify implementation.  

### Operational Controls
- **Q7:** How are incidents reported and managed?  
  - *Logic:* Annex A.16 Incident Management.  
  - *AI Role:* Find Incident Response Policy.  
  - *Human Needed:* Test process in practice.  

- **Q8:** Are backups defined, tested, and retained?  
  - *Logic:* Annex A.12.3 Backup.  
  - *AI Role:* Extract backup procedures.  
  - *Human Needed:* Review test evidence.  

### Monitoring & Improvement
- **Q9:** How often are internal ISMS audits performed?  
  - *Logic:* Clause 9.2 requires planned audits.  
  - *AI Role:* Look for Internal Audit Schedule.  
  - *Human Needed:* Check execution records.  

- **Q10:** Are nonconformities and corrective actions tracked?  
  - *Logic:* Clause 10.1 requires continual improvement.  
  - *AI Role:* Extract NC register references.  
  - *Human Needed:* Confirm closure status.  

---

## 2. Essential 8 (Australian Cyber Security Centre)

- **Q1:** Are application patches applied within 48 hours for critical updates?  
  - *Logic:* Mitigates exploitation risk.  
  - *AI Role:* Check patch management policy.  
  - *Human Needed:* Validate logs.  

- **Q2:** Are macros disabled or restricted in Office documents?  
  - *Logic:* Prevents malware delivery.  
  - *AI Role:* Locate Office security policy.  
  - *Human Needed:* Verify via endpoint config.  

- **Q3:** Are daily backups performed and tested?  
  - *Logic:* Mitigates ransomware impact.  
  - *AI Role:* Extract backup schedule.  
  - *Human Needed:* Confirm test restores.  

- **Q4:** Is MFA enforced for all privileged accounts?  
  - *Logic:* Prevents credential abuse.  
  - *AI Role:* Locate IAM/Access policy.  
  - *Human Needed:* Confirm implementation logs.  

---

## 3. NIST Cybersecurity Framework (CSF)

### Identify
- **Q1:** Have assets (hardware, software, data) been inventoried?  
  - *Logic:* CSF-ID.AM.  
  - *AI Role:* Extract asset register mentions.  
  - *Human Needed:* Confirm completeness.  

### Protect
- **Q2:** Are access controls enforced (least privilege, role-based)?  
  - *Logic:* CSF-PR.AC.  
  - *AI Role:* Locate Access Control Policy.  
  - *Human Needed:* Review system configs.  

### Detect
- **Q3:** Is continuous monitoring in place for anomalies?  
  - *Logic:* CSF-DE.CM.  
  - *AI Role:* Extract SIEM/monitoring procedure references.  
  - *Human Needed:* Confirm alerts reviewed.  

### Respond
- **Q4:** Is there a documented Incident Response Plan with roles defined?  
  - *Logic:* CSF-RS.RP.  
  - *AI Role:* Locate IR policy.  
  - *Human Needed:* Validate tabletop test.  

### Recover
- **Q5:** Are recovery plans tested periodically?  
  - *Logic:* CSF-RC.RP.  
  - *AI Role:* Locate BCP/DR policy.  
  - *Human Needed:* Confirm test reports.  

---

## 4. GDPR (Data Protection)

- **Q1:** What categories of personal data are collected and processed?  
  - *Logic:* Art. 30 records of processing.  
  - *AI Role:* Extract Data Inventory.  
  - *Human Needed:* Confirm with DPO.  

- **Q2:** What lawful bases are documented for each processing activity?  
  - *Logic:* Art. 6 requirement.  
  - *AI Role:* Locate Consent/Contractual basis.  
  - *Human Needed:* Validate actual consent flows.  

- **Q3:** How are data subject rights (access, rectification, erasure) handled?  
  - *Logic:* Art. 15–22 compliance.  
  - *AI Role:* Extract DSAR procedure.  
  - *Human Needed:* Verify request handling evidence.  

- **Q4:** Are Data Processing Agreements (DPAs) in place with third parties?  
  - *Logic:* Art. 28 controller-processor obligations.  
  - *AI Role:* Locate supplier agreements.  
  - *Human Needed:* Confirm signed copies.  

- **Q5:** What breach notification process exists (72-hour rule)?  
  - *Logic:* Art. 33–34.  
  - *AI Role:* Extract Incident/Breach policy.  
  - *Human Needed:* Confirm drills/tests.  

---

# Notes for AI Training
- Use **permutation detection**: different auditors ask the same thing differently.  
- Always output **source document reference** (doc name, section, paragraph).  
- Mark questions as **AI-preloadable** vs **needs auditor confirmation**.  
- Always include **follow-up questions**: e.g. *“Can you provide evidence logs?”*  
- AI should empower auditors, not replace them.  

