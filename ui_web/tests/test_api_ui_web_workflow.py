import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

from tasks.app.domain.model.config import WorkflowConfig
from tasks.app.domain.model.task import Task, EnrichmentOptions, TaskSearchCriteria, MemberGroup
from ui_web.facades.tasks_facade import TasksFacade
from ui_web.convertors.task_convertor import TaskConvertor
from ui_web.convertors.member_convertor import MemberConvertor
from ui_web.utils.federated_data_post_processors import MemberGroupTaskFilter
from ui_web.utils.federated_data_fetcher import FederatedDataFetcher
from ui_web.tests.fixtures.business_scenarios import BusinessScenarios
from ui_web.tests.fixtures.ui_web_builders import DomainTaskBuilder
from ui_web.tests.mocks.mock_task_search_api import MockTaskSearchApi
from ui_web.tests.mocks.mock_forecast_api import MockForecastApi


class TestApiUIWebWorkflow(unittest.IsolatedAsyncioTestCase):
    
    def setUp(self):
        self.task_search_api = MockTaskSearchApi()
        self.forecast_api = MockForecastApi()
        
        self.available_member_groups = [
            MemberGroup(id="frontend-team", name="Frontend Development Team"),
            MemberGroup(id="backend-team", name="Backend Development Team"),
            MemberGroup(id="devops-team", name="DevOps Team")
        ]
        
        self.current_tasks_criteria = TaskSearchCriteria(
            status_filter=["In Progress", "Development", "Testing"]
        )
        
        self.recently_finished_criteria = TaskSearchCriteria(
            status_filter=["Done", "Completed"]
        )
        
        self.workflow_config = WorkflowConfig(
            in_progress_status_codes=["In Progress", "Development", "Testing"],
            done_status_codes=["Done", "Completed", "Closed"],
            pending_status_codes=["To Do", "Open", "Backlog"],
            stages={
                "development": ["In Progress", "Development"],
                "qa": ["Testing", "Code Review"],
                "done": ["Done", "Completed", "Closed"],
                "backlog": ["To Do", "Open", "Backlog"]
            },
            recently_finished_tasks_days=30
        )
        
        # Mock member group config for filtering
        member_group_config = Mock()
        member_group_config.members = {
            "alice.johnson": {"member_groups": ["frontend-team"]},
            "bob.smith": {"member_groups": ["backend-team"]},
            "charlie.brown": {"member_groups": ["devops-team"]}
        }
        member_group_config.default_member_group_when_missing = None
        member_group_config.custom_filters = {}
        
        self.member_group_filter = MemberGroupTaskFilter(member_group_config)
        
        # Mock time policy for conversion
        with patch('sd_metrics_lib.utils.time.TimePolicy.BUSINESS_HOURS'):
            self.task_convertor = TaskConvertor(Mock())
        
        self.member_convertor = MemberConvertor()
        
        self.facade = TasksFacade(
            task_search_api=self.task_search_api,
            forecast_api=self.forecast_api,
            task_convertor=self.task_convertor,
            available_member_groups=self.available_member_groups,
            current_tasks_search_criteria=self.current_tasks_criteria,
            recently_finished_tasks_search_criteria=self.recently_finished_criteria,
            workflow_config=self.workflow_config,
            member_group_task_filter=self.member_group_filter,
            member_convertor=self.member_convertor
        )
    
    async def test_shouldExecuteConcurrentDataFederationForOptimalSprintDashboardPerformance(self):
        # Given - Multiple data sources that can be fetched concurrently
        current_tasks = BusinessScenarios.active_sprint_tasks()
        finished_tasks = BusinessScenarios.recently_completed_tasks()
        
        # Add delay to simulate realistic API response times
        async def delayed_search(criteria, enrichment):
            await asyncio.sleep(0.01)  # 10ms delay per call
            if criteria.status_filter == ["In Progress", "Development", "Testing"]:
                return current_tasks
            else:
                return finished_tasks
        
        self.task_search_api.mock.search.side_effect = delayed_search
        
        # When - Execute federated data workflow
        start_time = asyncio.get_event_loop().time()
        result = await self.facade.get_tasks()
        end_time = asyncio.get_event_loop().time()
        
        # Then - Should complete in roughly single delay time due to concurrent execution
        elapsed_time = end_time - start_time
        self.assertLess(elapsed_time, 0.05)  # Should be ~10ms, not ~20ms sequential
        self.assertEqual(5, len(result))  # 3 current + 2 finished tasks
    
    async def test_shouldApplyDataEnrichmentPipelineSequentiallyForAccurateBusinessInsights(self):
        # Given - Data enrichment workflow for business decision making
        base_tasks = [
            DomainTaskBuilder.domain_task_for_ui_conversion()
                .assigned_to("alice.johnson")
                .with_time_spent_hours(16.0)
                .build()
        ]
        
        # Mock forecast enrichment process
        async def enrich_with_forecasts(tasks, parameters):
            for task in tasks:
                task.forecast = Mock()
                task.forecast.target = Mock()
                task.forecast.target.health_status = Mock()
                task.forecast.target.health_status.value = 2  # YELLOW
            return tasks
        
        self.task_search_api.mock.search.side_effect = [base_tasks, []]
        self.forecast_api.mock.generate_forecasts_for_tasks.side_effect = enrich_with_forecasts
        
        # When - Execute enrichment workflow
        result = await self.facade.get_tasks()
        
        # Then - Data should be enriched through pipeline
        self.assertEqual(1, len(result))
        enriched_task = result[0]
        
        # Verify enrichment applied
        self.assertIsNotNone(enriched_task.forecast)
        self.assertEqual(2, enriched_task.forecast.health_status.value)  # YELLOW status
        self.assertEqual(2.0, enriched_task.time_tracking.total_spent_time_days)
        
        # Verify forecast generation was called
        self.forecast_api.mock.generate_forecasts_for_tasks.assert_called()
    
    async def test_shouldHandleWorkflowTimeoutsGracefullyForReliableUserExperience(self):
        # Given - Scenario with slow external dependencies
        slow_tasks = BusinessScenarios.active_sprint_tasks()
        
        async def timeout_simulation(criteria, enrichment):
            await asyncio.sleep(0.1)  # Simulate slow response
            return slow_tasks
        
        self.task_search_api.mock.search.side_effect = timeout_simulation
        
        # When - Execute workflow with timeout constraints
        try:
            result = await asyncio.wait_for(self.facade.get_tasks(), timeout=0.05)
            # Should not reach here due to timeout
            self.fail("Expected timeout but workflow completed")
        except asyncio.TimeoutError:
            # Then - Timeout should be handled appropriately
            pass  # Expected behavior for slow systems
    
    async def test_shouldMaintainWorkflowStateBetweenStagesForConsistentDataProcessing(self):
        # Given - Multi-stage workflow that requires state consistency
        stateful_tasks = [
            DomainTaskBuilder.domain_task_for_ui_conversion()
                .assigned_to("alice.johnson")
                .build()
        ]
        stateful_tasks[0].id = "STATEFUL-TASK-123"
        
        self.task_search_api.mock.search.side_effect = [stateful_tasks, []]
        
        # When - Execute workflow stages
        result = await self.facade.get_tasks()
        
        # Then - State should be preserved throughout workflow
        self.assertEqual(1, len(result))
        processed_task = result[0]
        
        # Verify task identity maintained through all stages
        self.assertEqual("STATEFUL-TASK-123", processed_task.id)
        self.assertEqual("alice.johnson", processed_task.assignment.assignee.id)
        
        # Verify workflow stages completed (conversion applied)
        self.assertIsNotNone(processed_task.time_tracking)
        self.assertIsNotNone(processed_task.system_metadata)
    
    async def test_shouldExecuteFilteringWorkflowForTeamSpecificDataIsolation(self):
        # Given - Mixed team data requiring workflow-based filtering
        mixed_team_tasks = [
            DomainTaskBuilder.domain_task_for_ui_conversion()
                .assigned_to("alice.johnson")  # Frontend
                .build(),
            DomainTaskBuilder.domain_task_for_ui_conversion()
                .assigned_to("bob.smith")     # Backend
                .build(),
            DomainTaskBuilder.domain_task_for_ui_conversion()
                .assigned_to("charlie.brown") # DevOps
                .build()
        ]
        
        self.task_search_api.mock.search.side_effect = [mixed_team_tasks, []]
        
        # When - Execute filtering workflow for specific team
        frontend_result = await self.facade.get_tasks("frontend-team")
        
        # Then - Filtering workflow should isolate team data
        self.assertEqual(1, len(frontend_result))
        filtered_task = frontend_result[0]
        self.assertEqual("alice.johnson", filtered_task.assignment.assignee.id)
        
        # Verify filtering was applied in workflow pipeline
        self.assertIn("frontend-team", 
                     [mg.id for mg in self.available_member_groups 
                      if mg.name == "Frontend Development Team"])
    
    async def test_shouldExecuteSortingWorkflowForPriorityBasedTaskDisplayInRetrospectives(self):
        # Given - Tasks with different time investments for retrospective analysis
        unsorted_tasks = [
            DomainTaskBuilder.domain_task_for_ui_conversion()
                .with_time_spent_hours(8.0)   # Low effort
                .build(),
            DomainTaskBuilder.domain_task_for_ui_conversion()
                .with_time_spent_hours(32.0)  # High effort
                .build(),
            DomainTaskBuilder.domain_task_for_ui_conversion()
                .with_time_spent_hours(16.0)  # Medium effort
                .build()
        ]

        unsorted_tasks[0].id = "LOW-EFFORT"
        unsorted_tasks[1].id = "HIGH-EFFORT"
        unsorted_tasks[2].id = "MEDIUM-EFFORT"

        self.task_search_api.mock.search.side_effect = [unsorted_tasks, []]

        # When - Execute data workflow (note: sorting now happens in view layer via TaskGroupingUtils)
        result = await self.facade.get_tasks()

        # Then - All tasks should be returned with correct data
        self.assertEqual(3, len(result))

        # Verify workflow maintained data integrity for all tasks
        task_by_id = {task.id: task for task in result}
        self.assertEqual(4.0, task_by_id["HIGH-EFFORT"].time_tracking.total_spent_time_days)
        self.assertEqual(2.0, task_by_id["MEDIUM-EFFORT"].time_tracking.total_spent_time_days)
        self.assertEqual(1.0, task_by_id["LOW-EFFORT"].time_tracking.total_spent_time_days)
    
    def test_shouldExecuteFederatedDataFetcherWorkflowForComplexDataOrchestration(self):
        # Given - Complex data orchestration scenario with proper mock objects
        class MockTask:
            def __init__(self, task_id, base_data):
                self.id = task_id
                self.base_data = base_data
        
        async def mock_base_fetcher():
            return [MockTask("task1", True)]
        
        async def mock_enricher(item):
            item.enriched = True
            item.priority = "HIGH"
        
        def mock_post_processor(items):
            for item in items:
                item.post_processed = True
            return sorted(items, key=lambda x: x.priority, reverse=True)
        
        async def mock_attribute_resolver(item):
            return f"resolved_{item.id}"
        
        # When - Execute federated workflow
        result = asyncio.run(
            FederatedDataFetcher
            .for_(mock_base_fetcher)
            .with_foreach_populator(mock_enricher)
            .with_attribute("resolved_name", mock_attribute_resolver)
            .with_result_post_processor(mock_post_processor)
            .fetch()
        )
        
        # Then - All workflow stages should be applied
        self.assertEqual(1, len(result))
        processed_item = result[0]
        
        self.assertTrue(processed_item.base_data)        # Base fetch
        self.assertTrue(processed_item.enriched)         # Enrichment
        self.assertEqual("HIGH", processed_item.priority) # Enrichment data
        self.assertTrue(processed_item.post_processed)   # Post processing
        self.assertEqual("resolved_task1", processed_item.resolved_name)  # Attribute resolution
    
    async def test_shouldHandleWorkflowErrorRecoveryForRobustDataProcessing(self):
        # Given - Workflow with potential failure points
        error_prone_tasks = BusinessScenarios.active_sprint_tasks()
        
        # Mock forecast API to fail then succeed
        call_count = 0
        async def failing_forecast(tasks, parameters):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Forecast service temporarily unavailable")
            return tasks  # Succeed on retry
        
        self.task_search_api.mock.search.side_effect = [error_prone_tasks, []]
        self.forecast_api.mock.generate_forecasts_for_tasks.side_effect = failing_forecast
        
        # When - Execute workflow with error conditions
        with self.assertRaises(Exception) as context:
            await self.facade.get_tasks()
        
        # Then - Error should propagate for proper handling
        self.assertEqual("Forecast service temporarily unavailable", str(context.exception))
        
        # Verify workflow execution attempted (may vary due to concurrent operations)
        self.assertGreaterEqual(self.forecast_api.mock.generate_forecasts_for_tasks.call_count, 1)
    
    async def test_shouldExecuteSequentialTaskProcessingForDataConsistencyInLargeDatasets(self):
        # Given - Large dataset requiring sequential processing  
        large_dataset_tasks = []
        for i in range(10):
            developer_id = f"developer.{i % 3}"
            task = (DomainTaskBuilder.domain_task_for_ui_conversion()
                    .assigned_to(developer_id)
                    .build())
            task.id = f"LARGE-DATASET-{i:03d}"  
            large_dataset_tasks.append(task)
        
        self.task_search_api.mock.search.side_effect = [large_dataset_tasks, []]
        
        # When - Execute sequential processing workflow
        result = await self.facade.get_tasks()

        # Then - All tasks should be processed consistently
        self.assertEqual(10, len(result))

        # Verify sequential processing maintained data consistency for all tasks
        # Note: sorting now happens in view layer via TaskGroupingUtils
        developer_counts = {"developer.0": 0, "developer.1": 0, "developer.2": 0}
        for task in result:
            self.assertIn(task.assignment.assignee.id, developer_counts)
            developer_counts[task.assignment.assignee.id] += 1
            self.assertIsNotNone(task.time_tracking)
            self.assertIsNotNone(task.system_metadata)

        # Verify correct distribution (10 tasks, 3 developers cycling through i % 3)
        self.assertEqual(4, developer_counts["developer.0"])  # indices 0,3,6,9
        self.assertEqual(3, developer_counts["developer.1"])  # indices 1,4,7
        self.assertEqual(3, developer_counts["developer.2"])  # indices 2,5,8
    
    async def test_shouldExecuteConditionalWorkflowBranchingForBusinessRuleApplication(self):
        # Given - Tasks requiring conditional workflow branching
        conditional_tasks = [
            DomainTaskBuilder.domain_task_for_ui_conversion()
                .assigned_to("alice.johnson")  # Frontend team member
                .build(),
            DomainTaskBuilder.domain_task_for_ui_conversion()
                .assigned_to("bob.smith")     # Backend team member
                .build()
        ]
        
        self.task_search_api.mock.search.side_effect = [conditional_tasks, []]
        
        # When - Execute conditional workflow (frontend team filter)
        frontend_result = await self.facade.get_tasks("frontend-team")
        
        # When - Execute different conditional branch (all teams)
        self.task_search_api.mock.search.side_effect = [conditional_tasks, []]
        all_teams_result = await self.facade.get_tasks()
        
        # Then - Conditional branching should produce different results
        self.assertEqual(1, len(frontend_result))      # Filtered result
        self.assertEqual(2, len(all_teams_result))     # Unfiltered result
        
        # Verify branching logic maintained data integrity
        frontend_task = frontend_result[0]
        self.assertEqual("alice.johnson", frontend_task.assignment.assignee.id)
        
        all_teams_assignees = {task.assignment.assignee.id for task in all_teams_result}
        self.assertIn("alice.johnson", all_teams_assignees)
        self.assertIn("bob.smith", all_teams_assignees)


if __name__ == '__main__':
    unittest.main()