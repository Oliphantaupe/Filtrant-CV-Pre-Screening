# Work Package 1 — Project Specification (Cahier des Charges)
## Automated CV Pre-Screening System
### Client: LuxTalent Advisory Group S.A.

---

## PART I — Context and Project Situation

### 1. Client Presentation

LuxTalent Advisory Group S.A. is a Luxembourg-based recruitment and consulting company that operates across multiple European markets. The company provides staffing solutions for financial institutions, IT companies, industrial actors, and public organizations. Over the past five years, its activity has expanded significantly, both in terms of volume and geographical reach.

As a result of this growth, the Human Resources department has experienced a steady increase in the number of applications received for each open position. For some technical roles, dozens of CVs may be submitted within a single day. For broader profiles, this number can rise even further.

Historically, LuxTalent has relied on experienced HR consultants to manually read, interpret, and filter CVs during the first stage of recruitment. This initial screening phase aims to determine which candidates should be invited to the interview stage. While this method allows for human judgment and contextual understanding, it also presents several challenges:

- Time constraints when application volumes peak
- Variability between consultants in evaluation criteria
- Limited traceability of decision logic
- Difficulty in standardizing pre-selection practices

Over time, the company has accumulated substantial historical data, including archived CVs, internal summaries, and records indicating whether candidates were invited to interviews. Management believes that these historical recruitment decisions implicitly encode patterns that could be learned and operationalized.

The executive board has therefore decided to explore the possibility of introducing an automated support system for the first stage of CV screening. The goal is not to replace HR professionals but to provide them with a structured, consistent, and scalable pre-selection tool capable of assisting in high-volume situations.

To achieve this objective, LuxTalent Advisory Group contacts your IT consulting team. The company seeks a solution capable of automatically processing newly submitted CVs, extracting relevant information, evaluating candidate profiles using a predictive model trained on historical decisions, and producing a recommendation indicating whether a candidate should proceed to the interview phase.

The company emphasizes that this solution must integrate into its operational workflow. Ideally, whenever a CV is received and stored in the system, it should be processed automatically without requiring manual activation. The resulting evaluation should then be made visible to HR staff in a structured and accessible way.

LuxTalent also underlines the importance of reliability and professionalism. The solution must be documented, traceable, and understandable from a systems perspective. The company is aware that algorithmic decision-making can raise broader ethical questions, but for this initial phase, the focus remains on building a functional and operational prototype that demonstrates technical feasibility.

Your team is therefore commissioned to design and implement this automated CV pre-screening system, based on the company's historical recruitment data and integrated into a structured digital workflow.

---

## PART II — Expected Deliverables

The client expects two primary outcomes:

1. A functional automated screening application
2. Complete and structured documentation of the system

The technical implementation details remain at your discretion, provided that the system satisfies the functional expectations described below.

### A. Functional System (Operational Application)

The delivered system must demonstrate:

- Automatic processing of newly submitted CVs
- Transformation of unstructured CV content into structured data
- Application of a predictive screening model trained on historical records
- Generation of a binary recommendation ("Invite" / "Reject")
- Storage and logging of evaluation results
- A graphical interface allowing HR staff to:
  - View daily applicants
  - Access candidate summaries
  - See screening outcomes
  - Identify evaluation timestamps

Automation of the workflow must be clearly implemented (e.g., through a workflow automation tool such as n8n or equivalent).

The system must operate end-to-end in demonstrable conditions.

### B. Documentation (Core Component)

The documentation must formalize the analysis, architecture, and reasoning behind the system.

It is expected to include, where relevant:

- Global system architecture representation
- Description of data flows
- Formal process modeling (e.g., use cases, BPMN, flow diagrams, sequence diagrams, or equivalent)
- Data schema description
- Feature definitions and preprocessing logic
- Modeling rationale and evaluation methodology
- Description of automation logic
- Explanation of system integration between components

The form and tools used for documentation are at your discretion. However, the documentation must reflect structured system thinking and professional analysis practices.

### C. Scope of Freedom

You retain freedom regarding:

- Modeling techniques
- Validation strategies
- Programming languages and frameworks
- Interface technologies
- Internal project organization

However, the final deliverable must demonstrate:

- Coherent system architecture
- Controlled data flow
- Reproducible modeling process
- Functional integration of all components
- Professional documentation standards

---

## Evaluation Basis for Work Package 1

Assessment will focus on:

- Operational completeness of the application
- Structural coherence of the system
- Quality and clarity of documentation
- Consistency between diagrams, code, and implementation
- Professional presentation of deliverables

> Fairness analysis, bias detection, and transparency mechanisms will be addressed in Work Package 2.
