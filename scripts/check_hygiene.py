"""Bounded tracked-tree/history checks. Never print matched values or emails."""

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKEN = re.compile(
    rb"(?:sk-(?:proj-|ant-)[A-Za-z0-9_-]{25,}|github_pat_[A-Za-z0-9_]{30,}|gh[pousr]_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)
FORBIDDEN = {
    ".venv",
    ".venv-local",
    ".uk-labour-market-navigator",
    "private",
    "jobs",
    "runs",
    "__pycache__",
    "node_modules",
}


def git(*args):
    return subprocess.check_output(["git", "-c", "core.quotepath=false", *args], cwd=ROOT, stderr=subprocess.DEVNULL)


def inspect(path, body, findings):
    parts = Path(path).parts
    if any(p in FORBIDDEN or p == ".env" or p.startswith(".env.") for p in parts):
        findings.add("Excluded private/generated path: " + path)
    if b"\x00" not in body[:4096] and TOKEN.search(body):
        findings.add("Potential credential pattern in " + path + " (value withheld)")


def main():
    findings = set()
    files = git("ls-files", "--cached", "--others", "--exclude-standard", "-z").decode().split("\x00")
    for name in filter(None, files):
        p = ROOT / name
        if p.is_file():
            inspect(name, p.read_bytes(), findings)
    objects = {}
    for line in git("rev-list", "--objects", "--all").decode().splitlines():
        oid, _, name = line.partition(" ")
        if name:
            objects[oid] = name
    scanned = 0
    with subprocess.Popen(
        ["git", "cat-file", "--batch"],
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    ) as process:
        for oid, name in objects.items():
            # Request and consume each object before filling either OS pipe.
            process.stdin.write((oid + "\n").encode())
            process.stdin.flush()
            header = process.stdout.readline().decode().split()
            if len(header) != 3 or header[0] != oid:
                raise ValueError("Could not enumerate history objects")
            body = process.stdout.read(int(header[2]))
            if process.stdout.read(1) != b"\n":
                raise ValueError("Incomplete history object")
            if header[1] == "blob":
                inspect(name, body, findings)
                scanned += 1
        process.stdin.close()
        if process.wait() != 0:
            raise ValueError("History inspection failed")
    emails = set(git("log", "--all", "--format=%ae%n%ce").decode().splitlines())
    personal = [
        e
        for e in emails
        if e
        and "noreply" not in e
        and e not in {"codex@openai.com", "codex@local"}
        and not e.endswith(("@local", "@localhost", ".invalid"))
    ]
    result = {
        "status": "failed" if findings else "passed_pattern_and_path_checks",
        "working_files": len([f for f in files if f]),
        "history_blobs": scanned,
        "findings": sorted(findings),
        "personal_author_email_present": bool(personal),
        "identity_review": "Personal author metadata was found in Git history. Review whether it is appropriate for sharing. Values are withheld; this check does not change history."
        if personal
        else "Only automated/noreply identities detected",
        "limits": "Pattern/path checks supplement manual review; they do not establish absence of all confidential or proprietary content.",
    }
    print(json.dumps(result, indent=2))
    if findings:
        raise SystemExit(1)
    return result


if __name__ == "__main__":
    main()
