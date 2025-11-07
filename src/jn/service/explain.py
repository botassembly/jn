"""Service layer: explain pipeline (resolve plan without execution)."""

from typing import Any, Dict

from ..models.project import PipelinePlan, Project


def explain_pipeline(
    config: Project,
    pipeline_name: str,
    show_commands: bool = False,
    show_env: bool = False,
) -> PipelinePlan:
    """
    Build a resolved plan for a pipeline without executing it.

    Args:
        config: The project configuration
        pipeline_name: Name of the pipeline to explain
        show_commands: Include command details (argv/cmd)
        show_env: Include environment variables

    Returns:
        PipelinePlan with pipeline plan details

    Raises:
        ValueError: If pipeline not found
    """
    # Find the pipeline
    pipeline = config.get_pipeline(pipeline_name)
    if not pipeline:
        raise ValueError(f"Pipeline '{pipeline_name}' not found")

    # Build step details
    steps = []

    for step in pipeline.steps:
        step_info: Dict[str, Any] = {
            "type": step.type,
            "name": step.ref,
        }

        if step.type == "source":
            source = config.get_source(step.ref)
            if source:
                step_info["driver"] = source.driver
                step_info["mode"] = source.mode
                if show_commands:
                    if source.driver == "exec" and source.exec:
                        step_info["argv"] = source.exec.argv
                        if source.exec.cwd:
                            step_info["cwd"] = source.exec.cwd
                    elif source.driver == "shell" and source.shell:
                        step_info["cmd"] = source.shell.cmd
                    elif source.driver == "curl" and source.curl:
                        step_info["method"] = source.curl.method
                        step_info["url"] = source.curl.url
                if show_env and source.driver == "exec" and source.exec:
                    step_info["env"] = source.exec.env or {}

        elif step.type == "converter":
            converter = config.get_converter(step.ref)
            if converter:
                step_info["engine"] = converter.engine
                if show_commands and converter.engine == "jq" and converter.jq:
                    step_info["expr"] = converter.jq.expr
                    step_info["raw"] = converter.jq.raw
                    if converter.jq.file:
                        step_info["file"] = converter.jq.file
                    if converter.jq.modules:
                        step_info["modules"] = converter.jq.modules

        elif step.type == "target":
            target = config.get_target(step.ref)
            if target:
                step_info["driver"] = target.driver
                step_info["mode"] = target.mode
                if show_commands:
                    if target.driver == "exec" and target.exec:
                        step_info["argv"] = target.exec.argv
                        if target.exec.cwd:
                            step_info["cwd"] = target.exec.cwd
                    elif target.driver == "shell" and target.shell:
                        step_info["cmd"] = target.shell.cmd
                    elif target.driver == "curl" and target.curl:
                        step_info["method"] = target.curl.method
                        step_info["url"] = target.curl.url
                if show_env and target.driver == "exec" and target.exec:
                    step_info["env"] = target.exec.env or {}

        steps.append(step_info)

    return PipelinePlan(
        pipeline=pipeline_name,
        steps=steps,
    )
