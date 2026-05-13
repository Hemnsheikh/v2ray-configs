"""
github_uploader.py – push files to a GitHub repository via the REST API.
No local git required; uses PyGitHub.
"""

import logging
from pathlib import Path

from github import Github, GithubException

log = logging.getLogger(__name__)


class GitHubUploader:
    def __init__(self, token: str, repo_name: str):
        """
        :param token:     GitHub personal access token (needs repo scope).
        :param repo_name: "owner/repo-name"
        """
        self._gh   = Github(token)
        self._repo = self._gh.get_repo(repo_name)
        log.info("Connected to GitHub repo: %s", repo_name)

    # ──────────────────────────────────────────────────────────────────────────

    def upload_file(
        self,
        local_path: Path,
        repo_path: str,
        commit_message: str,
        branch: str = "main",
    ) -> None:
        """
        Create or update *repo_path* in the repository with the contents of
        *local_path*.  The branch is created if it doesn't exist.
        """
        content = Path(local_path).read_bytes()

        try:
            existing = self._repo.get_contents(repo_path, ref=branch)
            # File exists – update it
            self._repo.update_file(
                path=repo_path,
                message=commit_message,
                content=content,
                sha=existing.sha,
                branch=branch,
            )
            log.info("Updated  %s on branch '%s'", repo_path, branch)
        except GithubException as exc:
            if exc.status == 404:
                # File doesn't exist yet – create it
                self._repo.create_file(
                    path=repo_path,
                    message=commit_message,
                    content=content,
                    branch=branch,
                )
                log.info("Created  %s on branch '%s'", repo_path, branch)
            else:
                log.error("GitHub API error for %s: %s", repo_path, exc)
                raise

    def ensure_branch(self, branch: str, source: str = "main") -> None:
        """Create *branch* from *source* if it does not exist."""
        try:
            self._repo.get_branch(branch)
        except GithubException:
            ref = self._repo.get_git_ref(f"heads/{source}")
            self._repo.create_git_ref(f"refs/heads/{branch}", ref.object.sha)
            log.info("Created branch '%s' from '%s'", branch, source)
