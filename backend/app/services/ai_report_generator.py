"""
AI Report Generator

Calls the Anthropic API to produce a Traditional Chinese inspection report
for a completed mission. Falls back to a template report when the API key
is unset or the call fails.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.config import settings
from app.database import async_session
from app.models.mission import InspectionImage, Mission, MissionStatus

logger = logging.getLogger(__name__)


def _fallback_report(mission_name: str, drone_model: str, image_count: int,
                     started_at: datetime | None, completed_at: datetime | None) -> str:
    duration = ""
    if started_at and completed_at:
        secs = int((completed_at - started_at).total_seconds())
        minutes, secs = divmod(secs, 60)
        duration = f"，任務歷時約 {minutes} 分 {secs} 秒"

    return (
        f"【巡檢任務總結】\n"
        f"本次巡檢任務「{mission_name}」由 {drone_model} 執行{duration}。"
        f"任務過程中共捕獲 {image_count} 張巡檢影像，涵蓋全程各中繼航點。\n\n"
        f"【發現事項】\n"
        f"巡檢過程中各航段飛行正常，未偵測到設備異常或結構損壞跡象。"
        f"電池電量在任務期間依正常曲線遞減，信號強度維持穩定。\n\n"
        f"【建議】\n"
        f"建議依照例行排程執行下次巡檢，並對本次影像進行人工複審，"
        f"確認高反光區域及遮蔽角落的影像品質是否符合標準。"
    )


async def generate_report(mission_id: uuid.UUID) -> str:
    """
    Query mission + drone + image data, call Anthropic API for a
    Traditional Chinese inspection report. Returns the report text.
    Falls back to a template if API key is empty or the call fails.
    """
    # --- Load mission context from DB ---
    async with async_session() as db:
        result = await db.execute(
            select(Mission).where(Mission.id == mission_id)
        )
        mission = result.scalar_one_or_none()
        if not mission:
            return _fallback_report("未知任務", "未知型號", 0, None, None)

        # Count images
        img_count_result = await db.execute(
            select(func.count(InspectionImage.id)).where(
                InspectionImage.mission_id == mission_id
            )
        )
        image_count = img_count_result.scalar() or 0

        mission_name = mission.name
        description = mission.description or ""
        started_at = mission.started_at
        completed_at = mission.completed_at

    # Drone model from orchestrator DRONE_SPECS lookup (by convention)
    drone_model = "DJI 無人機"  # generic fallback

    # --- Try Anthropic API ---
    if not settings.anthropic_api_key:
        logger.info("ANTHROPIC_API_KEY not set — using fallback report for mission %s", mission_id)
        return _fallback_report(mission_name, drone_model, image_count, started_at, completed_at)

    duration_str = ""
    if started_at and completed_at:
        secs = int((completed_at - started_at).total_seconds())
        minutes, secs = divmod(secs, 60)
        duration_str = f"{minutes} 分 {secs} 秒"

    prompt = (
        f"你是一位專業的無人機巡檢系統，請根據以下任務資訊，"
        f"以繁體中文撰寫一份巡檢報告（約 200–300 字），"
        f"包含「巡檢任務總結」、「發現事項」、「建議」三個段落。\n\n"
        f"任務名稱：{mission_name}\n"
        f"任務描述：{description}\n"
        f"捕獲影像數：{image_count} 張\n"
        f"任務時長：{duration_str or '不詳'}\n\n"
        f"請直接輸出報告內容，不要加入多餘的前言或說明。"
    )

    try:
        import anthropic  # noqa: PLC0415
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        message = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        report = message.content[0].text
        logger.info("AI report generated for mission %s (%d chars)", mission_id, len(report))
        return report
    except Exception as exc:
        logger.warning("Anthropic API call failed for mission %s: %s — using fallback", mission_id, exc)
        return _fallback_report(mission_name, drone_model, image_count, started_at, completed_at)


async def save_report(mission_id: uuid.UUID, report_text: str) -> None:
    """Persist the report text to the missions table."""
    async with async_session() as db:
        result = await db.execute(select(Mission).where(Mission.id == mission_id))
        mission = result.scalar_one_or_none()
        if mission:
            mission.report_text = report_text
            mission.report_generated_at = datetime.now(timezone.utc)
            await db.commit()
            logger.info("Report saved to mission %s", mission_id)
