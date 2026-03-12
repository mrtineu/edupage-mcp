# EduPage MCP Server

An MCP server that enables AI agents to query student data from EduPage. This server provides tools to access timetables, grades, notifications, and more through the Model Context Protocol.

## 1. Project Title and Description
The EduPage MCP Server is a bridge between the EduPage school platform and AI agents. It uses the `edupage-api` library to securely fetch information and exposes it via the Model Context Protocol (MCP).

Available tools include:
- `get_timetable`: Get the student's timetable for a specific date.
- `get_grades`: Get the student's grades, optionally filtered by year and term.
- `get_notifications`: Get timeline notifications, optionally filtered from a start date.
- `get_teachers`: Get all teachers at the school.
- `get_students`: Get students in your class.
- `get_classes`: Get all classes at the school.
- `get_subjects`: Get all subjects taught at the school.
- `get_meals`: Get the school meal menu for a specific date.
- `get_timetable_changes`: Get timetable substitutions/changes for a specific date.
- `get_missing_teachers`: Get list of absent teachers for a specific date.

## 2. Prerequisites
- Python 3.10 or higher
- An EduPage student account (without 2FA enabled)
- Your school's EduPage subdomain (e.g., if your school is at `schoolname.edupage.org`, the subdomain is `schoolname`)

## 3. Setup
1. Clone or download this project
2. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -e .
   ```
4. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
5. Fill in your credentials in `.env`:
   - `EDUPAGE_USERNAME`: Your EduPage username
   - `EDUPAGE_PASSWORD`: Your EduPage password
   - `EDUPAGE_SUBDOMAIN`: Your school's subdomain

## 4. Running
### Direct Execution
```bash
python server.py
```

### With MCP CLI
```bash
mcp run server.py
```

## 5. OpenCode Configuration
To use this server with an MCP client like OpenCode, add the following configuration to your `mcp.json`:

```json
{
  "mcpServers": {
    "edupage": {
      "command": "python",
      "args": ["/absolute/path/to/server.py"],
      "env": {
        "EDUPAGE_USERNAME": "your_username",
        "EDUPAGE_PASSWORD": "your_password",
        "EDUPAGE_SUBDOMAIN": "your_school"
      }
    }
  }
}
```

## 6. Available Tools
| Tool Name | Parameters | Description |
|-----------|------------|-------------|
| `get_timetable` | `date_str: str` (optional) | Get the student's timetable for a specific date. Defaults to today. |
| `get_grades` | `year: int`, `term: str` (optional) | Get the student's grades. Both `year` and `term` ("P1" or "P2") must be provided together. |
| `get_notifications` | `date_from: str` (optional) | Get timeline notifications, optionally filtered from a start date. |
| `get_teachers` | None | Get all teachers at the school. |
| `get_students` | None | Get students in your class. |
| `get_classes` | None | Get all classes at the school. |
| `get_subjects` | None | Get all subjects taught at the school. |
| `get_meals` | `date_str: str` (optional) | Get the school meal menu for a specific date. Defaults to today. |
| `get_timetable_changes` | `date_str: str` (optional) | Get timetable substitutions/changes for a specific date. Defaults to today. |
| `get_missing_teachers` | `date_str: str` (optional) | Get list of absent teachers for a specific date. Defaults to today. |

## 7. Limitations
- **Read-only**: This server does not support sending messages or uploading files.
- **Student accounts only**: Parent and teacher accounts have not been tested and may not work as expected.
- **No 2FA support**: Two-factor authentication must be disabled on your EduPage account.
- **Session expiry**: Long-running sessions may expire. The server includes a single re-login retry mechanism to handle this transparently.
