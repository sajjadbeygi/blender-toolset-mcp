"""MCP federation with one semantic tool catalog and explicit routing."""

import json
import logging
import os
from contextlib import AsyncExitStack, asynccontextmanager
from copy import deepcopy
from datetime import timedelta
from urllib.parse import quote, unquote

import anyio
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

from .catalog import Catalog
from .config import Config

log = logging.getLogger(__name__)
RESOURCE_PREFIX = "blender-unified://resource/"


async def pages(fetch, field):
    result, cursor, seen = [], None, set()
    while True:
        page = await fetch(cursor=cursor)
        result.extend(getattr(page, field))
        cursor = page.nextCursor
        if cursor is None:
            return result
        if cursor in seen:
            raise ValueError("Component returned a repeated pagination cursor")
        seen.add(cursor)


def public_uri(engine, uri):
    return RESOURCE_PREFIX + engine + "/" + quote(str(uri), safe="{}")


def error(message):
    return types.CallToolResult(
        isError=True, content=[types.TextContent(type="text", text=message)]
    )


class Gateway:
    def __init__(self, config: Config):
        self.config = config
        self.catalog = Catalog(config.priority, config.routes)
        self.sessions = {}
        self.health = {}
        self.resources = []
        self.templates = []
        self.prompts = {}
        self.active_request = None
        # Commands across different engines may address the SAME Blender scene.
        # Serialize all calls, so changing engine cannot introduce a write race.
        self.scene_lock = anyio.Lock()

    async def elicit(self, context, params):
        if self.active_request is None:
            return types.ElicitResult(action="cancel")
        frontend = self.active_request
        if getattr(params, "mode", "form") == "url":
            return await frontend.session.elicit_url(
                params.message,
                params.url,
                params.elicitationId,
                related_request_id=frontend.request_id,
            )
        return await frontend.session.elicit(
            params.message,
            params.requestedSchema,
            related_request_id=frontend.request_id,
        )

    @asynccontextmanager
    async def connect(self):
        async with AsyncExitStack() as stack:
            for engine in self.config.engines:
                env = {}
                for key, value in engine.env.items():
                    env[key] = (
                        os.environ[value[5:]] if value.startswith("$env:") else value
                    )
                try:
                    transport = await stack.enter_async_context(
                        stdio_client(
                            StdioServerParameters(
                                command=engine.command,
                                args=engine.args,
                                env=env,
                                cwd=engine.cwd,
                            )
                        )
                    )
                    session = await stack.enter_async_context(
                        ClientSession(
                            *transport,
                            read_timeout_seconds=timedelta(seconds=engine.timeout),
                            elicitation_callback=self.elicit,
                        )
                    )
                    init = await session.initialize()
                    tools = (
                        await pages(session.list_tools, "tools")
                        if init.capabilities.tools
                        else []
                    )
                    resources = (
                        await pages(session.list_resources, "resources")
                        if init.capabilities.resources
                        else []
                    )
                    templates = (
                        await pages(
                            session.list_resource_templates, "resourceTemplates"
                        )
                        if init.capabilities.resources
                        else []
                    )
                    prompts = (
                        await pages(session.list_prompts, "prompts")
                        if init.capabilities.prompts
                        else []
                    )
                    candidate = deepcopy(self.catalog)
                    for tool in tools:
                        candidate.add(engine.name, tool)
                    self.catalog = candidate
                    self.sessions[engine.name] = session
                    self.health[engine.name] = {
                        "connected": True,
                        "tools": len(tools),
                        "server": init.serverInfo.model_dump(),
                        "blender_connection": "not probed",
                    }
                    for resource in resources:
                        self.resources.append(
                            resource.model_copy(
                                update={"uri": public_uri(engine.name, resource.uri)}
                            )
                        )
                    for template in templates:
                        self.templates.append(
                            template.model_copy(
                                update={
                                    "uriTemplate": public_uri(
                                        engine.name, template.uriTemplate
                                    )
                                }
                            )
                        )
                    for prompt in prompts:
                        name = "workflow." + prompt.name
                        if name in self.prompts:
                            name += "." + engine.name
                        if name in self.prompts:
                            raise ValueError(f"Ambiguous prompt name: {name}")
                        self.prompts[name] = (engine.name, prompt)
                except Exception as exc:
                    self.health[engine.name] = {
                        "connected": False,
                        "error": type(exc).__name__,
                    }
                    if engine.required:
                        raise RuntimeError(
                            f"Required engine {engine.name} failed to initialize"
                        ) from exc
                    log.warning(
                        "Optional engine %s unavailable: %s",
                        engine.name,
                        type(exc).__name__,
                    )
            self.catalog.validate_routes()
            yield self

    def status(self):
        return {
            "engines": self.health,
            "canonical_tools": len(self.catalog.actions),
            "implementation_routes": sum(len(v) for v in self.catalog.actions.values()),
            "blender_verified": False,
            "note": "MCP engine discovery is not a Blender or external-service health check. The gateway does not retry calls; component retry behavior is unchanged.",
        }

    def rewrite_content(self, engine, content):
        result = []
        for item in content:
            if item.type == "resource_link":
                item = item.model_copy(update={"uri": public_uri(engine, item.uri)})
            elif item.type == "resource":
                item = item.model_copy(
                    update={
                        "resource": item.resource.model_copy(
                            update={"uri": public_uri(engine, item.resource.uri)}
                        )
                    }
                )
            result.append(item)
        return result

    async def call(self, name, arguments, progress=None, request_context=None):
        variant, params = self.catalog.resolve(name, arguments)
        async with self.scene_lock:
            self.active_request = request_context
            try:
                result = await self.sessions[variant.engine].call_tool(
                    variant.tool.name, params, progress_callback=progress
                )
            except Exception as exc:
                # A timeout can happen AFTER a mutation. Never fall back or retry.
                self.health[variant.engine]["last_call_error"] = type(exc).__name__
                return error(
                    f"{name} via {variant.engine} failed ({type(exc).__name__}). "
                    "Execution may have started; inspect Blender before retrying. "
                    "No alternate engine was called."
                )
            finally:
                self.active_request = None
        content = self.rewrite_content(variant.engine, result.content)
        if (
            name == "viewport.screenshot"
            and variant.engine == "modeling"
            and not result.isError
        ):
            # Blend AI returns image bytes in JSON. Expose an MCP image block
            # while retaining its original structured result for machine clients.
            payload = result.structuredContent
            if payload is None and len(content) == 1 and content[0].type == "text":
                try:
                    payload = json.loads(content[0].text)
                except ValueError:
                    payload = None
            if isinstance(payload, dict) and isinstance(payload.get("base64"), str):
                metadata = {k: v for k, v in payload.items() if k != "base64"}
                content = [
                    types.ImageContent(
                        type="image", mimeType="image/png", data=payload["base64"]
                    ),
                    types.TextContent(type="text", text=json.dumps(metadata)),
                ]
        return result.model_copy(update={"content": content})

    async def read(self, uri):
        value = str(uri)
        if value == "blender-unified://inventory":
            return types.ReadResourceResult(
                contents=[
                    types.TextResourceContents(
                        uri=value,
                        mimeType="application/json",
                        text=json.dumps(
                            {**self.status(), "tools": self.catalog.inventory()},
                            indent=2,
                        ),
                    )
                ]
            )
        if not value.startswith(RESOURCE_PREFIX):
            raise ValueError("Unknown resource URI")
        engine, separator, encoded = value[len(RESOURCE_PREFIX) :].partition("/")
        if not separator or engine not in self.sessions:
            raise ValueError("Unknown resource engine")
        async with self.scene_lock:
            result = await self.sessions[engine].read_resource(unquote(encoded))
        return result.model_copy(
            update={
                "contents": [
                    item.model_copy(update={"uri": public_uri(engine, item.uri)})
                    for item in result.contents
                ]
            }
        )

    async def prompt(self, name, arguments):
        engine, definition = self.prompts[name]
        async with self.scene_lock:
            result = await self.sessions[engine].get_prompt(definition.name, arguments)
        mappings = {
            v.tool.name: canonical
            for canonical, variants in self.catalog.actions.items()
            for v in variants
            if v.engine == engine
        }
        note = (
            "This workflow originated from "
            + engine
            + ". Use the unified tool names below. "
            "For this workflow's original parameter conventions, set implementation="
            + engine
            + ". "
            "Consult system.describe_tool for schemas.\n"
            + json.dumps(mappings, sort_keys=True)
        )
        messages = [
            types.PromptMessage(
                role="user", content=types.TextContent(type="text", text=note)
            )
        ]
        messages.extend(
            message.model_copy(
                update={"content": self.rewrite_content(engine, [message.content])[0]}
            )
            for message in result.messages
        )
        return result.model_copy(update={"messages": messages})
