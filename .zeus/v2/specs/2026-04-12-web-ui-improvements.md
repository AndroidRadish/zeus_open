# v2 Web UI Improvements & Multi-language Support Spec

> **Project**: zeus-open v2 enhancement  
> **Topic**: Milestone-centric progress view and task i18n (EN/ZH)  
> **North Star Impact**: `developer_adoption_rate` ↑↑, `ui_usability` ↑↑  

---

## 1. Problem Statement

### 1.1 Wave-based redundancy
The current Dashboard forces users to switch waves via a dropdown to inspect tasks. As the number of waves grows, this becomes increasingly redundant and prevents humans from getting a smooth, holistic view of project progress.

### 1.2 Missing multi-language support
A previous backlog item requested multi-language task descriptions, but it was never implemented. Currently, task `title` and `description` are monolingual, limiting collaboration in mixed-language teams.

## 2. Objectives

- Provide a **Milestone-centric progress view** that groups tasks by roadmap milestone (M-001, M-002…), eliminating the need to jump between waves.
- Add **language switching** (中文 / English) to the Web UI.
- Extend the task schema to support `title_en`, `title_zh`, `description_en`, `description_zh`.
- Ensure backward compatibility: if i18n fields are absent, fall back to the existing `title`/`description`.

## 3. Architecture

### 3.1 Milestone View

New API endpoint:
```
GET /milestones?version=v2
```

Returns:
```json
{
  "milestones": [
    {
      "id": "M-001",
      "title": "v2 Infrastructure",
      "status": "completed",
      "progress_percent": 100,
      "tasks": [
        { "id": "T-001", "title": "...", "passes": true, "wave": 1 }
      ]
    }
  ]
}
```

`status` rules:
- `completed` — all tasks pass
- `in_progress` — at least one task done, but not all
- `pending` — no tasks done

Web UI changes:
- New tab: **里程碑 / Milestones**
- Each milestone rendered as a card with:
  - Title + status badge
  - Progress bar
  - Expandable task table (ID, localized title, status, wave)

### 3.2 Multi-language Support

Schema extension (`task.schema.json`):
```json
"title_en": { "type": "string" },
"title_zh": { "type": "string" },
"description_en": { "type": "string" },
"description_zh": { "type": "string" }
```

All fields are optional.

Web UI localization strategy:
- `lang` ref defaults to `'zh'` (since the existing UI is Chinese).
- Language toggle button in the header.
- Helper `getLocalized(task, field)`:
  - returns `task[`${field}_${lang}`]` if present
  - else falls back to `task[field]`
- All task-rendering locations (Dashboard, Milestones, Agents) use the helper.

Backend prompt builder (`zeus_orchestrator.py`):
- When building `PROMPT.md`, prefer `title_zh` / `description_zh` if the prompt language is Chinese, otherwise fall back to `title`/`description`. (For now, keep the existing Chinese prompt and simply prefer `title_zh` when available.)

### 3.3 Data Seeding

Populate i18n fields for all 22 existing v2 tasks:
- `title_en` = original English title (for tasks already in English)
- `title_zh` = concise Chinese translation
- `description_en` = English description (derive from existing or write brief summary)
- `description_zh` = Chinese description

## 4. Task Breakdown

| Wave | Task | Description |
|------|------|-------------|
| 8 | T-023 | Add `/milestones` endpoint and Web UI "Milestones" tab |
| 8 | T-024 | Extend task schema with i18n fields; update backend/UI to consume them; add language switcher |
| 8 | T-025 | Seed i18n data for all existing v2 tasks; update docs |

## 5. Acceptance Criteria

- [ ] `/milestones` returns correct progress grouped by roadmap milestone.
- [ ] Web UI renders the Milestones tab without wave-switching friction.
- [ ] `task.schema.json` accepts optional `title_en`, `title_zh`, `description_en`, `description_zh`.
- [ ] Language toggle switches task titles/descriptions instantly; missing i18n fields fall back gracefully.
- [ ] All existing tests still pass; new tests added for `/milestones`.
- [ ] `zeus-execute-v2.md` documents the i18n fields and language toggle.
