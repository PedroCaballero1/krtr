"""Keeps the local record of runs launched on Modal.

Exists so a run started with `--detach` can be found again later from its call
id (or listed), without the user copying ids by hand, and so a failed run's
staged files can be located. Runs are kept one JSON object per line in
`.krtr/runs.jsonl`. Consumed by the runner and by the `runs`, `status`,
`result`, `cancel` and `staging clean` commands.
"""

import logging
from pathlib import Path

from pydantic import ValidationError

from krtr.compute.modal.artifacts import RunRecord
from krtr.compute.modal.config import RunStatus

logger = logging.getLogger(__name__)


class RunRegistry:
    """Reads and writes the run records kept in a JSON Lines file.

    Exists to give the rest of the code a small interface (`add`, `list_runs`,
    `get`, `update_status`) over the file, so nothing else parses or rewrites
    it. Consumed by the runner and the CLI commands that report on runs.
    """

    def __init__(self, runs_file: Path) -> None:
        """Binds the registry to a file, which need not exist yet.

        Args:
            runs_file: The JSON Lines file holding one `RunRecord` per line.
        """
        self._runs_file = runs_file

    def add(self, record: RunRecord) -> None:
        """Appends a run record, creating the file and its directory if needed.

        Exists so a run is recorded the moment it is launched.

        Args:
            record: The run to remember.

        Returns:
            None.
        """
        self._runs_file.parent.mkdir(parents=True, exist_ok=True)
        with self._runs_file.open("a", encoding="utf-8") as runs_file:
            runs_file.write(record.model_dump_json() + "\n")
        logger.debug(
            "Recorded run %s (call %s) in %s", record.run_id, record.call_id, self._runs_file
        )

    def list_runs(self) -> list[RunRecord]:
        """Reads every recorded run, oldest first.

        Exists so the `runs` command and the lookups share one parser.

        Returns:
            list[RunRecord]: the records in file order; empty if nothing was ever recorded.

        Raises:
            ValueError: if a line is not a valid run record.
        """
        if not self._runs_file.exists():
            return []
        lines = self._runs_file.read_text(encoding="utf-8").splitlines()
        return [
            self._parse_line(line, line_number)
            for line_number, line in enumerate(lines, start=1)
            if line.strip()
        ]

    def get(self, call_id: str) -> RunRecord:
        """Finds the run launched with a Modal call id.

        Exists so `status`, `result` and `cancel` can act on a run given only
        the id printed when it was launched.

        Args:
            call_id: The Modal function call id of the run.

        Returns:
            RunRecord: the matching record.

        Raises:
            ValueError: if no run was recorded with that call id.
        """
        records = self.list_runs()
        return records[self._index_of(records, call_id)]

    def update_status(self, call_id: str, status: RunStatus) -> RunRecord:
        """Changes the status of one recorded run and saves the file.

        Exists so a run's record follows it from running to finished, failed
        or cancelled. The whole file is rewritten through a temporary file, so
        an interruption cannot leave a half-written registry.

        Args:
            call_id: The Modal function call id of the run to update.
            status: The status to record.

        Returns:
            RunRecord: the updated record.

        Raises:
            ValueError: if no run was recorded with that call id.
        """
        records = self.list_runs()
        index = self._index_of(records, call_id)
        records[index] = records[index].model_copy(update={"status": status})
        self._write_all(records)
        logger.debug("Marked run with call %s as %s", call_id, status.value)
        return records[index]

    def _index_of(self, records: list[RunRecord], call_id: str) -> int:
        """Finds the position of the record with a call id.

        Args:
            records: The records to search.
            call_id: The Modal function call id to look for.

        Returns:
            int: the index of the matching record.

        Raises:
            ValueError: if no record has that call id.
        """
        for index, record in enumerate(records):
            if record.call_id == call_id:
                return index
        raise ValueError(f"No run with call id '{call_id}' is recorded in {self._runs_file}")

    def _parse_line(self, line: str, line_number: int) -> RunRecord:
        """Parses one line of the file into a run record.

        Exists so a corrupt line is reported with its position instead of a
        bare validation error.

        Args:
            line: The JSON text of one record.
            line_number: The 1-based position of the line in the file.

        Returns:
            RunRecord: the parsed record.

        Raises:
            ValueError: if the line is not a valid run record.
        """
        try:
            return RunRecord.model_validate_json(line)
        except ValidationError as error:
            raise ValueError(
                f"Invalid run record at {self._runs_file}:{line_number}: {error}"
            ) from error

    def _write_all(self, records: list[RunRecord]) -> None:
        """Replaces the file's contents with the given records.

        Exists so updates are atomic: the new contents are written to a
        sibling temporary file, which then replaces the registry in one step.

        Args:
            records: The complete list of records to keep.

        Returns:
            None.
        """
        temporary_file = self._runs_file.with_suffix(".jsonl.tmp")
        contents = "".join(record.model_dump_json() + "\n" for record in records)
        temporary_file.write_text(contents, encoding="utf-8")
        temporary_file.replace(self._runs_file)
