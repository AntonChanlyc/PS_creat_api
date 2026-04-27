"""Flask service that builds a GitHub/GitLab activity resume."""

from datetime import datetime, timezone
import os
import sys
from threading import Lock
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from flask import Flask, jsonify
import requests


class GitHubCollector:
    """Collect data from GitHub REST API."""

    def __init__(self, token: str, base_url: str) -> None:
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )

    def _get_json(self, url: str) -> Optional[Any]:
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException:
            return None

    def get_profile(self) -> Optional[Dict[str, Any]]:
        return self._get_json(f"{self.base_url}/user")

    def get_repositories(self) -> Optional[List[Dict[str, Any]]]:
        data = self._get_json(f"{self.base_url}/user/repos")
        if isinstance(data, list):
            return data
        if data is None:
            return None
        return []

    def get_languages(self, languages_url: str) -> Optional[List[str]]:
        data = self._get_json(languages_url)
        if not isinstance(data, dict):
            return None
        return list(data.keys())

    @staticmethod
    def count_filled_fields(profile: Optional[Dict[str, Any]]) -> int:
        if not profile:
            return 0
        fields = ["login", "name", "bio", "email"]
        return sum(1 for field in fields if profile.get(field) not in (None, ""))


class GitLabCollector:
    """Collect data from GitLab REST API."""

    def __init__(self, token: str, base_url: str) -> None:
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({"PRIVATE-TOKEN": token})

    def get_profile(self) -> Optional[Dict[str, Any]]:
        try:
            response = self.session.get(f"{self.base_url}/user", timeout=30)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict):
                return data
            return None
        except requests.exceptions.RequestException:
            return None

    @staticmethod
    def count_filled_fields(profile: Optional[Dict[str, Any]]) -> int:
        if not profile:
            return 0
        fields = ["username", "state", "location", "public_email"]
        return sum(1 for field in fields if profile.get(field) not in (None, ""))


def utc_timestamp() -> str:
    """Return current UTC timestamp in YYYY-MM-DDTHH:MM:SSZ format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def process_github_data(github: GitHubCollector, errors: List[str]) -> Dict[str, Any]:
    """Collect and aggregate GitHub summary fields."""
    result: Dict[str, Any] = {
        "github_username": None,
        "total_repos": 0,
        "total_stars": 0,
        "total_forks": 0,
        "most_popular_repo": None,
        "languages": [],
        "github_profile_filled": 0,
    }

    profile = github.get_profile()
    if profile:
        result["github_username"] = profile.get("login")
        result["github_profile_filled"] = github.count_filled_fields(profile)
    else:
        errors.append("github /user: не удалось загрузить профиль")

    repos = github.get_repositories()
    if repos is None:
        errors.append("github /user/repos: не удалось загрузить репозитории")
        errors.append(
            "github /repos/languages: не удалось получить языки проекта"
        )
        return result

    if not repos:
        return result

    result["total_repos"] = len(repos)
    languages_set = set()
    max_stars = -1

    for repo in repos:
        stars = repo.get("stargazers_count", 0) or 0
        forks = repo.get("forks_count", 0) or 0
        name = repo.get("name")

        result["total_stars"] += stars
        result["total_forks"] += forks

        if stars > max_stars:
            max_stars = stars
            result["most_popular_repo"] = name

        languages_url = repo.get("languages_url")
        if not languages_url:
            continue

        repo_languages = github.get_languages(languages_url)
        if repo_languages is None:
            errors.append(
                "github /repos/languages: не удалось получить языки проекта"
            )
            continue
        languages_set.update(repo_languages)

    result["languages"] = sorted(languages_set)
    return result


def process_gitlab_data(gitlab: GitLabCollector, errors: List[str]) -> Dict[str, Any]:
    """Collect and aggregate GitLab summary fields."""
    result = {
        "gitlab_username": None,
        "gitlab_profile_filled": 0,
    }

    profile = gitlab.get_profile()
    if profile:
        result["gitlab_username"] = profile.get("username")
        result["gitlab_profile_filled"] = gitlab.count_filled_fields(profile)
    else:
        errors.append("gitlab /user: не удалось загрузить профиль")

    return result


def load_config() -> Dict[str, Any]:
    """Load required environment values from .env and process defaults."""
    load_dotenv()

    github_token = os.getenv("GITHUB_TOKEN")
    gitlab_token = os.getenv("GITLAB_TOKEN")
    github_api_url = os.getenv("GITHUB_API_URL")
    gitlab_api_url = os.getenv("GITLAB_API_URL")

    missing = []
    if not github_token:
        missing.append("GITHUB_TOKEN")
    if not gitlab_token:
        missing.append("GITLAB_TOKEN")
    if not github_api_url:
        missing.append("GITHUB_API_URL")
    if not gitlab_api_url:
        missing.append("GITLAB_API_URL")

    if missing:
        print(
            "Ошибка: не заданы обязательные переменные окружения: "
            + ", ".join(missing)
        )
        sys.exit(1)

    return {
        "github_token": github_token,
        "gitlab_token": gitlab_token,
        "github_api_url": github_api_url.rstrip("/"),
        "gitlab_api_url": gitlab_api_url.rstrip("/"),
        "host": os.getenv("HOST", "0.0.0.0"),
        "port": int(os.getenv("PORT", "8080")),
    }


def build_resume(config: Dict[str, Any]) -> Dict[str, Any]:
    """Build complete resume response object."""
    errors: List[str] = []

    github = GitHubCollector(config["github_token"], config["github_api_url"])
    gitlab = GitLabCollector(config["gitlab_token"], config["gitlab_api_url"])

    github_data = process_github_data(github, errors)
    gitlab_data = process_gitlab_data(gitlab, errors)

    return {
        "metadata": {"last_updated": utc_timestamp()},
        "github_username": github_data["github_username"],
        "gitlab_username": gitlab_data["gitlab_username"],
        "total_repos": github_data["total_repos"],
        "total_stars": github_data["total_stars"],
        "total_forks": github_data["total_forks"],
        "most_popular_repo": github_data["most_popular_repo"],
        "languages": github_data["languages"],
        "github_profile_filled": github_data["github_profile_filled"],
        "gitlab_profile_filled": gitlab_data["gitlab_profile_filled"],
        "errors": errors,
    }


def create_app(config: Dict[str, Any]) -> Flask:
    """Create Flask application with cached resume state."""
    app = Flask(__name__)
    state: Dict[str, Any] = {"resume": build_resume(config)}
    lock = Lock()

    @app.get("/api/resume")
    def get_resume() -> Any:
        with lock:
            return jsonify(state["resume"])

    @app.post("/api/resume/update")
    def update_resume() -> Any:
        new_resume = build_resume(config)
        with lock:
            state["resume"] = new_resume
            return jsonify(state["resume"])

    return app


def main() -> None:
    """Entrypoint: load env, prefetch data, run HTTP server."""
    config = load_config()
    app = create_app(config)
    app.run(host=config["host"], port=config["port"])


if __name__ == "__main__":
    main()
