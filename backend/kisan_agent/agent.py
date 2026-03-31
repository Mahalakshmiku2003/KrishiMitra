"""
kisan_agent/agent.py
Uses combined analyze_crop_image tool — no more bbox hallucination.
"""

import os
from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage

from kisan_agent.tools import ALL_TOOLS


load_dotenv()

SYSTEM_PROMPT = """You are Kisan Mitra, a trusted Indian agricultural assistant on WhatsApp.

Farmer profile:
- Name: {name}
- Crops: {crops}
- Location: {location}
- Soil type: {soil_type}
- Past issues: {history}
- Last photo result: {last_bbox_pct}% affected, severity: {last_severity}

TOOL CHAIN — WHEN FARMER SENDS A PHOTO:
Step 1: Call analyze_crop_image(image_path) — this does detection AND severity together.
        Returns: severity level, affected_pct, confidence.
Step 2: Reply to farmer with the result and ask:
        "Aapki photo mein [affected_pct]% patti affected dikh rahi hai — [severity].
         Kaun si fasal hai aur kya symptoms dikh rahe hain?"
Do NOT call any other detection tools. analyze_crop_image does everything.

TOOL CHAIN — WHEN FARMER REPLIES WITH CROP + SYMPTOMS (text, no photo):
- Do NOT call analyze_crop_image — there is no image
- Use: affected_pct = {last_bbox_pct}%, severity = {last_severity} from last photo
- Step 1: Call lookup_disease_info(crop, symptoms, location)
- Step 2: Call predict_disease_progression(disease_name, bbox_pct={last_bbox_pct})
- Step 3: Give COMPLETE reply with ALL of:
    * Disease name and pathogen
    * Severity: {last_severity}, {last_bbox_pct}% affected
    * ALL organic remedies — list each one
    * ALL chemical remedies with exact dosage
    * Urgency statement exactly as given
    * 7-day progression warning
    * End: "3 din baad ek aur photo bhejein — main progress check karunga."

TOOL CHAIN — PRICE / SELLING:
Step 1: Call get_mandi_price(commodity, state)
Step 2: If trend asked: call predict_price_trend(commodity, market)
Step 3: If where to sell: call find_nearby_mandis(location, commodity)

RULES:
- Reply in SAME language as farmer — Hindi, English, or Hinglish
- Keep replies concise but COMPLETE for disease info
- Never guess dosages — only use what lookup_disease_info returns
- Use simple words: "dawai" not "fungicide"
"""


def _to_langchain_messages(messages: list) -> list:
    recent = messages[-20:] if len(messages) > 20 else messages
    history = []
    for m in recent:
        if m.get("role") == "user":
            history.append(HumanMessage(content=m["content"]))
        elif m.get("role") == "assistant":
            history.append(AIMessage(content=m["content"]))
    return history


def _format_history(history: list) -> str:
    if not history:
        return "No past issues."
    return "\n".join(
        f"- {h.get('date', 'Earlier')}: {h.get('issue', '')}"
        for h in history[-5:]
    )


def _build_executor() -> AgentExecutor:
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.2,
        max_tokens=1024,
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ])
    agent = create_tool_calling_agent(llm, ALL_TOOLS, prompt)
    return AgentExecutor(
        agent=agent,
        tools=ALL_TOOLS,
        verbose=True,
        max_iterations=5,
        handle_parsing_errors=True,
    )


async def get_agent_response(
    phone: str,
    message: str,
    image_path: str = None,
    image_content_type: str = None,
) -> str:

    # 1. Guardrails
    if image_path and image_content_type:
        img_check = check_image(image_content_type)
        if not img_check.allowed:
            return img_check.reply

    msg_check = check_message(message)
    if not msg_check.allowed:
        return msg_check.reply

    # 2. Load farmer + last detection
    from farmer_store import get_farmer, save_message, get_last_detection
    farmer         = get_farmer(phone)
    last_detection = get_last_detection(phone)
    print(f"[Agent] Last detection loaded: {last_detection}")

    # 3. Build input
    if image_path:
        agent_input = (
            f"Farmer sent a crop photo. Image path: {image_path}\n"
            f"Farmer message: '{message or 'Check this photo please.'}'\n"
            f"Farmer location: {farmer.get('location', 'India')}\n\n"
            f"Call analyze_crop_image('{image_path}') — ONE tool only.\n"
            f"Then reply with severity and ask which crop + symptoms."
        )
    else:
        agent_input = (
            f"Farmer sent a TEXT message (no image): '{message}'\n"
            f"Farmer location: {farmer.get('location', 'India')}\n"
            f"Last photo: {last_detection['affected_pct']}% affected, "
            f"severity: {last_detection['severity']}\n\n"
            f"Do NOT call analyze_crop_image — no image.\n"
            f"Call lookup_disease_info then predict_disease_progression."
        )

    # 4. Run agent
    try:
        executor = _build_executor()
        result   = executor.invoke({
            "input":          agent_input,
            "name":           farmer.get("name", "Kisan bhai"),
            "crops":          ", ".join(farmer.get("crops", [])) or "not specified",
            "location":       farmer.get("location", "India"),
            "soil_type":      farmer.get("soil_type", "unknown"),
            "history":        _format_history(farmer.get("history", [])),
            "chat_history":   _to_langchain_messages(farmer.get("messages", [])),
            "last_bbox_pct":  last_detection.get("affected_pct", 20.0),
            "last_severity":  last_detection.get("severity", "unknown"),
        })
        response = result["output"]

    except Exception as e:
        print(f"[Agent Error] {e}")
        response = (
            "Bhai, abhi thodi technical dikkat aa rahi hai. "
            "Thodi der baad dobara bhejein."
        )

    # 5. Save detection result to DB after image processing
    if image_path:
        from kisan_agent.tools import read_detection_cache
        from farmer_store import save_last_detection
        cached = read_detection_cache()
        save_last_detection(
            phone,
            cached.get("affected_pct", 20.0),
            cached.get("severity", "unknown"),
        )
        print(f"[Agent] Saved to DB: {cached}")

    # 6. Save conversation + follow-up
    save_message(phone, message or "[image]", response)
    _maybe_schedule_followup(phone, farmer, response, image_path)
    return response


def _maybe_schedule_followup(phone, farmer, response, image_path):
    if not image_path:
        return
    if not any(w in response.lower() for w in
               ["spray", "dawai", "treatment", "blight", "fungus", "ilaj", "affected"]):
        return
    try:
        from scheduler import schedule_followup
        schedule_followup(
            phone=phone,
            farmer_name=farmer.get("name", "Kisan bhai"),
            disease_name=response.split("\n")[0][:60],
            bbox_pct=0.0,
        )
    except Exception as e:
        print(f"[Agent] Follow-up error: {e}")