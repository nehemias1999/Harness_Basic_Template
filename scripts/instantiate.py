"""Instantiates a new project from the harness template.

Purpose
    Fill in the placeholders, empty the inherited scope and leave the repository
    in a "project just started" state. A human runs it ONCE, right after copying
    or cloning the template.

Why it is in Python and not in each shell
    `bootstrap.ps1` and `bootstrap.sh` are two doors into the same house. The
    logic lives here for the same reason the validators' does: these are ~200
    lines of decisions about what to delete and what to keep, and keeping them
    duplicated in PowerShell and bash guarantees that one day they will say
    different things. The wrappers only translate arguments.

What it does
    1. Refuses if the repository is already an instantiated project (unless --force).
    2. `feature_list.json`: writes project/description and empties `features`.
    3. Replaces `<YOUR_PROJECT>` and `<PROJECT_DESCRIPTION>` in README.md and in
       docs/{architecture,conventions,verification}.md.
    4. Resets `progress/current.md` and `progress/history.md` to their template.
    5. Deletes leftover reports and the previous project's requirements.
    6. Leaves the git repository ready and disconnects the template's `origin`.

What it does NOT do
    Define the scope. The draft of `docs/architecture.md` and the requirements
    are written by the `analyst` agent (`/requirements`), but approving them is
    yours, and until you do the verifier does not go green.

Usage
    python scripts/instantiate.py --name my-project [--description "What it does."]
                                  [--force] [--reset-git] [--no-git] [--dry-run]

Exit codes
    0  instantiated · 1 template files are missing, or it was already a project
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PROJECT_PLACEHOLDER = "<YOUR_PROJECT>"
DESCRIPTION_PLACEHOLDER = "<PROJECT_DESCRIPTION>"

REQUIRED = ("feature_list.json", "README.md", "progress/current.md", "progress/history.md")

# An explicit list on purpose: `docs/scripts.md` and `CHECKPOINTS.md` *talk
# about* the placeholders, so replacing them there would wreck their own
# documentation.
WITH_PLACEHOLDERS = (
    "README.md",
    "docs/architecture.md",
    "docs/conventions.md",
    "docs/verification.md",
)

REPORT_RE = re.compile(r"^(explore|impl|review|intake)_.*\.md$")
SPEC_RE = re.compile(r"^REQ-\d{3}_.*\.md$")

# The two remotes the workspace ends up with. `origin` is the project's own
# repository and `template` is the harness's. Knowing which is which used to be
# a guess — "does the URL contain Harness_Basic_Template?" — which missed a fork
# under another name and disconnected a project legitimately called that. Now it
# is a fact: whatever `origin` was when you cloned to get here IS the template.
ORIGIN = "origin"
TEMPLATE = "template"

CURRENT_TEMPLATE = """# Current session

> This file is emptied when each session closes and moved into `history.md`.
> While you work, **keep it up to date in real time**, not at the end.

- **Feature in progress:** _none_
- **Started:** _—_
- **Agent:** _—_

## Plan

_Describe in 3-5 bullets what you are going to do before touching any code._

## Log

_Note every significant step here: files created, decisions, blockers._

- ...

## Next step

_If the session is interrupted, the first thing the next one should do._
"""

HISTORY_TEMPLATE = """# Session history

> **Append-only** log. When each session closes, the summary that lived in
> `progress/current.md` is added at the end. A previous entry is never edited
> or deleted: this file is the project's memory between context windows.

Format of each entry:

```markdown
## <YYYY-MM-DD> — feature <id> <name>

- **Agent:** <who worked on it>
- **Result:** done | blocked
- **Files touched:** <list>
- **Verification:** <summarised init output>
- **Notes:** <decisions or blockers relevant to the next session>
```

---

_No sessions recorded yet._
"""


def _force_remove(func, path, _info) -> None:
    """Deleting .git fails on Windows: git's objects are read-only."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def rmtree(path: str) -> None:
    """shutil.rmtree that survives read-only files, on every Python >= 3.9."""
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_force_remove)
    else:
        shutil.rmtree(path, onerror=_force_remove)


