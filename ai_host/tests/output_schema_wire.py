import json


def assert_output_schema_delivered(request, expected_schema):
    decoder = json.JSONDecoder()
    for message in request["messages"]:
        if message["role"] not in {"system", "developer"}:
            continue
        content = message["content"]
        if not isinstance(content, str):
            continue
        for index, character in enumerate(content):
            if character != "{":
                continue
            try:
                value, _ = decoder.raw_decode(content[index:])
            except ValueError:
                continue
            if value == expected_schema:
                return
    raise AssertionError("The declared task output schema did not reach trusted model instructions.")
