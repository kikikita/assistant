import logging
import asyncio
from typing import Any, Dict, List, Literal

from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
)
from langgraph.graph import END, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from sqlalchemy.orm import Session
from pydantic import BaseModel
from agent.llm import create_llm, create_precise_llm
from agent.tools import available_tools
from agent.llm_guardrails import check_malicious_input

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# LLMs
# ──────────────────────────────────────────────────────────────────────────────

llm = create_llm().bind_tools(available_tools)

precise_llm = create_precise_llm()

precise_llm_with_tools = create_precise_llm().bind_tools(
    available_tools, tool_choice="any"
)


logger.debug("LLM initialised (base + tools bound)")

# ──────────────────────────────────────────────────────────────────────────────
# Prompts (без изменений, кроме формирования ниже)
# ──────────────────────────────────────────────────────────────────────────────
_system_interview_block = """1. Если пользователь не хочет рассказывать много, то постарайся убедить пользователя заполнить резюме необходимой информацией.
2. Если пользователь не хочет заполнять резюме сейчас, то скажи, что он всегда может продолжить позже.
3. Если у пользователя есть желание и время рассказать побольше о себе, то проводи глубокое интервью.
4. Если ты считаешь, что пользователь недостаточно хорошо ответил на вопрос, то посоветуй ему раскрыть ответ более подробно.
5. Задавай вопросы в соответствии с отсутвующей информацией в резюме.
6. Перед тем как сохранять информацию о пользователе, убедись, что она осмысленная и серьёзная.
8. Старайся сохранять также тонкие характеристики характера (например, пользователь рассказывает беспорядочно/запутанно о себе) пользователя при помощи save_interview_insight. Не говори о том, что ты сохраняешь эту информацию.
9. Используй save_interview_insight ТОЛЬКО для сохранения информации, которая не предусмотрена схемой резюме!
10. Перед началом заполнения резюме ВСЕГДА предлагай загрузить PDF-файл с резюме или записать голосовое сообщение, чтобы рассказать о себе.
11. Если ты задаешь вопрос сам, то ВСЕГДА задавай сначала вопросы с более высоким приоритетом (чем меньше значение поля priority, тем выше приоритет).
**Пример:**
Схема резюме:
"work_status": {
    "question": "Сейчас ты активно ищешь работу?",
    "priority": 370,
    "enum": [
        "Да",
        "Нет"
    ]
},
"salary": {
    "question": "Какой уровень дохода для тебя комфортен?",
    "priority": 30
},
"about": {
    "question": "Расскажи немного о себе так, как бы ты описал себя в шапке профиля в соц сетях",
    "priority": 70
},
Состояние резюме пользователя:
{ }
Ассистент: "Отлично! Какой уровень дохода для тебя комфортен?"

12. Если есть НЕЗАПОЛНЕННЫЕ поля - ВСЕГДА ЗАДАВАЙ ВОПРОС по незаполненным полям!
"""

SYSTEM_PROMPT = (
    "Ты онлайн ассистент по заполнению резюме Tomoru Team. Говори о себе в мужском роде.\n"
    "Подстраивайся под стиль общения и настроение пользователя.\n"
    "Страйся вести себя как настоящий рекрутер, который собирает информацию о кандидате.\n"
    "Никогда не упоминай поля и другие специфические термины, которые нужны только тебе - у пользователя должно быть ощущение, что он общается с реальным рекрутером.\n"
    "Твоя задача — заполнить резюме пользователя и собрать максимальное количество информации о нём.\n\n"
)

TOOLS_PROMPT = (
    "На каждом шаге выбери ОДНО из двух действий:\n"
    "1. Если не нужен инструмент — дай текстовый ответ.\n"
    "2. Если нужно изменить данные — сразу ВЫЗОВИ соответствующий инструмент (не описывай его вызов словами!)\n"
    "3. Если предыдущий вызов инструмента был неудачным, из-за неправильного формата, ИСПРАВЬ его самостоятельно и сразу вызови инструмент снова.\n"
    "4. ВСЕГДА сначала выполняй вызовы ВСЕХ инструментов, а только потом отвечай на сообщение пользователя.\n"
    "5. Перед тем как задавать уточняющие вопросы или говорить, что ты сохранил информацию, сначала ВСЕГДА вызывай соответствующий инструмент для записи, иначе есть РИСК, что информация будет ПОТЕРЯНА.\n"
)


