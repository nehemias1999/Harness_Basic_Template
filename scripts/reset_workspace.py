"""Returns the workspace to the pristine template and starts another project.

Purpose
    One local copy of the harness, many projects, one after another. When a
    project is finished and pushed to its own repository, this makes the folder
    identical to the template again and instantiates the next project on top.

The rule, in three sentences
    Everything git tracked in the previous project is deleted. Everything in
    the template's tree is written in its place. Everything git ignored stays
    where it is, and is listed at the end so you can see what came across.

Where the template comes from
    The `template` remote, set at bootstrap time. It is read BEFORE anything is
    deleted, because the remote lives in `.git` and `.git` is one of the things
    this deletes. The pristine tree is cloned into a temporary folder outside
    the repository first: nothing here is touched until a verified copy of the
    template exists somewhere else.

    A side effect worth knowing: every new project starts on the *current*
    harness, not the one you cloned months ago.

Order of operations
    The order IS the safety design. Read, clone, verify, back up, inventory,
    and only then delete. A wrong URL or a network failure leaves the current
    project exactly as it was.

Usage
    python scripts/reset_workspace.py --name ecommerce --repo <url>
           [--description "..."] [--template-repo <url>] [--from <path>]
           [--force] [--clean-ignored] [--no-bundle] [--dry-run]

Exit codes
    0  reset (or simulated) · 1 it refused, and nothing was deleted
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import instantiate  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ok = instantiate.ok
warn = instantiate.warn
fail = instantiate.fail

# The switch that disarms the PreToolUse hook. It is ignored by git, but it is
# the one ignored file that must NOT travel: carrying it into the next project
# means starting with the harness's own protection turned off and nothing in
# `git status` to say so.
MAINTENANCE_MARK = ".harness-maintenance"


# Deleting .git on Windows needs the read-only dance; it lives next to the
# other instantiation logic so both scripts share one implementation.
rmtree = instantiate.rmtree


class Resetter:
    def __init__(self, root: str, args: argparse.Namespace) -> None:
        self.root = root
        self.args = args

    # -- git helpers ------------------------------------------------------
    def git(self, *arguments: str, cwd: str | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *arguments],
            cwd=cwd or self.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def has_git(self) -> bool:
        return os.path.isdir(os.path.join(self.root, ".git"))

    def remote_url(self, name: str, cwd: str | None = None) -> str:
        return self.git("remote", "get-url", name, cwd=cwd).stdout.strip()

    # -- 1. where does the pristine template come from --------------------
    def resolve_template(self) -> str | None:
        """The template's URL (a filesystem path counts), or None."""
        if self.args.source:
            if not os.path.isdir(self.args.source):
                fail(f"--from {self.args.source} is not a folder")
                return None
            return os.path.abspath(self.args.source)

        if self.args.template_repo:
            return self.args.template_repo

        if self.has_git():
            url = self.remote_url(instantiate.TEMPLATE)
            if url:
                return url
            # The folder may still be the template's own clone, never bootstrapped.
            origin = self.remote_url(instantiate.ORIGIN)
            if origin:
                warn(
                    f"git: there is no '{instantiate.TEMPLATE}' remote; using "
                    f"'{instantiate.ORIGIN}' ({origin}) as the template"
                )
                return origin

        fail(
            "I do not know where the template lives: this repository has no "
            f"'{instantiate.TEMPLATE}' remote."
        )
        print("        Say it once and it is remembered from then on:")
        print("")
        print("          --template-repo <harness-url>")
        print("          --from <path>                 a local copy, for working offline")
        return None

    # -- 2. preconditions --------------------------------------------------
    def preconditions(self, template_url: str) -> list[str]:
        """Reasons not to reset. `--force` skips these."""
        problems: list[str] = []
        if not self.has_git():
            return problems

        # Porcelain is "XY path": two status columns, then the path. The
        # maintenance mark is left out on purpose: it is a switch, never
        # committed, and `wipe` deletes it anyway — blocking a reset over it
        # would only teach the maintainer to reach for --force.
        dirty = [
            line[2:].strip()
            for line in self.git("status", "--porcelain").stdout.splitlines()
            if line.strip() and line[2:].strip() != MAINTENANCE_MARK
        ]
        if dirty:
            problems.append(
                f"{len(dirty)} file(s) with uncommitted changes "
                f"({', '.join(dirty[:3])})"
            )

        stashes = self.git("stash", "list").stdout.strip()
        if stashes:
            problems.append(
                f"{len(stashes.splitlines())} stash entry(ies) — stashes live in "
                f".git, and .git is one of the things this deletes"
            )

        has_commits = self.git("rev-parse", "HEAD").returncode == 0
        branch = self.git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        origin = self.remote_url(instantiate.ORIGIN)

        if has_commits and (not origin or origin == template_url):
            problems.append(
                "there is no 'origin' of its own, so nothing here can be shown "
                "to be pushed anywhere"
            )
        elif has_commits and origin:
            # Never let a network hiccup block a reset, and never let it claim
            # everything is pushed when it could not check.
            self.git("-c", "credential.helper=", "fetch", instantiate.ORIGIN, "--quiet")
            unpushed = self.git("rev-list", "--count", f"{instantiate.ORIGIN}/{branch}..HEAD")
            if unpushed.returncode != 0:
                problems.append(
                    f"could not compare against {origin} (is it reachable?), so "
                    f"there is no way to tell whether your commits are pushed"
                )
            elif unpushed.stdout.strip() not in ("", "0"):
                newest = self.git("log", "-1", "--pretty=%s").stdout.strip()
                problems.append(
                    f"{unpushed.stdout.strip()} commit(s) are not on {origin} "
                    f'(the newest: "{newest}")'
                )
        return problems

    # -- 3. the pristine tree ---------------------------------------------
    def materialise_template(self, url: str, workdir: str) -> tuple[str, str] | None:
        """Clones the template into a temp dir. Returns (path, default branch)."""
        target = os.path.join(workdir, "template")

        # A plain copy with no git at all still works: `git clone` would refuse
        # it, and refusing an offline copy of the template would be pedantic.
        # The test is `rev-parse`, not "is there a .git folder": a bare repo has
        # no .git subfolder and copying its internals would be nonsense.
        is_repo = os.path.isdir(url) and self.git("rev-parse", "--git-dir", cwd=url).returncode == 0
        if os.path.isdir(url) and not is_repo:
            shutil.copytree(url, target, ignore=shutil.ignore_patterns(".git"))
            return target, ""

        clone = self.git("clone", "--depth", "1", "--quiet", url, target, cwd=workdir)
        if clone.returncode != 0:
            fail(f"Could not read the template from {url}:")
            for line in (clone.stderr or "").strip().splitlines()[:3]:
                print(f"          {line}")
            return None

        # The clone checks out the remote's HEAD, so this is the default branch
        # with no main/master guessing anywhere.
        branch = self.git("rev-parse", "--abbrev-ref", "HEAD", cwd=target).stdout.strip() or "main"
        rmtree(os.path.join(target, ".git"))
        return target, branch

    def looks_like_the_harness(self, tree: str) -> bool:
        """The guard that stops a mistyped URL from emptying the folder."""
        try:
            with open(os.path.join(tree, "feature_list.json"), encoding="utf-8") as handle:
                project = json.load(handle).get("project", "")
        except (OSError, json.JSONDecodeError):
            return False
        if project != instantiate.PROJECT_PLACEHOLDER:
            return False
        return all(
            os.path.isfile(os.path.join(tree, f))
            for f in ("scripts/instantiate.py", "init.sh", "AGENTS.md")
        )

    # -- 4. the safety net -------------------------------------------------
    def backup_bundle(self) -> str | None:
        """One file holding every ref, including the stash. Cheap insurance."""
        if self.args.no_bundle or not self.has_git():
            return None
        if self.git("rev-parse", "HEAD").returncode != 0:
            return None

        # Capture the uncommitted tree too, without touching the working copy.
        wip = self.git("stash", "create").stdout.strip()
        if wip:
            self.git("update-ref", "refs/harness/pre-reset-wip", wip)

        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        name = f"{os.path.basename(self.root.rstrip(os.sep))}-pre-reset-{stamp}.bundle"
        path = os.path.abspath(os.path.join(self.root, "..", name))
        result = self.git("bundle", "create", path, "--all")
        if result.returncode != 0:
            warn("git: the backup bundle could not be written; carrying on")
            return None
        return path

    # -- 5. what gets deleted and what survives ---------------------------
    def inventory(self) -> tuple[list[str], list[str]]:
        """(what gets deleted, what survives because git ignores it).

        Run BEFORE restoring: the classification has to be made by the
        project's own .gitignore, not by the template's.
        """
        if not self.has_git():
            doomed = []
            for folder, dirs, names in os.walk(self.root):
                dirs[:] = [d for d in dirs if d != ".git"]
                for name in names:
                    rel = os.path.relpath(os.path.join(folder, name), self.root)
                    doomed.append(rel.replace("\\", "/"))
            warn(
                "this folder is not a git repository, so nothing can be told "
                "apart as ignored: everything except .git is deleted"
            )
            return sorted(doomed), []

        def listing(*flags: str) -> list[str]:
            return self.git("ls-files", *flags).stdout.split("\n")

        tracked = listing()
        untracked = listing("--others", "--exclude-standard")
        ignored = listing("--others", "--ignored", "--exclude-standard", "--directory")

        doomed = {p for p in tracked + untracked if p}
        kept = {p for p in ignored if p and p != MAINTENANCE_MARK}
        return sorted(doomed), sorted(kept)

    def wipe(self, doomed: list[str]) -> list[str]:
        """Deletes and returns whatever it could not delete."""
        stuck: list[str] = []
        for rel in doomed:
            path = os.path.join(self.root, rel.rstrip("/"))
            try:
                if os.path.isdir(path) and not os.path.islink(path):
                    rmtree(path)
                elif os.path.exists(path) or os.path.islink(path):
                    os.remove(path)
            except OSError as exc:
                stuck.append(f"{rel}: {exc}")

        mark = os.path.join(self.root, MAINTENANCE_MARK)
        if os.path.exists(mark):
            os.remove(mark)
            ok(f"{MAINTENANCE_MARK} -> deleted (it disarms the hook; it does not travel)")

        for folder, _dirs, _names in os.walk(self.root, topdown=False):
            if folder == self.root or ".git" in folder.replace("\\", "/").split("/"):
                continue
            if not os.listdir(folder):
                os.rmdir(folder)
        return stuck

    def restore(self, tree: str, kept: list[str]) -> None:
        collisions = [k for k in kept if os.path.exists(os.path.join(tree, k))]
        for rel in collisions:
            warn(f"collision: the template also ships {rel}; yours was overwritten")
        shutil.copytree(tree, self.root, dirs_exist_ok=True)

    # -- 6. orchestration --------------------------------------------------
    def run(self) -> int:
        template_url = self.resolve_template()
        if template_url is None:
            return 1

        # Never skipped, not even with --force: it would turn your next push
        # into a commit on the harness's repository.
        if self.args.repo and self.args.repo == template_url:
            fail(
                "--repo is the template's own URL. That would push the new "
                "project into the harness repository: use a different one."
            )
            return 1

        problems = self.preconditions(template_url)
        if problems and not self.args.force:
            fail("Resetting this workspace would destroy work that is nowhere else:")
            for problem in problems:
                print(f"          - {problem}")
            print("")
            print("        Reset makes this folder identical to the template again.")
            print("        Whatever only exists here stops existing.")
            print("")
            print("        Push what you want to keep, or insist:")
            print("")
            print(f'          --name "{self.args.name}" --force')
            print("")
            print("        And if you only wanted to see what it would delete: --dry-run.")
            return 1
        for problem in problems:
            warn(f"--force: {problem}")

        doomed, kept = self.inventory()
        if self.args.clean_ignored and kept:
            doomed = sorted(set(doomed) | set(kept))
            ok(f"--clean-ignored: the {len(kept)} ignored file(s) go too")
            kept = []

        with tempfile.TemporaryDirectory() as workdir:
            materialised = self.materialise_template(template_url, workdir)
            if materialised is None:
                warn("nothing was deleted: the workspace is exactly as it was")
                return 1
            tree, branch = materialised
            if not branch:
                branch = self.args.branch

            if not self.looks_like_the_harness(tree):
                fail(f"{template_url} does not carry the harness template.")
                print("        That is almost certainly the wrong URL. Nothing was deleted.")
                return 1
            ok(f"template read from {template_url} (branch {branch})")

            mode = " (dry run: nothing is written)" if self.args.dry_run else ""
            print(f"-- Resetting the workspace for '{self.args.name}'{mode} -----------")
            print(f"          {len(doomed)} file(s) of the current project are deleted")
            if self.args.repo:
                print(f"          origin   -> {self.args.repo}")
            print(f"          template -> {template_url}")

            if self.args.dry_run:
                print("          (the template really was cloned into a temporary folder —")
                print("           that is the only way this list can be true)")
                for rel in doomed[:15]:
                    print(f"            - {rel}")
                if len(doomed) > 15:
                    print(f"            … and {len(doomed) - 15} more")
                self.report_kept(kept)
                ok("simulated: the workspace was not touched")
                return 0

            bundle = self.backup_bundle()
            stuck = self.wipe(doomed)
            self.restore(tree, kept)
            ok("workspace restored to the pristine template")

            if self.has_git():
                rmtree(os.path.join(self.root, ".git"))
                ok("the previous project's history -> deleted")

        code = instantiate.Instantiator(self.root, self.instantiate_args(template_url, branch)).run()
        if code != 0:
            return code

        for line in stuck:
            warn(f"could not delete {line}")
        self.report_kept(kept)
        if bundle:
            print("")
            ok(f"Backup of the previous history: {bundle}")
            print(f"        Recover it with: git clone \"{bundle}\" recovered")
        return 0

    def instantiate_args(self, template_url: str, branch: str) -> argparse.Namespace:
        return argparse.Namespace(
            name=self.args.name,
            description=self.args.description,
            repo=self.args.repo,
            template_repo=template_url,
            branch=branch,
            force=True,          # the tree is pristine by now
            reset_git=False,     # already deleted above
            no_git=self.args.no_git,
            dry_run=False,
        )

    def report_kept(self, kept: list[str]) -> None:
        if not kept:
            return
        print("")
        print("-- Kept, because git ignores them ---------------------------")
        for rel in kept[:10]:
            print(f"  {rel}")
        if len(kept) > 10:
            print(f"  … and {len(kept) - 10} more")
        print(f"  These come from the previous project and are now inside "
              f"'{self.args.name}'.")
        print("  Delete whatever does not belong, or run again with --clean-ignored.")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Returns the workspace to the template and starts another project."
    )
    parser.add_argument("--name", required=True, help="Name of the new project")
    parser.add_argument("--description", default="", help="One line describing the project")
    parser.add_argument("--repo", default="", help="URL of the new project's repository")
    parser.add_argument("--template-repo", default="", help="URL of the harness repository")
    parser.add_argument(
        "--from",
        dest="source",
        default="",
        help="Local copy of the template to restore from (works offline)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reset even with uncommitted changes, unpushed commits or stashes",
    )
    parser.add_argument(
        "--clean-ignored",
        action="store_true",
        help="Also delete the files git ignores (.venv/, .env, …)",
    )
    parser.add_argument(
        "--no-bundle",
        action="store_true",
        help="Do not write the backup bundle of the previous history",
    )
    parser.add_argument("--no-git", action="store_true", help="Do not touch git at all")
    parser.add_argument(
        "--dry-run", action="store_true", help="List what it would do without doing it"
    )
    parser.add_argument(
        "--branch",
        default="main",
        help="Branch for the new history when it cannot be read from the template",
    )
    parser.add_argument("--root", default=REPO_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv[1:])

    if not args.name.strip():
        fail("--name cannot be empty")
        return 1
    if shutil.which("git") is None:
        fail("git is not installed: reset needs it to read the template and rebuild the repository.")
        return 1
    if args.force and args.no_bundle:
        warn(
            "--force together with --no-bundle: uncommitted work will be gone "
            "for good, with nothing to recover it from"
        )

    return Resetter(args.root, args).run()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
