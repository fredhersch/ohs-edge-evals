---
name: review-github-issues
description: >-
  Systematic workflow for reviewing, triaging, implementing, and closing GitHub issues
  created via the inline agent feedback widget or collaborators on the repository.
  Use this skill whenever the user says "review issues", "check issues", "address feedback",
  "triage open issues", or asks the agent to resolve GitHub issues for this project.
---

# Review GitHub Issues Skill

This skill guides the agent through an end-to-end, automated process for reviewing and addressing open GitHub issues on `fredhersch/ohs-edge-evals`, specifically those created using the **Inline Agent Feedback Widget**.

## Quick Execution

Run the issue fetcher script to get an immediate structured summary of all open issues:

```bash
python3 .agents/skills/review-github-issues/scripts/fetch_issues.py
```

---

## Workflow Steps

### Step 1: Fetch and Group Open Issues

1. Execute the helper script:
   `python3 .agents/skills/review-github-issues/scripts/fetch_issues.py`
2. Parse the output. For each issue, identify:
   - **Issue Number** (`#ID`)
   - **Category**: `UI Fix`, `Copy`, `Bug`, `Feature`
   - **Target File / Page**: (e.g. `docs/acdu-architecture.html`, `docs/datasets.html`)
   - **Target Selector / DOM Element**: (e.g. `h2`, `span.font-bold`)
   - **Element Text**: The exact snippet of text on the page
   - **User Directive / Action**: What the user requested to change or fix
3. **Group by File**: Cluster issues that target the same HTML or documentation file so they can be reviewed and edited in a single cohesive pass.

---

### Step 2: Grounding and File Review

For each target file:
1. Open the file and locate the exact section using the target element text or selector:
   ```bash
   git grep -n "<Element Text Snippet>" <Target File>
   ```
2. Read the surrounding context (20–50 lines before and after) to understand the component structure, styling classes, and semantic intent.
3. Cross-reference related issues on the same page to avoid contradictory edits or multiple conflicting rewrites.

---

### Step 3: Implementation Guidelines

When applying changes for an issue:
1. **Preserve Documentation Integrity**:
   - Keep unaffected sections, code samples, LaTeX math, and diagrams intact.
   - Match existing Tailwind CSS classes, color themes (`var(--background)`, `var(--card)`, etc.), and typography.
2. **Handle Special Directives**:
   - **"Clarify or remove for now"**: If a complex section is confusing, either streamline it to its core takeaway or collapse/hide it cleanly.
   - **"Move to X page" / "Link to X"**: If the user directs content to be moved or linked, verify the destination file exists (e.g., `acdu-architecture.html`, `datasets.html`), add the cross-link, and remove or summarize the duplicated section.
   - **"Make it collapsible"**: Use standard `<details class="group ..."><summary>...</summary>...</details>` styled to match the dark card theme.
   - **"Connect the threads"**: Ensure narrative transitions between sections are intuitive and explain *why* an evaluation or component matters for frontline clinical practice.

---

### Step 4: Verification

Before committing:
1. **HTML & Syntax Validation**:
   - Check that tags, scripts, and styling remain well-formed:
     ```bash
     git diff <Target File>
     ```
   - Ensure the inline feedback widget script tag `<script src="assets/js/agent-feedback.js?v=3" defer></script>` is preserved at the end of the `<body>`.
2. **Review Diff**:
   - Run `git diff --stat` and verify that only intended files and sections were modified.

---

### Step 5: Commit, Push, and Auto-Close

1. Stage modified files:
   ```bash
   git add <modified files>
   ```
2. Commit using GitHub closing keywords to automatically close the resolved issues:
   ```bash
   git commit -m "fix(docs): address review feedback for datasets and benchmarks (fixes #X, fixes #Y)"
   ```
3. Push to `main`:
   ```bash
   git push origin main
   ```
4. Confirm closure on GitHub:
   ```bash
   python3 -c "
   import urllib.request, json, ssl
   ctx = ssl._create_unverified_context()
   data = json.loads(urllib.request.urlopen('https://api.github.com/repos/fredhersch/ohs-edge-evals/issues?state=closed&per_page=10', context=ctx).read())
   for i in data[:5]: print(f'Closed #{i[\"number\"]}: {i[\"title\"]}')
   "
   ```

---

### Step 6: User Report Format

Always present a clear Markdown summary table when concluding an issue review run:

| Issue | Target Page & Element | Directive | Action Taken | Status |
| :--- | :--- | :--- | :--- | :--- |
| **#28** | `docs/datasets.html` (`span.text-white`) | Fix UI navigation | Added prominent back/home link to header navigation | **Closed** ✅ |
| **#26** | `docs/benchmarks.html` (`h2`) | Clarify or remove AST section | Streamlined explanation and converted to collapsible card | **Closed** ✅ |
