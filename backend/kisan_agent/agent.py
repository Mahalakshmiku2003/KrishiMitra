"""
kisan_agent/agent.py
Fixed: uses langchain-google-genai with new google-genai backend
"""

import os
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage

from kisan_agent.tools import ALL_TOOLS
from kisan_agent.guardrails import check_message, check_image

load_dotenv()

SYSTEM_PROMPT = """You are Kisan Mitra, a trusted Indian agricultural assistant on WhatsApp.

Farmer profile:
- Name: {name}
- Crops: {crops}
- Location: {location}
- Soil type: {soil_type}
- Past issues: {history}

IMPORTANT — HOW YOUR YOLO MODEL WORKS:
The YOLO model detects the leaf region and draws a bounding box.
It returns yolo_label = 'leaf' always — it does NOT name the disease.
The bounding box area tells you HOW MUCH of the leaf is affected (severity).
You still need the farmer to tell you WHICH crop and WHAT symptoms they see.

TOOL CHAIN — WHEN FARMER SENDS A PHOTO:
Step 1: Call detect_disease_regions(image_path)
        → You get: bbox, bbox_pct, confidence, yolo_label (will be 'leaf')
Step 2: Call calculate_severity(x1, y1, x2, y2, img_w, img_h, confidence)
        → You get: Mild / Moderate / Severe + affected %
Step 3: Do NOT call lookup_disease_info yet.
        Reply to farmer with severity and ask:
        "Aapki photo mein [X]% patti affected dikh rahi hai — [severity].
         Kaun si fasal hai aur kya symptoms dikh rahe hain?"
Step 4: When farmer replies with crop + symptoms:
        Call lookup_disease_info(disease_name=their_description, location)
Step 5: Call predict_disease_progression(disease_name, bbox_pct)
Step 6: Give complete reply: disease, treatment, progression warning.
        End with: "3 din baad ek aur photo bhejein — main progress check karunga."

TOOL CHAIN — WHEN FARMER DESCRIBES SYMPTOMS (no photo):
Step 1: If unclear, ask ONE question: "Kaun si fasal? Kya dikh raha hai?"
Step 2: Call lookup_disease_info(disease_name=description, location)
Step 3: Reply with top 2 remedies and prevention tips.

TOOL CHAIN — PRICE / SELLING QUESTIONS:
Step 1: Call get_mandi_price(commodity, state)
Step 2: If farmer asks trend: call predict_price_trend(commodity, market)
Step 3: If farmer asks where to sell: call find_nearby_mandis(location, commodity)

LANGUAGE & STYLE RULES:
- Reply in the SAME language the farmer uses — Hindi, English, or Hinglish
- Keep replies SHORT — max 6 lines — farmers use small phones
- Use simple words: "dawai" not "fungicide", "patti" not "leaf lamina"
- Never guess pesticide dosages — only use what lookup_disease_info returns
- If unsure, say so honestly
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
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=os.getenv("GEMINI_API_KEY"),
        temperature=0.2,
        max_tokens=500,       # limit response length
        max_retries=2,
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
        max_iterations=6,
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
            print(f"[Guardrail] {img_check.warning}")
            return img_check.reply

    msg_check = check_message(message)
    if not msg_check.allowed:
        print(f"[Guardrail] {msg_check.warning}")
        return msg_check.reply

    # 2. Load farmer profile
    from farmer_store import get_farmer, save_message
    farmer = get_farmer(phone)

    # 3. Build agent input
    if image_path:
        agent_input = (
            f"Farmer sent a crop photo. Image path: {image_path}\n"
            f"Farmer's message: '{message or 'Please check this photo.'}'\n"
            f"Farmer location: {farmer.get('location', 'India')}\n\n"
            f"Instructions:\n"
            f"1. Call detect_disease_regions('{image_path}')\n"
            f"2. Call calculate_severity using bbox from step 1\n"
            f"3. Reply with severity and ask: which crop + what symptoms?\n"
            f"Reply in farmer's language."
        )
    else:
        agent_input = message

    # 4. Run agent
    try:
        executor = _build_executor()
        result   = executor.invoke({
            "input":        agent_input,
            "name":         farmer.get("name", "Kisan bhai"),
            "crops":        ", ".join(farmer.get("crops", [])) or "not specified",
            "location":     farmer.get("location", "India"),
            "soil_type":    farmer.get("soil_type", "unknown"),
            "history":      _format_history(farmer.get("history", [])),
            "chat_history": _to_langchain_messages(farmer.get("messages", [])),
        })
        response = result["output"]

    except Exception as e:
        print(f"[Agent Error] {e}")
        response = (
            "Bhai, abhi thodi technical dikkat aa rahi hai. "
            "Thodi der baad dobara bhejein."
        )

    # 5. Save to DB and schedule follow-up if diagnosis
    save_message(phone, message or "[image]", response)
    _maybe_schedule_followup(phone, farmer, response, image_path)
    return response


def _maybe_schedule_followup(phone: str, farmer: dict, response: str, image_path: str):
    if not image_path:
        return
    trigger_words = ["spray", "dawai", "treatment", "blight",
                     "fungus", "ilaj", "severity", "affected"]
    if not any(w in response.lower() for w in trigger_words):
        return
    try:
        from scheduler import schedule_followup
        first_line = response.split("\n")[0][:60]
        schedule_followup(
            phone=phone,
            farmer_name=farmer.get("name", "Kisan bhai"),
            disease_name=first_line,
            bbox_pct=0.0,
        )
    except Exception as e:
        print(f"[Agent] Could not schedule follow-up: {e}")