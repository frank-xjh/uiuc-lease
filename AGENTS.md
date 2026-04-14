# Plugin Notes

This file records the AstrBot plugin knowledge gathered while setting up and extending this plugin template.

Current plugin path:
`/Users/frank/Projects/AstrBot/data/plugins/helloworld`

Primary official docs:
- https://docs.astrbot.app/dev/star/plugin-new.html
- https://docs.astrbot.app/dev/star/guides/simple.html
- https://docs.astrbot.app/dev/star/guides/listen-message-event.html
- https://docs.astrbot.app/dev/star/guides/send-message.html
- https://docs.astrbot.app/dev/star/guides/plugin-config.html
- https://docs.astrbot.app/dev/star/guides/ai.html
- https://docs.astrbot.app/dev/star/guides/storage.html
- https://docs.astrbot.app/dev/star/guides/session-control.html
- https://docs.astrbot.app/en/dev/star/plugin-publish.html

## Local environment

Run AstrBot from the repo root:

```bash
uv sync
uv run main.py
```

If `uv run` has sandbox issues, use a local cache dir:

```bash
UV_CACHE_DIR=/Users/frank/Projects/AstrBot/.uv-cache uv run main.py
```

The plugin must live under:
`AstrBot/data/plugins/<plugin_name>`

## Required plugin structure

The minimal plugin usually includes:
- `main.py`: plugin class and handlers
- `metadata.yaml`: plugin metadata used by AstrBot

Useful optional files:
- `_conf_schema.json`: WebUI-visible plugin config schema
- `requirements.txt`: plugin-specific Python dependencies
- `README.md`: installation and usage notes
- `resources/`: static assets such as a plugin logo

## Template facts

The starter template currently uses:
- `@register("helloworld", "YourName", "一个简单的 Hello World 插件", "1.0.0")`
- a `Star` subclass in `main.py`
- `metadata.yaml` with the template name and repo

Before writing real logic, rename all template identifiers consistently:
- plugin folder name
- `@register(...)` plugin name
- `metadata.yaml` fields
- README and repository URL

## Metadata rules

`metadata.yaml` is required. At minimum keep these fields correct:
- `name`: unique identifier
- `display_name`: human-readable plugin name
- `desc`: short description
- `version`: plugin version
- `author`: plugin author
- `repo`: plugin repository URL

The docs also mention optional marketplace-facing assets and metadata such as:
- plugin logo
- support channel / social links
- supported platform information

## Main plugin class

Typical imports:

```python
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
```

Typical shape:

```python
@register("plugin_name", "Author", "Description", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    async def initialize(self):
        ...

    async def terminate(self):
        ...
```

Notes:
- `initialize()` is optional and runs after instantiation.
- `terminate()` is optional and runs when the plugin is unloaded or disabled.

## Command and message handling

Use `filter` decorators to register handlers.

Common patterns:
- `@filter.command("name")`
- `@filter.command_group("group")`
- `@filter.regex(...)`
- `@filter.event_message_type(...)`
- permission or admin filters when needed

Handler conventions:
- Handlers usually accept `event: AstrMessageEvent`
- For simple replies, return or `yield` an event result such as `event.plain_result(...)`
- Use docstrings on handlers because AstrBot can expose them as handler descriptions

Useful event accessors from the docs and template:
- `event.message_str`: plain text content
- `event.get_messages()`: message chain
- `event.get_sender_name()`

## Sending messages

For normal responses, prefer AstrBot result helpers instead of building raw protocol payloads.

Examples from the docs include:
- plain text messages
- message chains combining multiple message components
- replies to the current session or target context

When building richer messages, check `astrbot.api.message_components`.

## Session control

Normal command handlers can often `yield` results directly.

For multi-step or session-controller flows:
- use `await event.send(...)` for intermediate output
- call `event.stop_event()` when this plugin should stop further event propagation

Do not assume `yield` is enough for long interactive flows.

## Plugin configuration

AstrBot plugin configuration is defined through `_conf_schema.json`.

Use config schema for:
- typed fields
- defaults
- descriptions shown in WebUI
- secrets or tokens that should be user-configurable

Implementation guidance:
- read plugin config from the plugin instance rather than hardcoding values
- prefer schema-backed config over environment-variable-only plugin behavior
- keep names stable because WebUI and saved config depend on them

## AI capabilities

AstrBot exposes AI-related APIs for plugins. The docs cover:
- generating model output through the platform AI layer
- tool-loop / agent-like workflows
- conversation-aware integrations when needed

Guidance:
- use AstrBot's AI abstractions instead of calling model vendors directly unless there is a specific need
- keep provider-specific logic isolated
- treat AI calls as optional plugin capabilities and degrade cleanly on failure

## Storage and files

Do not write plugin runtime data into the plugin source folder unless it is actually source-controlled content.

Use AstrBot data-path utilities and `pathlib.Path` for:
- cached files
- plugin state
- generated artifacts
- temporary files

General rule:
- source code stays in the plugin directory
- runtime data stays in AstrBot-managed data or temp directories

## Dependencies

If the plugin needs extra Python packages:
- add them to the plugin's own `requirements.txt` if AstrBot expects plugin-local dependencies in your workflow
- otherwise verify whether the dependency belongs in the main AstrBot environment

Avoid unnecessary dependencies. Prefer AstrBot APIs first.

## Publishing checklist

Before publishing:
- ensure `metadata.yaml` is accurate
- replace template names and URLs
- provide a clear README
- include a recognizable logo if the marketplace listing uses one
- verify supported platforms
- test install and basic command flow on a clean AstrBot instance

## Working rules for this plugin

- Keep new code comments in English.
- Prefer `pathlib.Path` for path handling.
- Prefer AstrBot APIs over direct platform-specific protocol code.
- Use concise handlers and move reusable logic into helper functions or modules if the plugin grows.
- If adding WebUI config, update `_conf_schema.json` and document expected values in `README.md`.
