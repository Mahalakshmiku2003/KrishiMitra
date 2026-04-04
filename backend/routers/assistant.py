from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, Form
from pydantic import BaseModel
from typing import Optional
import os
import uuid
from agent.agent import process_message
from agent.diagnose import diagnose_image
from config import UPLOAD_DIR, CLASSIFIER_PATH, DETECTOR_PATH

router = APIRouter(prefix="/assistant", tags=["Assistant"])

class ChatResponse(BaseModel):
    status: str
    reply: str

@router.post("/chat", response_model=ChatResponse)
async def chat_with_assistant(
    message: str = Form(...),
    farmer_id: str = Form("default_farmer"),
    image: Optional[UploadFile] = File(None)
):
    """
    Endpoint for the React Native app to talk to the Kisan Assistant.
    Supports optional image upload for auto-diagnosis.
    """
    try:
        disease_result = None
        
        # 1. Handle image if present
        if image:
            # Create uploads directory if it doesn't exist
            os.makedirs(UPLOAD_DIR, exist_ok=True)
            
            # Save file temporarily
            ext = os.path.splitext(image.filename)[1] or ".jpg"
            temp_filename = f"chat_{uuid.uuid4()}{ext}"
            temp_path = os.path.join(UPLOAD_DIR, temp_filename)
            
            with open(temp_path, "wb") as f:
                f.write(await image.read())
            
            # Run diagnosis using agent logic
            disease_result = diagnose_image(
                temp_path, CLASSIFIER_PATH, DETECTOR_PATH
            )
            
            # We can keep the image for reference or delete it.
            # For now, let's keep it (or we could store it in DB).
            print(f"📸 Image diagnosis for {farmer_id}: {disease_result.get('disease')}")

        # 2. Process message via AI Agent
        reply = await process_message(
            farmer_id=farmer_id,
            message=message,
            disease_result=disease_result
        )
        
        return ChatResponse(status="success", reply=reply)
        
    except Exception as e:
        print(f"❌ Assistant Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

