"""
Scoring algorithms for TimerMind.

This module provides AI-powered scoring functions for task urgency and importance.
Uses Google Gemini to provide intelligent, context-aware assessments.
"""

import json
from datetime import datetime
from typing import Optional

import google.generativeai as genai
from config import GEMINI_API_KEY
from utils.logging import log_event

# Configure Gemini API
genai.configure(api_key=GEMINI_API_KEY)


def compute_urgency_score(deadline_str: Optional[str], label: str = "", description: Optional[str] = None) -> tuple[float, str]:
    """
    Compute urgency using urgency_agent for intelligent assessment.

    Uses the urgency agent to analyze deadline and context.

    Returns:
        tuple[float, str]: (score 0.0-1.0, rationale explaining the score)
    """
    now = datetime.now().isoformat()

    # Prepare context for the agent
    prompt = f"""Analyze the urgency of this task:

Task: {label}
Description: {description or "N/A"}
Deadline: {deadline_str if deadline_str else "No deadline specified"}
Current time: {now}

Please assess the urgency score and provide your rationale."""

    try:
        model = genai.GenerativeModel('gemini-2.0-flash-exp')

        # Enhanced prompt with buffer ratio logic and few-shot examples
        enhanced_prompt = f"""{prompt}

URGENCY SCORING LOGIC:
1. Calculate time remaining until deadline
2. Estimate task effort from description:
   - Trivial (5-15 min): "get mail", "phone call", "quick email"
   - Simple (30-60 min): "appointment", "shopping", "review doc"
   - Moderate (2-4 hrs): "presentation", "report", "meeting prep"
   - Complex (1-3 days): "research", "planning", "major deliverable"
3. Compute buffer ratio = time_remaining / estimated_effort
4. Score based on buffer:
   - < 1.5x buffer: 0.7-1.0 (HIGH - tight deadline)
   - 1.5-3x buffer: 0.4-0.7 (MEDIUM - adequate time)
   - > 3x buffer: 0.1-0.4 (LOW - plenty of time)
   - Overdue/< 1hr: 1.0 (CRITICAL)
   - No deadline: 0.1-0.3 (LOW)

FEW-SHOT EXAMPLES:
Example 1:
Task: "Get the mail from the mailbox"
Deadline: Tomorrow evening (24 hours away)
→ {{"score": 0.2, "rationale": "Trivial task (5 min effort) with large time buffer (24 hours), resulting in very low urgency"}}

Example 2:
Task: "Have dinner ready"
Deadline: 6:30 PM (2.5 hours away)
→ {{"score": 0.75, "rationale": "Moderate task (45-60 min cooking) with limited buffer (2.5 hrs / 1 hr = 2.5x), creating moderate-high urgency"}}

Example 3:
Task: "Write and submit quarterly financial report"
Deadline: Friday at 5 PM (4 days away)
→ {{"score": 0.85, "rationale": "Complex task (2-3 days effort) with tight buffer ratio (4 days / 2.5 days = 1.6x), indicating high urgency"}}

Example 4:
Task: "Complete critical project presentation"
Deadline: 2 hours from now
→ {{"score": 0.95, "rationale": "Moderate-complex task (2-4 hrs effort) with insufficient time buffer (2 hrs / 3 hrs = 0.67x), creating critical urgency"}}

Example 5:
Task: "Schedule dentist appointment"
Deadline: Next month
→ {{"score": 0.15, "rationale": "Simple task (15 min effort) with very large time buffer (30 days), resulting in very low urgency"}}

Respond with JSON only:
{{"score": 0.0-1.0, "rationale": "Brief explanation mentioning buffer ratio, time, and effort"}}"""

        result = model.generate_content(enhanced_prompt)
        response_text = result.text.strip()

        # Extract JSON from markdown if present
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        data = json.loads(response_text)
        score = max(0.0, min(1.0, float(data["score"])))
        rationale = data["rationale"]

        return score, rationale

    except Exception as e:
        log_event("urgency_scoring_error", {"error": str(e), "deadline": deadline_str})
        # Fallback to simple logic if scoring fails
        if not deadline_str:
            return 0.3, "No deadline provided"
        return 0.5, f"Error in urgency assessment: {str(e)}"


def compute_importance_score(category: str, label: str, description: Optional[str] = None) -> tuple[float, str]:
    """
    Compute importance using importance_agent for intelligent assessment.

    Uses the importance agent to analyze task context and category.

    Returns:
        tuple[float, str]: (score 0.0-1.0, rationale explaining the score)
    """
    # Prepare context for the agent
    prompt = f"""Analyze the importance of this task:

Task: {label}
Description: {description or "N/A"}
Category: {category}

Please assess the importance score and provide your rationale."""

    try:
        model = genai.GenerativeModel('gemini-2.0-flash-exp')

        # Enhanced prompt with importance criteria and few-shot examples
        enhanced_prompt = f"""{prompt}

IMPORTANCE SCORING LOGIC:
Analyze task importance based on:
1. Keywords indicating high importance:
   - "critical", "urgent", "important", "asap", "emergency"
   - "vital", "essential", "crucial", "mandatory"
2. Keywords indicating low importance:
   - "maybe", "optional", "nice to have", "someday"
   - "if time", "low priority", "when possible"
3. Context clues:
   - Health matters: usually high importance
   - Financial deadlines: high importance
   - Work deliverables: moderate-high importance
   - Routine personal tasks: moderate importance
   - Optional activities: low importance
4. Category: {category}

Importance scoring:
- 0.9-1.0: Critical (health emergencies, critical work deliverables)
- 0.7-0.9: High importance (important meetings, significant work)
- 0.5-0.7: Moderate importance (routine work, regular personal tasks)
- 0.3-0.5: Low importance (optional tasks, low priority items)
- 0.0-0.3: Trivial (nice-to-haves, very optional)

FEW-SHOT EXAMPLES:
Example 1:
Task: "Get the mail from the mailbox"
Category: personal
→ {{"score": 0.3, "rationale": "Routine personal task with no critical consequences if delayed, indicating low importance"}}

Example 2:
Task: "Have dinner ready"
Category: personal
→ {{"score": 0.5, "rationale": "Daily necessity task with moderate importance for health and routine maintenance"}}

Example 3:
Task: "Write and submit quarterly financial report"
Category: work
→ {{"score": 0.85, "rationale": "Critical work deliverable with significant business impact and mandatory deadline"}}

Example 4:
Task: "Complete critical project presentation"
Category: work
→ {{"score": 0.9, "rationale": "Explicitly marked as critical work task with high-stakes presentation implications"}}

Example 5:
Task: "Schedule dentist appointment"
Category: health
→ {{"score": 0.7, "rationale": "Health-related task with preventive care importance, though not emergency level"}}

Example 6:
Task: "Review optional training materials"
Category: work
→ {{"score": 0.35, "rationale": "Optional professional development with low immediate importance"}}

Respond with JSON only:
{{"score": 0.0-1.0, "rationale": "Brief explanation of why this task has this importance level"}}"""

        result = model.generate_content(enhanced_prompt)
        response_text = result.text.strip()

        # Extract JSON from markdown if present
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        data = json.loads(response_text)
        score = max(0.0, min(1.0, float(data["score"])))
        rationale = data["rationale"]

        return score, rationale

    except Exception as e:
        log_event("importance_scoring_error", {"error": str(e), "category": category})
        # Fallback to simple default
        return 0.5, f"Error in importance assessment: {str(e)}"
