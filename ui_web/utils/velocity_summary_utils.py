from typing import List, Optional

from ..data.velocity_report_data import VelocityReportData
from ..data.velocity_summary_data import VelocitySummaryData


class VelocitySummaryUtils:

    @staticmethod
    def summarize(velocity_reports_data: List[VelocityReportData], periods: int) -> Optional[VelocitySummaryData]:
        reports = sorted(velocity_reports_data, key=lambda report: report.start_date)[-periods:]
        if not reports:
            return None

        latest = reports[-1]
        previous = reports[-2] if len(reports) > 1 else None
        best = max(reports, key=lambda report: report.velocity)
        return VelocitySummaryData(
            period_count=len(reports),
            average_velocity=sum(report.velocity for report in reports) / len(reports),
            latest_period=VelocitySummaryUtils._period_label(latest),
            latest_velocity=latest.velocity,
            latest_change=latest.velocity - previous.velocity if previous else None,
            total_story_points=sum(report.story_points for report in reports),
            best_period=VelocitySummaryUtils._period_label(best),
            best_velocity=best.velocity,
        )

    @staticmethod
    def _period_label(report: VelocityReportData) -> str:
        return f"{report.start_date.year}-{report.start_date.month:02d}"
