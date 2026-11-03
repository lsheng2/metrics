import json
import sys
from pathlib import Path

from django.core.management.base import BaseCommand, CommandParser

from bug_metrics.app.api.provider_credentials import create_credential_adoption_service
from bug_metrics.app.api.provider_connections import ConnectionError


def error_envelope(code):
    return {"schema_version": 1, "result": None,
            "error": {"code": code, "message": str(ConnectionError(code))}}


class JsonArgumentParser(CommandParser):
    def error(self, message):
        print(json.dumps(error_envelope("INVALID_ARGUMENTS"), sort_keys=True), file=sys.stderr)
        raise SystemExit(2)


class Command(BaseCommand):
    help = "Preview or apply protected provider credentials."
    requires_system_checks = []

    def create_parser(self, prog_name, subcommand, **kwargs):
        parser = super().create_parser(prog_name, subcommand, **kwargs)
        parser.error = self._argument_error
        return parser

    def _argument_error(self, message):
        self.stderr.write(json.dumps(error_envelope("INVALID_ARGUMENTS"), sort_keys=True))
        raise SystemExit(2)

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest="action", required=True, parser_class=JsonArgumentParser)
        preview = subparsers.add_parser("preview")
        preview.add_argument("--profile-id", required=True)
        preview.add_argument("--source-file", required=True)
        apply = subparsers.add_parser("apply")
        apply.add_argument("--profile-id", required=True)
        apply.add_argument("--source-file", required=True)
        apply.add_argument("--preview-file", required=True)
        apply.add_argument("--apply", action="store_true", dest="confirm_apply")
        apply.add_argument("--replace", action="store_true")

    def handle(self, *args, **options):
        try:
            result = self._dispatch(options)
            self.stdout.write(json.dumps({"schema_version": 1, "result": result, "error": None}, sort_keys=True))
        except SystemExit:
            raise
        except ConnectionError as error:
            self.stderr.write(json.dumps({"schema_version": 1, "result": None, "error": self._error(error.code)}, sort_keys=True))
            raise SystemExit(1)
        except Exception:
            self.stderr.write(json.dumps({"schema_version": 1, "result": None, "error": self._error("INTERNAL_ERROR")}, sort_keys=True))
            raise SystemExit(1)

    def _dispatch(self, options):
        self._validate_local_path(options.get("source_file"))
        service = create_credential_adoption_service()
        if options["action"] == "preview":
            return service.preview(options["profile_id"], options["source_file"]).to_dict()
        if not options.get("confirm_apply"):
            raise ConnectionError("INVALID_ARGUMENTS")
        preview = self._load_preview_file(options.get("preview_file"))
        return service.apply(
            options["profile_id"],
            options["source_file"],
            expected_preview=preview,
            replace=bool(options.get("replace")),
        ).to_dict()

    def _validate_local_path(self, value):
        if not value or not isinstance(value, str):
            raise ConnectionError("INVALID_ARGUMENTS")

    def _load_preview_file(self, value):
        self._validate_local_path(value)
        path = Path(value)
        if not path.is_file():
            raise ConnectionError("INVALID_ARGUMENTS")
        try:
            with path.open("rb") as source:
                raw = source.read(65537)
            if len(raw) > 65536:
                raise ValueError("Preview exceeds limit")
            value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object)
            if isinstance(value, dict) and "schema_version" in value:
                if (set(value) != {"schema_version", "result", "error"}
                        or type(value["schema_version"]) is not int or value["schema_version"] != 1
                        or value["error"] is not None or not isinstance(value["result"], dict)):
                    raise ValueError("Invalid preview envelope")
                return value["result"]
            return value
        except Exception:
            raise ConnectionError("INVALID_ARGUMENTS") from None

    def _error(self, code: str) -> dict:
        return error_envelope(code)["error"]


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate preview key")
        value[key] = item
    return value
