"""
api/routes/chat.py
-------------------
Follow-up chat endpoints for a completed research session.
The generated report acts as the system context for all assistant replies.
"""
import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, status

from api.schemas import (
    ChatRequest,
    ChatResponse,
    ChatMessageResponse,
    ChatHistoryResponse,
    SuccessResponse,
)
from db.models import MessageRole, SessionStatus
from db.repository import (
    SessionRepository,
    ChatRepository,
    get_session_repo,
    get_chat_repo,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_ai_reply(
    question: str,
    company_name: str,
    report: dict,
    chat_history: list,
) -> tuple[str, int, int]:
    """
    Call Claude with the research report as context and return
    (reply_text, prompt_tokens, completion_tokens).
    """
    import json
    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
    from config.settings import settings

    # Build a compact report context (avoid token bloat)
    report_context = json.dumps(report, indent=2)[:4000]

    system_prompt = f"""You are an expert Research Copilot assistant helping a sales professional
prepare for a meeting with {company_name}.

You have access to a detailed research briefing about this company.
Answer questions based strictly on the report data provided.

CRITICAL INSTRUCTIONS:
1. ONLY answer questions directly related to {company_name}, its products/services, or the research report.
2. If the question is not about {company_name}, its products/services, or the research report, politely decline to answer, stating that you can only answer questions related to {company_name} and its products.
3. Be extremely concise. Use short bullet points or brief sentences where possible. Avoid generic introductions, pleasantries, or wordy explanations.
4. If a fact is not in the report or relevant context, state that clearly — do not fabricate information.

RESEARCH REPORT:
{report_context}
"""

    # Build conversation history (last 6 messages for context window efficiency)
    messages = [SystemMessage(content=system_prompt)]
    for msg in chat_history[-6:]:
        if msg.role == MessageRole.USER:
            messages.append(HumanMessage(content=msg.content))
        else:
            messages.append(AIMessage(content=msg.content))

    # Add the current question
    messages.append(HumanMessage(content=question))

    llm = ChatAnthropic(
        model=settings.anthropic_model,
        anthropic_api_key=settings.anthropic_api_key,
        temperature=0.3,
        max_tokens=1000,
    )

    response = await llm.ainvoke(messages)
    reply = response.content.strip()

    # Extract token usage if available
    prompt_tokens = 0
    completion_tokens = 0
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        prompt_tokens = response.usage_metadata.get("input_tokens", 0)
        completion_tokens = response.usage_metadata.get("output_tokens", 0)

    return reply, prompt_tokens, completion_tokens


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/{id}", response_model=ChatResponse)
async def send_chat_message(
    id: uuid.UUID,
    payload: ChatRequest,
    session_repo: SessionRepository = Depends(get_session_repo),
    chat_repo: ChatRepository = Depends(get_chat_repo),
):
    """
    Send a follow-up question about the research report.
    Requires the session to have a completed report.
    """
    session = await session_repo.get_by_id(id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found with id: {id}",
        )

    if session.status != SessionStatus.COMPLETED or not session.report:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Cannot start chat until the research report has been generated. "
                "Run the workflow first and wait for it to complete."
            ),
        )

    # 1. Save user message
    user_msg = await chat_repo.add_message(
        session_id=id,
        role=MessageRole.USER,
        content=payload.message,
    )

    # 2. Fetch recent chat history for context
    history = await chat_repo.get_history(id)

    # 3. Call Claude with the report as context
    try:
        reply, prompt_tokens, completion_tokens = await _get_ai_reply(
            question=payload.message,
            company_name=session.company_name,
            report=session.report,
            chat_history=history[:-1],  # Exclude the message we just added
        )
    except Exception as exc:
        logger.error(f"Chat AI call failed for session {id}: {exc}", exc_info=True)
        reply = (
            f"I encountered an error generating a response. "
            f"Please check your API configuration and try again."
        )
        prompt_tokens = 0
        completion_tokens = 0

    # 4. Save assistant message with token usage
    assistant_msg = await chat_repo.add_message(
        session_id=id,
        role=MessageRole.ASSISTANT,
        content=reply,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )

    return ChatResponse(
        user_message=ChatMessageResponse.model_validate(user_msg),
        assistant_message=ChatMessageResponse.model_validate(assistant_msg),
    )


@router.get("/{id}", response_model=ChatHistoryResponse)
async def get_chat_history(
    id: uuid.UUID,
    session_repo: SessionRepository = Depends(get_session_repo),
    chat_repo: ChatRepository = Depends(get_chat_repo),
):
    """Retrieve the full chat history for a session."""
    session = await session_repo.get_by_id(id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found with id: {id}",
        )

    messages = await chat_repo.get_history(id)
    return ChatHistoryResponse(
        session_id=id,
        messages=[ChatMessageResponse.model_validate(m) for m in messages],
        total=len(messages),
    )


@router.delete("/{id}", response_model=SuccessResponse)
async def clear_chat_history(
    id: uuid.UUID,
    session_repo: SessionRepository = Depends(get_session_repo),
    chat_repo: ChatRepository = Depends(get_chat_repo),
):
    """Clear all chat messages for a session."""
    session = await session_repo.get_by_id(id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found with id: {id}",
        )

    deleted_count = await chat_repo.clear_history(id)
    return SuccessResponse(
        message=f"Successfully cleared {deleted_count} messages from chat history."
    )
