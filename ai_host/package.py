from ai_base_runtime.apps import AgentDefinition, AppPackage, TaskProfile

from project_management.app.api.ai_profiles import load_task_profiles

from ai_host.settings import APP_ID
from ai_host.context_provider import WORKBENCH_CONTEXT_PROVIDER
from ai_host.host_actions import WORKBENCH_HOST_ACTIONS


METRICS_AGENT = AgentDefinition(
    name='dashboard',
    instructions=(
        'You are embedded in Metrics Dashboard. Use only capabilities declared '
        'by this app package and the authenticated Metrics principal.'
    ),
)

METRICS_APP = AppPackage(
    app_id=APP_ID,
    agents=(METRICS_AGENT,),
    context_providers=(WORKBENCH_CONTEXT_PROVIDER,),
    host_actions=WORKBENCH_HOST_ACTIONS,
    task_profiles=tuple(
        TaskProfile(
            id=profile.id,
            version=profile.version,
            instructions=profile.instructions,
            input_schema=profile.input_schema,
            output_schema=profile.output_schema,
            definition_digest=profile.definition_sha256,
            limits=profile.limits,
        )
        for profile in load_task_profiles()
    ),
)
