import asyncio
import json
import logging
from typing import Any, Dict, Optional

import jsonschema

logger = logging.getLogger(__name__)


class ToolExecutionError(Exception):
    """Raised when tool execution fails."""
    pass


class ToolExecutor:
    """Executes tools in subprocess sandbox with JSON Schema validation and timeout."""

    MAX_OUTPUT_SIZE = 65536  # 64KB max output

    async def execute(
        self,
        tool_name: str,
        input_data: Dict[str, Any],
        input_schema: Dict[str, Any],
        execution_command: Optional[str] = None,
        timeout_seconds: int = 30,
    ) -> Dict[str, Any]:
        """Validate input against schema, execute tool, return result."""
        self._validate_input(input_data, input_schema, tool_name)

        result = await self._execute_subprocess(
            tool_name=tool_name,
            input_data=input_data,
            execution_command=execution_command,
            timeout_seconds=timeout_seconds,
        )

        return result

    def _validate_input(
        self,
        input_data: Dict[str, Any],
        schema: Dict[str, Any],
        tool_name: str,
    ) -> None:
        """Validate tool input against JSON Schema. Raise ToolExecutionError on failure."""
        try:
            jsonschema.validate(instance=input_data, schema=schema)
        except jsonschema.ValidationError as e:
            raise ToolExecutionError(
                f"Invalid input for tool '{tool_name}': {e.message}"
            )

    async def _execute_subprocess(
        self,
        tool_name: str,
        input_data: Dict[str, Any],
        execution_command: Optional[str],
        timeout_seconds: int,
    ) -> Dict[str, Any]:
        """Execute tool as subprocess with timeout. Tools read JSON from stdin, write JSON to stdout."""
        if not execution_command:
            logger.info(
                "Tool '%s' has no execution command — returning mock result",
                tool_name,
            )
            return {
                "status": "success",
                "output": f"Tool '{tool_name}' executed (no command configured)",
                "input_received": input_data,
            }

        process = None
        try:
            process = await asyncio.create_subprocess_exec(
                *execution_command.split(),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            input_bytes = json.dumps(input_data).encode()
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=input_bytes),
                timeout=timeout_seconds,
            )

            stdout_text = stdout.decode()[: self.MAX_OUTPUT_SIZE]

            if process.returncode != 0:
                stderr_text = stderr.decode()[:1024]
                raise ToolExecutionError(
                    f"Tool '{tool_name}' failed with exit code {process.returncode}: {stderr_text}"
                )

            try:
                return json.loads(stdout_text)
            except json.JSONDecodeError:
                return {"status": "success", "output": stdout_text}

        except asyncio.TimeoutError:
            if process and process.returncode is None:
                process.kill()
                await process.wait()
            raise ToolExecutionError(
                f"Tool '{tool_name}' timed out after {timeout_seconds}s"
            )
        except FileNotFoundError:
            raise ToolExecutionError(
                f"Tool '{tool_name}' command not found: {execution_command}"
            )