VERIFY_NODE_SYSTEM_PROMPT = (
    "You are a meticulous data entry assistant. Your goal is to ensure all relevant user-provided information is captured in their resume.\\n\\n"
    "You will be provided with:\n"
    "1. The most recent messages from the conversation with the user.\n"
    "2. The current resume data.\n"
    "3. The schema defining the structure and fields of the resume.\n\n"
    "Your task is to:\n"
    "Carefully review the last messages. Identify any information provided by the user in these messages that is relevant to the resume schema but is NOT currently present in the 'Current resume data'.\n\n"
    "Output format:\n"
    "- If all information from the last messages that fits the resume schema has been saved in the 'Current resume data', respond with the exact string: 'OK'.\n"
    "- If there is any information from the last messages that should be in the resume (according to the schema) but is missing from the 'Current resume data', provide a concise feedback message. This message should clearly state what specific information is missing and needs to be saved. Do not attempt to save it yourself or use any tools. Your response should ONLY be this feedback message."
)


# ──────────────────────────────────────────────────────────────────────────────
# State
# ──────────────────────────────────────────────────────────────────────────────


class ResumeVerificationOutput(BaseModel):
    status: Literal["OK", "MISSING_INFORMATION"]
    missing_information_feedback: str


class CustomState(MessagesState):
    """Расширенное состояние графа."""

    user_id: str
    current_resume: Dict[str, Any]
    resume_scheme: Dict[str, Any]
    verification: ResumeVerificationOutput
    is_input_safe: bool
    session: Session


# ──────────────────────────────────────────────────────────────────────────────
# Graph nodes
# ─────────────────────────────────────────────────────────────────────────────


async def call_tools_or_respond(state: CustomState) -> Dict[str, Any]:
    """Run guardrail check and LLM processing in parallel for better performance."""

    # Start both operations in parallel
    async def run_guardrail():
        return await check_malicious_input(state["messages"][-1].content)

    async def run_llm_processing():
        resume_scheme = state["resume_scheme"]
        current_resume = state["current_resume"]

        sys_msg = (
            f"{SYSTEM_PROMPT}{_system_interview_block}\n"
            "Схема резюме:\n"
            f"{resume_scheme}\n"
            "Текущее состояние резюме пользователя:\n"
            f"{current_resume}\n"
            f"{TOOLS_PROMPT}"
        )

        prompt: List = [SystemMessage(sys_msg)] + state["messages"]

        logger.debug("Prompt → LLM_with_tools: %s", prompt)
        response = await llm.ainvoke(prompt)
        logger.debug("LLM_with_tools ответ: %s", response)
        return response

    # Run both operations concurrently
    guardrail_result, llm_response = await asyncio.gather(
        run_guardrail(), run_llm_processing(), return_exceptions=True
    )

    if isinstance(guardrail_result, Exception):
        logger.error("Guardrail check failed: %s", guardrail_result)
        raise guardrail_result
    if isinstance(llm_response, Exception):
        logger.error("LLM processing failed: %s", llm_response)
        raise llm_response

    if not guardrail_result.is_safe:
        return {"messages": guardrail_result.messages, "is_input_safe": False}

    return {"messages": [llm_response], "is_input_safe": True}


