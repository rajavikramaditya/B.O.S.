# B.O.S. Architecture Recovery Audit Report

**Sprint:** Architecture Convergence Safety  
**Date:** July 21, 2026  
**Status:** DRAFT (CONTAMINATION LOGGED)  

---

## 1. Executive Summary

According to the B.O.S. Natural Language Rule (`AGENTS.md`):
> *"Business understanding MUST NOT depend on: regex, keyword matching, string comparison, hardcoded intents. Everything else must be interpreted by the Runtime using AI reasoning."*
>
> *"The Runtime must never understand human language. Only the LLM understands language. The Runtime operates only on normalized semantic structures."*

This audit identifies every instance in the current codebase where this boundary is breached.

---

## 2. Contamination Log

### 1. `backend/runtime/context/context_engine.py` (Lines 20-35)
* **Violation Description:** Contains manual Hinglish pronoun definitions (`usko`, `wahi`, `usi`, `usi customer`, `previous customer`, `kal wala`, `last invoice`, `last asset`) and hardcoded string lookup rules:
  ```python
  if "customer" in val or "person" in val ...
  ```
* **Why it violates architecture:** Performs language-specific keyword checks and manual pronoun resolution logic inside the core Runtime.
* **Which layer should own it instead:** `UnderstandingEngine` / `IntentEngine`. The LLM reasoning step should output a fully normalized entities schema containing resolved UUIDs before passing the context request.

### 2. `backend/runtime/intent/intent_classifier.py` (Lines 21-34)
* **Violation Description:** Resolves intent category, priority, and urgency using keyword lists:
  ```python
  elif text_lower in ("haan", "yes", "confirm", "kar do", "approve"):
  ...
  if any(w in text_lower for w in ("urgent", "immediately", "asap", "turant")):
  ```
* **Why it violates architecture:** Uses hardcoded Hinglish/English strings to guess categories and urgency values directly from raw message strings.
* **Which layer should own it instead:** `UnderstandingEngine`. Category and urgency fields should be structured, normalized fields populated by LLM JSON classification prior to runtime routing.

### 3. `backend/runtime/orchestrator/routing_strategy.py` (Lines 25-28)
* **Violation Description:** Triggers workflow routing decisions based on goal text content matches:
  ```python
  if intent.category == IntentCategory.INQUIRY or "know" in intent.goal.lower():
  ...
  if "history" in intent.goal.lower() or intent.actor_role == "customer":
  ```
* **Why it violates architecture:** Routes execution pipelines using manual substring matches of raw user goal strings.
* **Which layer should own it instead:** `UnderstandingEngine`. Intent classification must result in normalized type tags (e.g. `intent.goal_type = GoalType.KNOWLEDGE_QUERY`), not string substrings.

### 4. `backend/adapters/router.py` (Lines 44-75)
* **Violation Description:** Matches capability actions to adapters dynamically using keyword lookup tables:
  ```python
  if "schedule" in action_lower or "meeting" in action_lower:
      adapter = AdapterRegistry.get("calendar")
  ```
* **Why it violates architecture:** Guesses fallback target adapters by parsing action names semantically.
* **Which layer should own it instead:** `CapabilityResolver`. Action-to-adapter bindings should be explicitly declared in capability manifests rather than guessed by string matching in the router.
