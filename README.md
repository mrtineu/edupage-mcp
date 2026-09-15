# edupage-mcp

`edupage-mcp` is a read-only MCP server for EduPage. It lets MCP clients and agents query timetable data, grades, notifications, meals, and school metadata through the `edupage-api` library.

## Supported Features

Supported tools:

- `get_timetable`
- `get_grades`
- `get_notifications`
- `get_teachers`
- `get_students`
- `get_classes`
- `get_subjects`
- `get_meals`
- `get_substitutions`
- `get_timetable_changes`
- `get_homework`
- `download_homework_file`

`get_homework` and `download_homework_file` are not backed by `edupage-api` (which has no homework/material support); they parse EduPage's internal material-player page directly. Pass the `superid` from a homework notification's `additional_data` (see `get_notifications`) to `get_homework` to read the assignment text and list its attachments, then pass an attachment URL to `download_homework_file` to save it locally.

Experimental tool:

- `get_missing_teachers`

`get_missing_teachers` is exposed, but some schools block teacher substitution visibility entirely, so it may return an availability message instead of teacher data.

## Requirements

- Python `3.10+`
- `uv`
- An EduPage account
- EduPage 2FA disabled
- Your school subdomain from `https://<subdomain>.edupage.org`

Environment variables:

```env
EDUPAGE_USERNAME=your_username
EDUPAGE_PASSWORD=your_password
EDUPAGE_SUBDOMAIN=your_school_subdomain
```

## Run It

Install and run from PyPI with `uvx`:

```bash
uvx edupage-mcp
```

For local development:

```bash
uv sync
uv run edupage-mcp
```

The server uses stdio transport, so it is meant to be launched by an MCP client.

## MCP Setup

### OpenCode

Add this to `~/.config/opencode/opencode.json` or project `opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "edupage": {
      "type": "local",
      "command": ["uvx", "edupage-mcp"],
      "environment": {
        "EDUPAGE_USERNAME": "your_username",
        "EDUPAGE_PASSWORD": "your_password",
        "EDUPAGE_SUBDOMAIN": "your_school_subdomain"
      }
    }
  }
}
```

### Claude Desktop

Add this to your Claude Desktop MCP config:

```json
{
  "mcpServers": {
    "edupage": {
      "command": "uvx",
      "args": ["edupage-mcp"],
      "env": {
        "EDUPAGE_USERNAME": "your_username",
        "EDUPAGE_PASSWORD": "your_password",
        "EDUPAGE_SUBDOMAIN": "your_school_subdomain"
      }
    }
  }
}
```

## Tool Summary

| Tool | Parameters | Description |
|---|---|---|
| `get_timetable` | `date_str` | Timetable for a date. Defaults to today. |
| `get_grades` | `year`, `term` | Grades, optionally filtered by school year and term. |
| `get_notifications` | `date_from` | Notifications, optionally from a given date onward. |
| `get_teachers` | none | Teachers at the school. |
| `get_students` | none | Students in the logged-in student's class. |
| `get_classes` | none | School classes. |
| `get_subjects` | none | School subjects. |
| `get_meals` | `date_str` | Meal menu for a date. Defaults to today. |
| `get_substitutions` | `date_str` | Raw substitution rows for a date. Defaults to today. |
| `get_timetable_changes` | `date_str` | Timetable changes for a date. Defaults to today. |
| `get_homework` | `superid` | Full homework/material content (text + attachment list) for a homework notification. |
| `download_homework_file` | `url`, `filename`, `dest_dir` | Download a homework attachment to disk. `dest_dir` overrides the default (`EDUPAGE_DOWNLOAD_DIR` env var, or `~/Downloads/edupage-mcp`). |
| `get_missing_teachers` | `date_str` | Absent teachers for a date. Experimental. |

## Limitations

- Read-only only (`download_homework_file` writes files to local disk, but does not submit or modify anything on EduPage)
- No 2FA support
- Parent and teacher accounts are not verified
- Depends on upstream `edupage-api` behavior



## Acknowledgements

This project would not be possible without the upstream `edupage-api` library:

https://github.com/EdupageAPI/edupage-api