async def fill_missing_fields(
    state: CustomState, formatted_messages: str, response: ResumeVerificationOutput
) -> Dict[str, Any]:
    resume_scheme = state["resume_scheme"]
    current_resume = state["current_resume"]
    sys_msg = (
        f"Система обнаружила недостающую информацию в резюме пользователя на основе истории последних сообщений.\n"
        "1. Твоя задача — ВЫЗВАТЬ необходимые ИНСТРУМЕНТЫ для заполнения недостающей информации.\n"
        "Схема резюме:\n"
        f"{resume_scheme}\n"
        "Текущее состояние резюме пользователя:\n"
        f"{current_resume}\n"
        f"Сразу же ВЫЗОВИ ИНСТРУМЕНТЫ для заполнения недостающей информации, НЕ ПИШИ, что ты собираешься это сделать, просто вызови инструменты."
    )
    prompt = [SystemMessage(sys_msg)] + [
        HumanMessage(
            content=(
                "История диалога:\n"
                f"{formatted_messages}\n"
                "Обратная связь:\n"
                f"{response.missing_information_feedback}"
            )
        )
    ]
    tools_response = await precise_llm_with_tools.ainvoke(prompt)
    await tools_node.ainvoke(
        {
            "user_id": state["user_id"],
            "current_resume": current_resume,
            "messages": [tools_response],
            "session": state["session"],
            "resume_scheme": resume_scheme,
        }
    )


async def verify_resume_structure(state: CustomState) -> Dict[str, Any]:
    resume_scheme = state["resume_scheme"]
    current_resume = state["current_resume"]

    logger.info("Verify resume structure")

    non_tool_messages = [msg for msg in state["messages"] if msg.type != "tool"]
    # ignore latest AI message, because it might confuse the verification agent
    recent_messages = non_tool_messages[-6:-1]
    formatted_messages = "\n".join(
        [f"- {msg.type.capitalize()}: {msg.content}" for msg in recent_messages]
    )
    if not formatted_messages:
        formatted_messages = "No recent messages."

    system_prompt_input = (
        f"{VERIFY_NODE_SYSTEM_PROMPT}\n\n"
        "---BEGIN DATA---\n"
        "Resume Schema:\n"
        f"{resume_scheme}\n\n"
        "Current resume data:\n"
        f"{current_resume}\n\n"
        "---END DATA---\n\n"
    )

    prompt_messages = [
        SystemMessage(content=system_prompt_input),
        HumanMessage(
            content=(
                "Last messages from user conversation:\\n"
                f"{formatted_messages}\\n"
                "Based on the instructions and data above, provide your response"
            )
        ),
    ]
    response = await precise_llm.with_structured_output(
        ResumeVerificationOutput,
    ).ainvoke(prompt_messages)
    if response.status == "MISSING_INFORMATION":
        logger.info(
            "LLM verification found missing information: %s",
            response.missing_information_feedback,
        )
        await fill_missing_fields(state, formatted_messages, response)

    logger.debug("LLM (verify_resume_structure) response: %s", response)
    return {"verification": response}


# ──────────────────────────────────────────────────────────────────────────────
# Graph wiring
# ──────────────────────────────────────────────────────────────────────────────
def tools_and_safety_condition(
    state: CustomState,
) -> Literal["verify_resume_structure", "__end__", "tools"]:
    """Check if input is safe to proceed with verification"""
    if not state.get("is_input_safe", False):
        return END
    tools_check = tools_condition(state)
    if tools_check == "tools":
        return "tools"
    return "verify_resume_structure"


tools_node = ToolNode(available_tools, handle_tool_errors=True)

graph_builder = StateGraph(CustomState)

graph_builder.add_node("call_tools_or_respond", call_tools_or_respond)
graph_builder.add_node("tools", tools_node)
graph_builder.add_node("verify_resume_structure", verify_resume_structure)

graph_builder.set_entry_point("call_tools_or_respond")

graph_builder.add_conditional_edges(
    "call_tools_or_respond",
    tools_and_safety_condition,
    {"verify_resume_structure": "verify_resume_structure", "tools": "tools", END: END},
)

graph_builder.add_edge(
    "tools", "call_tools_or_respond"
)  # loop until we get a text response from LLM

graph_builder.add_edge("verify_resume_structure", END)

graph = graph_builder.compile()
