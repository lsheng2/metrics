from typing import List, Optional, Callable

from ..data.chart_data import ChartData, ChartDatasetData
from ..data.velocity_report_data import VelocityReportData


class VelocityChartConvertor:
    
    def convert_velocity_reports_to_velocity_chart(self, velocity_reports_data: List[VelocityReportData]) -> Optional[ChartData]:
        return self._convert_team_reports_to_chart(
            velocity_reports_data, 
            lambda report: report.velocity
        )
    
    def convert_velocity_reports_to_story_points_chart(self, velocity_reports_data: List[VelocityReportData]) -> Optional[ChartData]:
        return self._convert_team_reports_to_chart(
            velocity_reports_data, 
            lambda report: report.story_points
        )
    
    def convert_dev_velocity_reports_to_velocity_chart(self, velocity_reports_data: List[VelocityReportData]) -> Optional[ChartData]:
        return self._convert_dev_reports_to_chart(
            velocity_reports_data,
            lambda report: report.velocity
        )
    
    def convert_dev_velocity_reports_to_story_points_chart(self, velocity_reports_data: List[VelocityReportData]) -> Optional[ChartData]:
        return self._convert_dev_reports_to_chart(
            velocity_reports_data,
            lambda report: report.story_points
        )
    
    def _convert_team_reports_to_chart(self, velocity_reports_data: List[VelocityReportData], extract_fn: Callable[[VelocityReportData], float]) -> Optional[ChartData]:
        if not velocity_reports_data:
            return None
        
        labels = []
        data_values = []
        
        for report in velocity_reports_data:
            label = f"{report.start_date.year}-{report.start_date.month:02d}"
            labels.append(label)
            data_values.append(extract_fn(report))
        
        dataset = ChartDatasetData(
            label="team",
            data=data_values
        )
        
        return ChartData(labels=labels, datasets=[dataset])
    
    def _convert_dev_reports_to_chart(self, velocity_reports_data: List[VelocityReportData], extract_fn: Callable[[VelocityReportData], float]) -> Optional[ChartData]:
        if not velocity_reports_data:
            return None
        
        labels = set()
        developer_data = {}
        
        for report in velocity_reports_data:
            label = f"{report.start_date.year}-{report.start_date.month:02d}"
            labels.add(label)
            
            developer_name = report.metric_scope_name or report.metric_scope or 'Unknown'
            if developer_name not in developer_data:
                developer_data[developer_name] = {}
            
            developer_data[developer_name][label] = extract_fn(report)
        
        sorted_labels = sorted(list(labels))
        datasets = []
        
        for developer, periods in developer_data.items():
            metrics = [periods.get(label, 0) for label in sorted_labels]
            
            datasets.append(ChartDatasetData(
                label=developer,
                data=metrics
            ))
        
        return ChartData(labels=sorted_labels, datasets=datasets)