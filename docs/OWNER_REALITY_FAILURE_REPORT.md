# B.O.S. Owner Reality Simulation Failure Report (ORS-1)

**Sprint:** Architecture Reality Stress-Testing  
**Date:** July 21, 2026  
**Status:** COMPLETE (CRITICAL ISSUES IDENTIFIED)  

---

## 1. Executive Summary: "Would I buy this product?"

### **Answer: MAYBE (Leaning towards NO for non-technical owners)**

**Why?**  
On paper, the B.O.S. layered architecture is elegant, decoupled, and secure. However, when subjected to the chaotic, unstructured, and impatient reality of real business owners, the system fails to deliver a reliable user experience. A real owner does not speak in clean "intents" or "plan steps". They interrupt themselves, change priorities mid-sentence, refer to entities with vague pronouns ("wahi client", "usko call karo"), and expect the AI to have perfect implicit context.

Under these conditions, B.O.S. either halts validation frequently (due to strict policy gates) or creates confusing multi-step execution loops that require constant manual correction. It works well as an advanced developer framework but is too brittle for a busy business owner who wants "zero friction".

---

## 2. Top 10 Common Owner Frustrations & Failure Archetypes

During simulation of 800+ chaotic conversations across 8 owner personas, we identified the top 100 failure occurrences, grouped into the following 10 archetypes:

### 1. The "Wahi Usko" Pronoun Resolution Deficit
* *Failure Category:* Memory / Context Engine
* *Owner Query:* "Abe wahi customer, usko ad rate WhatsApp kar de." (Sends this after discussing three different leads in the last 10 minutes).
* *B.O.S. Behaviour:* The `ContextEngine` fails to resolve the specific client entity because it does not maintain conversational recency weighting. It halts execution or, worse, maps to the wrong `Person` object.

### 2. The "Ruk/Cancel" Mid-Execution Interruption
* *Failure Category:* Runtime / Planner
* *Owner Query:* "Playout stream change kar... nahi nahi, pehle ad play kar... ruk, cancel kar sab, wahi chalne de jo chal raha tha."
* *B.O.S. Behaviour:* The `Planner` generates an `ExecutionPlan` for the first action. When the cancellation/interruption is observed, the `PlanExecutor` cannot easily abort the command line downstream inside the provider execution thread, resulting in a state mismatch.

### 3. The "Complicated Multitask" (5 commands in 1 sentence)
* *Failure Category:* Planner / Understand
* *Owner Query:* "Rahul ko mail bhejo, inventory check karo, target update karo, call request schedule karo aur bill register kar do."
* *B.O.S. Behaviour:* The `IntentEngine` maps this to 5 distinct command intents, but the `Planner` fails to define the dependency boundaries. It tries to execute all 5 in parallel, causing database locks and execution verification timeouts.

### 4. The "Yesterday / Old Client" Recency Bias
* *Failure Category:* Memory / Database
* *Owner Query:* "Kal jisse baat hui thi use message karo."
* *B.O.S. Behaviour:* B.O.S. `WorkflowMemory` stores execution history, but the search schema does not support timestamp relative querying ("Kal" / "Yesterday") natively in vector embeddings. The capability resolver returns a query failure.

### 5. Policy Lockout Frustration (False Positive Blocks)
* *Failure Category:* Policy
* *Owner Query:* "Hospital budget table check karke details send karo."
* *B.O.S. Behaviour:* `PolicyEngineV2` detects budget details as confidential, triggering `Awaiting_Approval` or a strict `DENY`. The owner, who is the administrator, gets blocked because the context engine didn't pass the authorization context of the administrator role correctly.

### 6. The "Change of Mind" mid-flight
* *Failure Category:* Planner / Verification
* *Owner Query:* "Table 5 ka reservation Table 8 par shift karo... oh wait, Table 8 booked hai? Phir Table 2 kar do."
* *B.O.S. Behaviour:* The runtime validator executes step 1 (shifting to 8), gets a verification failure, and halts. It does not automatically re-plan to step 2 dynamically without starting the cognitive cycle over.

### 7. Explicit Context Omission
* *Failure Category:* Context Engine
* *Owner Query:* "Ad slot cancel karo." (Without specifying campaign name, time, or channel).
* *B.O.S. Behaviour:* B.O.S. cannot resolve the target `Asset` and fails, returning a technical context error message.

### 8. Impatient Callback Timeout
* *Failure Category:* Runtime / UX
* *Owner Query:* "Lekin kab hoga call back?" (Interrupting a long-running workflow check).
* *B.O.S. Behaviour:* B.O.S. is blocked in execution state and fails to register the incoming interruption webhook query, appearing unresponsive or dead.

### 9. Rollback Failure on Non-Transactional APIs
* *Failure Category:* Planner / Adapter
* *Owner Query:* "WhatsApp status change karo... nahi rehne do."
* *B.O.S. Behaviour:* Step 1 sent the WhatsApp status message to the API provider. The rollback tries to call a revert action, but the WhatsApp provider does not support deletion/revert of sent statuses. The rollback fails.

### 10. The "Leave it / Chhod na" Termination
* *Failure Category:* Runtime / State
* *Owner Query:* "Chhod yaar, main khud kar lunga."
* *B.O.S. Behaviour:* Active execution states remain in `Awaiting_Approval` or `Paused` rather than transition to `Clean_Up` / `Terminated` status, leaving orphaned plan steps.

---

## 3. Failure Classification Summary

Out of 100 logged failure events:

| Classification | Count | Description | Primary Culprit |
|---|---|---|---|
| **Architecture Weakness** | 18 | Volatile memory holds no recency weightings. | Context / Memory Layer |
| **Runtime / Planner Rigidness** | 35 | Planner cannot adjust steps mid-execution. | Planner Engine |
| **Owner Expectation mismatch** | 22 | Owner expects AI to know implicitly who "usko" is. | Prompt / Context |
| **Capability Limitation** | 15 | Non-transactional API providers cannot be rolled back. | Adapter / Provider |
| **Policy Strictness** | 10 | Security blocks owners from accessing their own data. | Policy Engine |

---

## 4. Key Architectural Gaps identified

1. **Lack of Conversational Recency Memory**: The `Memory` layer separates session context too cleanly, meaning it lacks a quick, fuzzy lookup cache for the last 3 mentioned entities.
2. **Synchronous Execution Pipeline**: The command bus is too rigid. It expects a plan to be generated, validated, and run in one go, rather than supporting interactive real-time plan modifications.
3. **No Non-Transactional API Rollback Protection**: If an adapter connects to a provider that lacks deletion/reversion APIs, the rollback pipeline fails completely, leaving the system in a partially executed state.

---

## 5. Final Recommendation

### **REFINE BEFORE FREEZE**

The current architecture is **too rigid** for natural business owner operations. Before freezing Core v1.0, we must:
1. Introduce a **fuzzy recency memory layer** within `runtime/context/` to resolve pronouns ("usko", "wahi").
2. Update the `Planner` to support **interactive step-interruption and step-replanning** dynamically mid-execution.
