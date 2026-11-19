import json


ARGUMENTS = {
    'profile_id': 'chiplet-2a-jira', 'chart_id': 'open_bug_trend',
    'requested_series': ['new_critical_high'],
    'range_mode': 'ww', 'range_start': '26WW32', 'range_end': '26WW35',
}


def completion(content, *, tool_name=None, arguments=None, call_id='synthetic-call'):
    message = {'role': 'assistant', 'content': content}
    if tool_name:
        message['tool_calls'] = [{
            'id': call_id, 'type': 'function',
            'function': {'name': tool_name, 'arguments': json.dumps(arguments)},
        }]
    return {
        'id': call_id, 'object': 'chat.completion', 'created': 1794873600, 'model': 'scripted',
        'choices': [{'index': 0, 'message': message, 'finish_reason': 'tool_calls' if tool_name else 'stop'}],
        'usage': {'prompt_tokens': 12, 'completion_tokens': 6, 'total_tokens': 18},
    }


class MetricToolResponse(dict):
    def __init__(self, tool_name, arguments, call_id):
        super().__init__()
        self.tool_name, self.arguments, self.call_id = tool_name, arguments, call_id

    def __call__(self, request):
        offered = [
            item['function']['name'] for item in request.get('tools', [])
            if item.get('function', {}).get('description') == f'metrics tool {self.tool_name}'
        ]
        if len(offered) != 1:
            raise ValueError(f'Expected exactly one offered {self.tool_name} tool.')
        return completion('Synthetic tool request.', tool_name=offered[0],
                          arguments=self.arguments, call_id=self.call_id)


def publication_responses():
    return [
        MetricToolResponse('metrics.catalog', {}, 'synthetic-catalog'),
        MetricToolResponse('metrics.chart_workflow', ARGUMENTS, 'synthetic-workflow'),
        MetricToolResponse('metrics.publish_chart', ARGUMENTS, 'synthetic-publication'),
        completion('Synthetic publication completed.'),
    ]
