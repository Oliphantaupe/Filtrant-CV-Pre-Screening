# Work Package 2 — Project Specification (Cahier des Charges)
## Fairness Audit, Ethical Reflection and Model Redesign
### Client: LuxTalent Advisory Group S.A.

---

## PART I — Context and Project Situation

### 1. Evolution of the Project Context

Several months after the deployment of the automated CV pre-screening system developed in Work Package 1, LuxTalent Advisory Group S.A. has begun to rely operationally on the tool for high-volume recruitment campaigns.

The system processes incoming CVs automatically, extracts structured information, applies a predictive model trained on historical decisions, and produces recommendations indicating whether candidates should proceed to the interview stage.

At first glance, the system appears to function reliably. It reduces manual workload and standardizes the pre-screening phase. HR consultants appreciate the efficiency gains and the ability to quickly visualize daily applications.

However, during an internal review, concerns begin to emerge.

A member of the HR compliance team observes that certain categories of candidates appear to be invited to interviews at significantly different rates compared to others. These disparities are not immediately obvious in individual cases, but statistical patterns suggest possible imbalances across specific groups.

Although the model was trained on historical recruitment decisions, questions are raised about whether past decisions themselves may have embedded implicit biases. If the algorithm has learned from those historical patterns, it may be reproducing and amplifying structural inequalities.

LuxTalent's executive board decides to initiate an internal audit of the system. They contact your consulting team again and request a thorough evaluation of the model's behavior.

The company explicitly asks:

- Does the system treat comparable candidates equally?
- Are there measurable disparities across specific groups?
- If disparities exist, are they justified by relevant job-related features?
- Can the model be improved to reduce unjustified differences?
- Can decisions be made more transparent and explainable?

In parallel, LuxTalent organizes a conference led by an external expert in algorithmic decision systems, digital ethics, and discrimination law. The purpose of this lecture is to provide a conceptual and regulatory framework to better understand the implications of automated decision-making.

Your team is expected to attend this expert session. The insights from this presentation must guide your audit methodology and redesign strategy.

The company now commissions you to:

1. Audit the fairness of the existing screening model.
2. Identify and measure potential discrimination patterns.
3. Propose and implement corrective strategies.
4. Enhance the system with transparency and explanation mechanisms.
5. Deliver a revised version of the application reflecting these improvements.

This phase does not replace the system developed in Work Package 1. Instead, it critically evaluates and redesigns it.

---

## PART II — Expected Deliverables

The client expects three main outcomes:

1. A structured fairness audit of the existing system
2. A revised and improved screening model
3. An enhanced application integrating transparency mechanisms

Students retain methodological freedom but must address the following elements.

### A. Expert Lecture Integration (Mandatory Component)

Attendance to the expert presentation is required.

Students must:

- Extract key conceptual principles discussed in the lecture.
- Identify relevant ethical, legal, or procedural considerations.
- Integrate these insights into their audit framework.
- Explicitly reference how the lecture influenced their technical choices.

A short reflection document must connect the expert's concepts to the system redesign.

### B. Fairness Audit

The audit must include:

- Identification of potentially sensitive attributes (within the pedagogical simulation).
- Statistical analysis of decision disparities.
- Selection and justification of fairness metrics.
- Clear visualization of observed patterns.
- Identification of features that may act as direct or indirect proxies.

The methodology is flexible, but the reasoning must be structured and justified.

### C. Model Redesign and Mitigation Strategy

Students must implement at least one corrective approach to address identified disparities.

Possible strategies may include:

- Data rebalancing or reweighting
- Feature adjustment
- Threshold modification
- Alternative modeling approaches

Students must:

- Compare original and revised models.
- Present performance metrics before and after mitigation.
- Discuss trade-offs between predictive performance and fairness objectives.

The redesign must remain integrated within the automated pipeline established in Work Package 1.

### D. Explainability and Transparency

The improved system must include mechanisms that:

- Provide interpretable explanations for screening decisions.
- Identify influential features in individual predictions.
- Present results in a form understandable to HR personnel.

The goal is not full legal compliance analysis, but demonstrable transparency.

### E. Updated Application (Version 2)

The revised application must demonstrate:

- Integration of the improved model.
- Display of fairness-related indicators where appropriate.
- Clear distinction between baseline and revised model (if relevant).
- Continued end-to-end automation.
- Maintained logging and traceability.

The system must remain operational.

### F. Documentation

The documentation must include:

- Audit methodology.
- Justification of fairness metrics.
- Redesign rationale.
- Integration of expert lecture insights.
- Updated system diagrams if architecture changes.
- Comparative analysis between Version 1 and Version 2.

Formal modeling tools (BPMN, diagrams, flow representations, etc.) may be used where relevant.

---

## Scope of Freedom

Students retain freedom regarding:

- Choice of fairness metrics.
- Mitigation techniques.
- Explainability tools.
- Analytical frameworks.
- Visualization methods.

However, the final submission must clearly demonstrate:

- Structured critical reasoning.
- Measurable analysis.
- Concrete corrective implementation.
- Conceptual integration of ethical considerations.

---

## Evaluation Basis for Work Package 2

Assessment will focus on:

- Depth and rigor of fairness audit.
- Quality of analytical reasoning.
- Coherence between expert lecture insights and technical redesign.
- Implementation of corrective measures.
- Integration of transparency mechanisms.
- Professional quality of documentation.
- Operational integrity of revised application.

---

## Expected Outcome

At completion of Work Package 2, the system should evolve from:

> "A functional automated screening tool"

to:

> "A critically evaluated, improved, and more transparent decision-support system."
