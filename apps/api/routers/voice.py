# WHY: TR-VOX-08, FR-VOX-01, D7, D8 — Voice Endpoints for Turns, Confirmations, and Repairs
"""FastAPI endpoints for Voice Sheet VOX-1 & VOX-2 dialogues."""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.database import get_db
from apps.api.services.orchestrator import VoiceOrchestrator


router = APIRouter(prefix="/api/v1/voice", tags=["voice"])


class VoiceTurnRequest(BaseModel):
    """Payload for text or scripted turn invocation."""
    session_token: Optional[str] = None
    phone: str = "9876500021"
    role: str = "fisher"
    transcript: Optional[str] = None
    noise: bool = False


class VoiceConfirmRequest(BaseModel):
    """Explicit confirmation payload for pending write actions."""
    session_token: str
    confirmed: bool
    phone: str = "9876500021"


class VoiceRepairRequest(BaseModel):
    """Selection from repair options when ambiguous."""
    session_token: str
    selected_option: str
    phone: str = "9876500021"


@router.post("/turn")
async def process_voice_turn(
    session_token: Optional[str] = Form(None),
    phone: str = Form("9876500021"),
    role: str = Form("fisher"),
    transcript: Optional[str] = Form(None),
    audio_file: Optional[UploadFile] = File(None),
    noise: bool = Form(False),
    db: AsyncSession = Depends(get_db),
):
    """Main voice turn: speech/text in -> NLU + action + timings + audio out."""
    token = session_token or str(uuid.uuid4())
    audio_bytes = None
    if audio_file:
        audio_bytes = await audio_file.read()

    result = await VoiceOrchestrator.process_turn(
        session_token=token,
        user_phone=phone,
        role=role,
        audio_bytes=audio_bytes,
        transcript_override=transcript,
        noise=noise,
        db=db,
    )
    result["session_token"] = token
    return result


@router.post("/confirm")
async def confirm_voice_action(
    req: VoiceConfirmRequest,
    db: AsyncSession = Depends(get_db),
):
    """Confirm or discard a pending write action (D8)."""
    transcript_sim = "ಹೌದು" if req.confirmed else "ಇಲ್ಲ"
    result = await VoiceOrchestrator.process_turn(
        session_token=req.session_token,
        user_phone=req.phone,
        transcript_override=transcript_sim,
        db=db,
    )
    return result


@router.post("/repair")
async def repair_voice_disambiguation(
    req: VoiceRepairRequest,
    db: AsyncSession = Depends(get_db),
):
    """Select the exact intended fish or option after repair prompt."""
    result = await VoiceOrchestrator.process_turn(
        session_token=req.session_token,
        user_phone=req.phone,
        transcript_override=req.selected_option,
        db=db,
    )
    return result