def ok(message: str) -> None:
    print(f"[OK]    {message}")


def warn(message: str) -> None:
    print(f"[WARN]  {message}")


def fail(message: str) -> None:
    print(f"[FAIL]  {message}")


class Instantiator:
    def __init__(self, root: str, args: argparse.Namespace) -> None:
        self.root = root
        self.args = args

    # -- helpers ---------------------------------------------------------
    def path(self, *parts: str) -> str:
        return os.path.join(self.root, *parts)

    def read(self, rel: str) -> str:
        with open(self.path(rel), encoding="utf-8") as handle:
            return handle.read()

    def write(self, rel: str, content: str) -> None:
        if self.args.dry_run:
            return
        with open(self.path(rel), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)

    def delete(self, rel: str) -> None:
        if self.args.dry_run:
            return
        os.remove(self.path(rel))

    def announce(self, message: str) -> None:
        ok(f"{message}{' (simulated)' if self.args.dry_run else ''}")

    # -- steps -----------------------------------------------------------
    def check_template(self) -> bool:
        missing = [f for f in REQUIRED if not os.path.isfile(self.path(f))]
        for name in missing:
            fail(f"A template file is missing: {name}")
        return not missing

    def already_a_project(self) -> list[str]:
        """Reasons why this does not look like the freshly copied template."""
        reasons: list[str] = []
        try:
            project = str(json.loads(self.read("feature_list.json")).get("project", "")).strip()
        except (OSError, json.JSONDecodeError):
            project = ""
        if project and project != PROJECT_PLACEHOLDER:
            reasons.append(f"feature_list.json already belongs to project '{project}'")

        specs = self.inherited_requirements()
        if specs:
            reasons.append(f"there are {len(specs)} requirement(s) in specs/")
        return reasons

    def inherited_requirements(self) -> list[str]:
        spec_dir = self.path("specs")
        if not os.path.isdir(spec_dir):
            return []
        return sorted(f for f in os.listdir(spec_dir) if SPEC_RE.match(f))

    def rewrite_feature_list(self) -> None:
        data = json.loads(self.read("feature_list.json"))
        data["project"] = self.args.name
        if self.args.description:
            data["description"] = self.args.description
        data["features"] = []
        self.write(
            "feature_list.json",
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        )
        self.announce(f"feature_list.json -> project '{self.args.name}', 0 features")

    def replace_placeholders(self) -> None:
        for rel in WITH_PLACEHOLDERS:
            if not os.path.isfile(self.path(rel)):
                continue
            content = self.read(rel)
            updated = content.replace(PROJECT_PLACEHOLDER, self.args.name)
            if self.args.description:
                updated = updated.replace(DESCRIPTION_PLACEHOLDER, self.args.description)
            if updated == content:
                continue
            self.write(rel, updated)
            self.announce(f"{rel} -> placeholders replaced")

    def reset_progress(self) -> None:
        history = self.read("progress/history.md")
        has_entries = "## " in history.split("---", 2)[-1]
        if has_entries and not self.args.force:
            warn(
                "progress/history.md has entries from previous sessions. "
                "Use --force to reset it."
            )
        else:
            self.write("progress/history.md", HISTORY_TEMPLATE)
            self.announce("progress/history.md -> reset")

        self.write("progress/current.md", CURRENT_TEMPLATE)
        self.announce("progress/current.md -> reset")

    def clean_reports(self) -> None:
        progress = self.path("progress")
        if not os.path.isdir(progress):
            return
        for name in sorted(os.listdir(progress)):
            if REPORT_RE.match(name):
                self.delete(os.path.join("progress", name))
                self.announce(f"progress/{name} -> deleted")

    def prepare_specs(self) -> None:
        spec_dir = self.path("specs")
        if not os.path.isdir(spec_dir):
            if not self.args.dry_run:
                os.makedirs(spec_dir)
            self.announce("specs/ -> created")

        # The requirements belong to the previous project. If they stay, the
        # step above empties `features` and we are left with approved specs no
        # feature references: the verifier is born red.
        for name in self.inherited_requirements():
            self.delete(os.path.join("specs", name))
            self.announce(f"specs/{name} -> deleted")

    # -- git -------------------------------------------------------------
    def git(self, *arguments: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *arguments],
            cwd=self.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def remote_url(self, name: str) -> str:
        return self.git("remote", "get-url", name).stdout.strip()

    def set_remote(self, name: str, url: str) -> None:
        if self.remote_url(name):
            self.git("remote", "set-url", name, url)
        else:
            self.git("remote", "add", name, url)

    def base_commit(self, branch: str = "") -> None:
        # The branch name comes from the template — the branch that was checked
        # out before the history was replaced — so main/master is never left to
        # whatever `init.defaultBranch` happens to say on this machine.
        # `git init -b` needs git >= 2.28; the fallback covers older ones.
        branch = branch or getattr(self.args, "branch", "")
        if branch and self.git("init", "--quiet", "-b", branch).returncode != 0:
            self.git("init", "--quiet")
            self.git("symbolic-ref", "HEAD", f"refs/heads/{branch}")
        elif not branch:
            self.git("init", "--quiet")
        self.git("add", "-A")
        if not self.git("config", "user.email").stdout.strip():
            self.git("config", "user.email", "harness@localhost")
            self.git("config", "user.name", "Harness bootstrap")
            warn("git: no identity was configured, a provisional local one was set")
        commit = self.git(
            "commit", "--quiet", "-m", f"chore: instantiate the harness for {self.args.name}"
        )
        if commit.returncode == 0:
            ok("git: repository initialised with the harness base commit")
        else:
            warn("git: the base commit failed; make it by hand before working")

    def derive_template_url(self) -> str:
        """Where the harness lives: the flag, or whatever `origin` is today.

        Nobody should have to type --template-repo: you cloned the harness to
        get here, so `origin` already holds its URL. It has to be read before
        anything can destroy it, which is why this is a method of its own —
        `run()` calls it before touching a single file, and `configure_git()`
        calls it again once it knows `.git` is still there.
        """
        flag = getattr(self.args, "template_repo", "")
        if flag:
            return flag
        if not os.path.isdir(self.path(".git")):
            return ""
        # A `template` remote means this folder has been through bootstrap
        # before: `origin` is the project's, and the harness is already named.
        return self.remote_url(TEMPLATE) or self.remote_url(ORIGIN)

    def configure_git(self) -> str | None:
        """Leaves the two remotes in place. Returns a closing note, if needed.

        Two reasons to touch git here. The reviewer identifies the files touched
        in a session by comparing against history — with no repo it works blind.
        And if you cloned the template, `origin` still points at it, so your
        first push would send the new project to the harness's repository.

        The workspace ends up with `origin` = your project and `template` = the
        harness. The second one is what lets you reset this folder later and use
        it for the next project.
        """
        if self.args.no_git:
            warn("git: skipped by --no-git (the reviewer compares against history)")
            return None
        if shutil.which("git") is None:
            warn("git is not installed: the reviewer will not be able to compare against history")
            return None
        if self.args.dry_run:
            ok("git: no changes (simulated)")
            return None

        has_git = os.path.isdir(self.path(".git"))

        # Read from .git everything that will be needed after .git is gone.
        branch = ""
        if has_git:
            branch = self.git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
            if branch == "HEAD":  # detached
                branch = ""

        template_url = self.derive_template_url()

        if has_git and self.args.reset_git:
            rmtree(self.path(".git"))
            ok(".git inherited from the template -> deleted")
            has_git = False

        if not has_git:
            self.base_commit(branch)

        if template_url:
            self.set_remote(TEMPLATE, template_url)
            ok(f"git: remote '{TEMPLATE}' -> {template_url} (the harness)")
        else:
            warn(
                f"git: no '{TEMPLATE}' remote could be worked out. Without it you "
                f"cannot reset this folder later: add it with "
                f"--template-repo <url>"
            )

        # `run()` already refused --repo == the template, before writing a
        # single file.
        repo = getattr(self.args, "repo", "")
        if repo:
            self.set_remote(ORIGIN, repo)
            ok(f"git: remote '{ORIGIN}' -> {repo} (your project)")
            return None

        if self.remote_url(ORIGIN) and self.remote_url(ORIGIN) == template_url:
            self.git("remote", "remove", ORIGIN)
            warn(f"git: '{ORIGIN}' still pointed at the template, so it was disconnected")

        return "Add your project's remote: git remote add origin <url>"

    # -- orchestration -----------------------------------------------------
    def run(self) -> int:
        if not self.check_template():
            return 1

        # Before anything is rewritten: pointing the project at the harness's
        # own repository is not something to discover after the tree has been
        # instantiated and the first push is on its way.
        repo = getattr(self.args, "repo", "")
        if repo and repo == self.derive_template_url():
            fail(
                "--repo is the template's own URL. That would push your "
                "project into the harness repository: use a different one."
            )
            return 1

        reasons = self.already_a_project()
        if reasons and not self.args.force:
            fail("This repository is already an instantiated project:")
            for reason in reasons:
                print(f"          - {reason}")
            print("")
            print("        Instantiating empties the features, deletes the requirements in")
            print("        specs/ and resets progress/. On a live project that is not recoverable.")
            print("")
            print("        If you really want to instantiate it again, say so explicitly:")
            print("")
            print(f'          --name "{self.args.name}" --force')
            print("")
            print("        And if you only wanted to see what it would do: add --dry-run.")
            return 1

        mode = " (dry run: nothing is written)" if self.args.dry_run else ""
        print(f"-- Instantiating project '{self.args.name}'{mode} ----------------------")

        self.rewrite_feature_list()
        self.replace_placeholders()
        self.reset_progress()
        self.clean_reports()
        self.prepare_specs()
        note = self.configure_git()

        print("")
        print("-- Next step (by hand) --------------------------------")
        print("  1. Open Claude Code at the root and hand it your requirements in plain")
        print("     language (or use /requirements). The analyst leaves them in specs/ and")
        print("     drafts docs/architecture.md.")
        print("  2. Read them and ask for whatever changes you want: each pass is a round.")
        print("  3. When you are happy: /approve 1 2, or /approve-all. That is when the")
        print("     features move to pending and the architecture gets approved.")
        print("  4. Run the verifier — it should come out green.")
        print("  5. /next-feature to start development.")
        if note:
            print(f"  6. {note}")
        print("")
        ok(f"Project '{self.args.name}' instantiated{mode}")
        return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Instantiates a new project from the harness template."
    )
    parser.add_argument("--name", required=True, help="Name of the new project")
    parser.add_argument("--description", default="", help="One line describing the project")
    parser.add_argument(
        "--repo",
        default="",
        help="URL of the project's OWN repository; it becomes `origin`",
    )
    parser.add_argument(
        "--template-repo",
        default="",
        help="URL of the harness repository; it becomes the `template` remote "
             "(by default, whatever `origin` points at right now)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Instantiate even if the repository is already a project, and reset history.md",
    )
    parser.add_argument(
        "--reset-git",
        action="store_true",
        help="Delete the .git inherited from the template and start a new history",
    )
    parser.add_argument("--no-git", action="store_true", help="Do not touch git at all")
    parser.add_argument(
        "--dry-run", action="store_true", help="List the changes without applying them"
    )
    parser.add_argument("--root", default=REPO_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv[1:])

    if not args.name.strip():
        fail("--name cannot be empty")
        return 1

    return Instantiator(args.root, args).run()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
