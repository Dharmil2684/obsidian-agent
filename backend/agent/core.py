"""
Agent core — Phase 1

The LLM (Hermes-3) owns all intelligence: intent, domain, description cleaning,
multi-task splitting, correction detection, clarification decisions.

This file just:
  1. Calls classify_intent() to get the LLM's structured decision
  2. Routes to the right vault tool based on that decision
  3. Formats a warm response
"""
import random
from typing import Optional

import httpx

from backend.agent.intent import classify_intent
from backend.agent.context import get_context_prompt
from backend.agent.tools.task_tools import add_task, complete_task, clear_tasks
from backend.agent.tools.blocker_tools import create_blocker, resolve_blocker
from backend.agent.tools.carry_tools import carry_tasks_forward
from backend.agent.tools.summary_tools import generate_daily_summary, generate_weekly_summary
from backend.agent.tools.status_tools import get_today_status
from backend import config

# ---------------------------------------------------------------------------
# Personality — warm, varied acknowledgments
# ---------------------------------------------------------------------------

_ACK_TASK    = ["Got it!", "Added!", "On it!", "Noted!", "Sure thing!"]
_ACK_DONE    = ["Nice work!", "Great, marked as done!", "Awesome, checked off!", "Crushed it!"]
_ACK_BLOCKER = ["Logged!", "Noted, that's a pain.", "Got it, blocker logged!"]
_ACK_RESOLVE = ["Nice, glad that's sorted!", "Great fix!", "Resolved and archived!"]
_ACK_CLEAR   = ["Done!", "All clear!", "Wiped."]

def _ack(pool: list) -> str:
    return random.choice(pool)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

async def process_message(message: str) -> dict:
    """
    Full agent pipeline:
      classify (LLM) → check correction/clarification → route to tool → respond
    """
    clf = await classify_intent(message)

    intent                = clf["intent"]
    domain                = clf["domain"]
    description           = clf.get("description") or message
    tasks                 = clf.get("tasks", [])
    is_correction         = clf.get("is_correction", False)
    needs_clarification   = clf.get("needs_clarification", False)
    clarification_question = clf.get("clarification_question")

    # 1. Correction — LLM detected user is fixing a previous agent mistake
    if is_correction:
        return {
            "response": (
                "You're right, sorry about that! "
                "Could you list the tasks with numbers so I get them all?\n\n"
                "e.g. *\"1. Upgrade NuGet packages  2. Update drivers lat-long action name\"*"
            ),
            "intent": "chitchat",
            "domain": "unknown",
            "action": None,
            "success": True,
            "needs_clarification": True,
        }

    # 2. Clarification — LLM decided it needs more info before acting
    if needs_clarification:
        question = clarification_question or (
            "Which domain is this for?\n\n"
            "🖥️ **Backend** · 🌐 **Frontend** · 📊 **Data Science**"
        )
        return {
            "response": question,
            "intent": intent,
            "domain": "unknown",
            "action": None,
            "success": True,
            "needs_clarification": True,
        }

    # 3. Multi-task — LLM extracted 2+ tasks from the message
    if len(tasks) >= 2 and intent == "create_task":
        return await _handle_multi_task(tasks, domain)

    # 4. Single task — prefer LLM's cleaned description from tasks[0] if available
    if len(tasks) == 1 and intent == "create_task":
        description = tasks[0].get("description", description)
        domain      = tasks[0].get("domain", domain)

    # 5. Route to vault tool
    tool_result: Optional[dict] = None

    if intent == "create_task":
        tool_result = add_task(description, domain if domain != "unknown" else "backend")

    elif intent == "create_blocker":
        tool_result = create_blocker(description, domain if domain != "unknown" else "backend")

    elif intent == "resolve_blocker":
        tool_result = resolve_blocker(description)

    elif intent == "complete_task":
        tool_result = complete_task(description)

    elif intent == "carry_forward":
        tool_result = carry_tasks_forward()

    elif intent == "clear_tasks":
        tool_result = clear_tasks(domain if domain != "unknown" else "all")

    elif intent == "get_status":
        tool_result = get_today_status()

    elif intent == "generate_summary":
        tool_result = generate_daily_summary()

    elif intent == "generate_weekly":
        tool_result = generate_weekly_summary()

    elif intent == "chitchat":
        return {
            "response": await _llm_reply(message),
            "intent": "chitchat",
            "domain": "unknown",
            "action": None,
            "success": True,
            "needs_clarification": False,
        }

    # 6. Build warm response
    if tool_result:
        prefix = ""
        if tool_result.get("success"):
            if intent == "create_task":       prefix = f"{_ack(_ACK_TASK)} "
            elif intent == "complete_task":   prefix = f"{_ack(_ACK_DONE)} "
            elif intent == "create_blocker":  prefix = f"{_ack(_ACK_BLOCKER)} "
            elif intent == "resolve_blocker": prefix = f"{_ack(_ACK_RESOLVE)} "
            elif intent == "clear_tasks":     prefix = f"{_ack(_ACK_CLEAR)} "

        return {
            "response": prefix + tool_result.get("message", "Done."),
            "intent":   intent,
            "domain":   domain,
            "action":   tool_result.get("action"),
            "success":  tool_result.get("success", True),
            "needs_clarification": False,
        }

    return {
        "response": "Hmm, not sure what to do with that. Try `/status` to see today's tasks.",
        "intent":   intent,
        "domain":   domain,
        "action":   None,
        "success":  False,
        "needs_clarification": False,
    }


async def _handle_multi_task(tasks: list, fallback_domain: str) -> dict:
    """Create multiple tasks returned by the LLM in one shot."""
    label_map = {"backend": "🖥️ BE", "frontend": "🌐 FE", "data_science": "📊 DS"}
    created, failed = [], []

    for t in tasks:
        desc   = t.get("description", "")
        domain = t.get("domain", fallback_domain)
        if domain == "unknown":
            domain = fallback_domain if fallback_domain != "unknown" else "backend"
        if not desc:
            continue
        result = add_task(desc, domain)
        if result["success"]:
            created.append((desc, domain))
        else:
            failed.append(desc)

    if not created:
        return {
            "response": "Hmm, I couldn't add any of those tasks. Try `/task:be [description]` for each.",
            "intent": "create_task", "domain": fallback_domain,
            "action": None, "success": False, "needs_clarification": False,
        }

    task_list = "\n".join(f"- [{label_map.get(d, d)}] **{desc}**" for desc, d in created)
    response  = f"{_ack(_ACK_TASK)} Added {len(created)} task{'s' if len(created) > 1 else ''}:\n\n{task_list}"
    if failed:
        response += f"\n\n⚠️ Couldn't add: {', '.join(failed)}"

    return {
        "response": response,
        "intent": "create_task",
        "domain": fallback_domain,
        "action": f"✓ {len(created)} tasks written to today's daily note",
        "success": True,
        "needs_clarification": False,
    }


async def _llm_reply(message: str) -> str:
    """Free-form chitchat reply via local Ollama."""
    context = get_context_prompt()
    payload = {
        "model": config.LOCAL_MODEL,
        "messages": [
            {"role": "system", "content": context},
            {"role": "user",   "content": message},
        ],
        "stream": False,
        "options": {"temperature": 0.7, "num_predict": 300},
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.post(f"{config.OLLAMA_BASE_URL}/api/chat", json=payload)
            resp.raise_for_status()
            return resp.json()["message"]["content"]
        except Exception:
            return (
                "I'm here to help manage your tasks and blockers. "
                "Try *\"I'm working on X\"*, `/status`, or `/task [description]`."
            )

