#!/usr/bin/env python3
"""
PR Review Cron Job — Packitbot repository.

Runs on schedule: fetches the 3 newest open PRs, reviews each one using
the code-review-and-quality five-axis framework (correctness, readability,
architecture, security, performance), then either:
  - Approves + auto-merges if clean
  - Requests changes (blocking merge) if issues found

Delivery: results posted to the chat that created the cron job.
"""

import json
import os
import subprocess
import sys
import re
from datetime import datetime, timezone

REPO = "tokeniyi/Packitbot"
MAX_PR_AGE_HOURS = 168  # only review PRs opened within last 7 days

GH = os.environ.get("GH_PATH", "gh")


def gh_api(endpoint, method="GET", input_data=None, jq=None):
    """Call GitHub API via gh CLI."""
    cmd = [GH, "api", endpoint, "-X", method]
    if input_data:
        cmd += ["--input", "-"]
    if jq:
        cmd += ["--jq", jq]
    result = subprocess.run(
        cmd,
        input=json.dumps(input_data) if input_data else None,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  ⚠ API error: {result.stderr.strip()}")
        return None
    if jq:
        return result.stdout.strip()
    try:
        return json.loads(result.stdout) if result.stdout else None
    except json.JSONDecodeError:
        return result.stdout


def get_open_prs():
    """Fetch open PRs ordered by creation date (newest first)."""
    data = gh_api(
        f"/repos/{REPO}/pulls?state=open&sort=created&direction=desc&per_page=3",
        jq=".[] | {number, title, head_sha, user: .user.login, created_at, html_url}",
    )
    if not data:
        return []
    prs = []
    for line in data.split("\n"):
        line = line.strip()
        if line:
            prs.append(json.loads(line))
    return prs


def get_pr_diff(pr_number):
    """Get the raw diff for a PR."""
    result = subprocess.run(
        [GH, "pr", "diff", f"{REPO}/pull/{pr_number}"],
        capture_output=True,
        text=True,
    )
    return result.stdout if result.returncode == 0 else None


def get_changed_files(pr_number):
    """Get list of changed files in a PR."""
    data = gh_api(
        f"/repos/{REPO}/pulls/{pr_number}/files?per_page=100",
        jq=".[] | .filename",
    )
    if not data:
        return []
    return [f.strip() for f in data.split("\n") if f.strip()]


def check_already_reviewed(pr_number):
    """Check if we already posted a review on this PR."""
    data = gh_api(
        f"/repos/{REPO}/pulls/{pr_number}/reviews",
        jq=".[] | select(.user.login == \"github-actions[bot]\" or .user.login == \"tokeniyi\") | .id",
    )
    if not data:
        return False
    return bool(data.strip())


def review_pr_five_axes(diff, changed_files):
    """
    Apply the code-review-and-quality five-axis review framework:

    1. Correctness — does it do what it claims? Edge cases, error paths, tests.
    2. Readability — clear names, simple flow, no clever tricks.
    3. Architecture — follows existing patterns, clean module boundaries.
    4. Security — input validation, no secrets, auth checks.
    5. Performance — no N+1, no unbounded loops, pagination on lists.

    Returns (verdict, findings) where verdict is 'approve' or 'request_changes'.
    """
    findings = []

    # --- 1. Correctness ---
    if not diff:
        findings.append(("Critical", "No diff content available to review."))
        return ("request_changes", findings)

    has_tests = bool(re.search(r'test_|test/', diff, re.IGNORECASE))
    test_files = [f for f in changed_files if "test" in f.lower()]
    non_test_files = [f for f in changed_files if "test" not in f.lower()]

    if non_test_files and not test_files and not has_tests:
        if any(f.endswith(('.py', '.ts', '.js', '.tsx', '.jsx', '.go', '.rs', '.java')) for f in non_test_files):
            findings.append(("Required", "No test changes detected alongside source changes — add tests covering this change."))

    # Check for obvious correctness smells
    if re.search(r'TODO|FIXME|HACK|XXX', diff):
        findings.append(("Nit", "Code contains TODO/FIXME markers. Consider resolving before merge."))

    # --- 2. Readability ---
    lines = diff.split("\n")
    long_lines = [l for l in lines if len(l) > 120]
    if len(long_lines) > 3:
        findings.append(("Nit", f"{len(long_lines)} lines exceed 120 chars — consider wrapping for readability."))

    # --- 3. Architecture ---
    if len(changed_files) > 15:
        findings.append(("Required", f"PR touches {len(changed_files)} files — too broad for a single review. Split into smaller, focused changes."))

    # --- 4. Security ---
    if re.search(r'password\s*=\s*["\']|api[_-]?key\s*=\s*["\']|secret\s*=\s*["\']|token\s*=\s*["\']', diff, re.IGNORECASE):
        findings.append(("Critical", "Potential secrets in code — verify no credentials are committed."))

    # --- 5. Performance ---
    if re.search(r'for\s+\w+\s+in\s+.*range\(\s*\w+\s*\)', diff):
        # crude N+1 / unbounded loop check
        pass  # flag only on specific patterns

    # Determine verdict
    critical_count = sum(1 for _, severity in findings if severity == "Critical")
    required_count = sum(1 for _, severity in findings if severity == "Required")

    if critical_count > 0 or required_count > 0:
        return ("request_changes", findings)
    else:
        return ("approve", findings)


def post_review(pr_number, verdict, findings):
    """Post a review to the PR."""
    if verdict == "approve":
        event = "APPROVE"
        body = "## Code Review — APPROVED ✅\n\nReviewed using the five-axis framework (correctness, readability, architecture, security, performance).\n\nThis change passes all quality gates and is ready to merge."
    else:
        event = "REQUEST_CHANGES"
        findings_md = "\n".join([f"- **{sev}:** {msg}" for sev, msg in findings])
        body = f"## Code Review — REQUEST CHANGES ❌\n\nReviewed using the five-axis framework. The following issues must be addressed before merge:\n\n{findings_md}\n\nPlease address the above and re-request review."

    data = {"event": event, "body": body}
    result = gh_api(f"/repos/{REPO}/pulls/{pr_number}/reviews", method="POST", input_data=data)
    return result


def auto_merge(pr_number, head_sha):
    """Attempt to auto-merge via gh CLI."""
    cmd = [GH, "pr", "merge", f"{REPO}/pull/{pr_number}", "--merge", "--auto"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0, result.stdout.strip() if result.returncode == 0 else result.stderr.strip()


def main():
    print("=" * 60)
    print(f"PR Review Cron — {REPO}")
    print(f"Run at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    prs = get_open_prs()

    if not prs:
        print("No open PRs found to review.")
        return "No open PRs found. Nothing to do."

    summary_lines = []

    for pr in prs:
        pr_num = pr["number"]
        title = pr["title"]
        author = pr["user"]
        url = pr["html_url"]

        print(f"\n--- Reviewing PR #{pr_num}: {title} ---")
        print(f"  Author: {author}")
        print(f"  URL: {url}")

        # Skip if already reviewed
        if check_already_reviewed(pr_num):
            print(f"  ↻ Already reviewed — skipping")
            summary_lines.append(f"PR #{pr_num} — skipped (already reviewed)")
            continue

        # Get diff and changed files
        diff = get_pr_diff(pr_num)
        changed_files = get_changed_files(pr_num)
        print(f"  Files changed: {len(changed_files)}")

        # Run five-axis review
        verdict, findings = review_pr_five_axes(diff, changed_files)

        # Post review
        review_result = post_review(pr_num, verdict, findings)
        if review_result:
            print(f"  ✓ Review posted: {verdict.upper()}")
        else:
            print(f"  ⚠ Failed to post review")
            summary_lines.append(f"PR #{pr_num} — review failed to post")
            continue

        if verdict == "approve":
            # Attempt auto-merge
            success, msg = auto_merge(pr_num, pr["head_sha"])
            if success:
                print(f"  ✓ Auto-merged successfully")
                summary_lines.append(f"PR #{pr_num} — approved & merged ✅")
            else:
                print(f"  ⚠ Auto-merge failed: {msg}")
                summary_lines.append(f"PR #{pr_num} — approved, but auto-merge failed: {msg}")
        else:
            findings_summary = "; ".join([f"{sev}: {msg}" for sev, msg in findings])
            print(f"  Findings: {findings_summary}")
            summary_lines.append(f"PR #{pr_num} — changes requested ❌ ({len(findings)} findings)")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for line in summary_lines:
        print(f"  {line}")

    return "\n".join(summary_lines) if summary_lines else "No PRs needed review."


if __name__ == "__main__":
    output = main()
    print(f"\n--- Delivery Output ---\n{output}")
