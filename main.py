"""Script to collect user data from GitHub and GitLab APIs and generate a
summary."""

import os
import sys
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv


class GitHubCollector:
    """Collects user data from GitHub API."""

    def __init__(self, token: str, base_url: str):
        """Initialize GitHub collector with token and base URL."""
        self.token = token
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
        })

    def _make_request(
        self, url: str, endpoint: str
    ) -> Optional[Dict[str, Any]]:
        """
        Make a GET request to GitHub API.

        Args:
            url: Full URL to make request to
            endpoint: Endpoint name for error messages

        Returns:
            JSON response as dict or None on error
        """
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException:
            return None

    def get_profile(self) -> Optional[Dict[str, Any]]:
        """Get authenticated user profile."""
        url = f'{self.base_url}/user'
        return self._make_request(url, '/user')

    def get_repositories(self) -> Optional[List[Dict[str, Any]]]:
        """Get list of user repositories."""
        url = f'{self.base_url}/user/repos'
        return self._make_request(url, '/user/repos')

    def get_languages(
        self, languages_url: str, repo_name: str
    ) -> Optional[List[str]]:
        """
        Get languages for a repository.

        Args:
            languages_url: URL to fetch languages
            repo_name: Repository name for error messages

        Returns:
            List of language names or None on error
        """
        endpoint = f'/repos/{repo_name}/languages'
        data = self._make_request(languages_url, endpoint)
        if data is None:
            return None
        return list(data.keys())

    @staticmethod
    def count_filled_fields(
        profile: Optional[Dict[str, Any]]
    ) -> int:
        """
        Count how many of the 4 required fields are filled.

        Fields: login, name, bio, email
        """
        if not profile:
            return 0

        fields = ['login', 'name', 'bio', 'email']
        filled = 0
        for field in fields:
            value = profile.get(field)
            if value is not None and value != '':
                filled += 1
        return filled


class GitLabCollector:
    """Collects user data from GitLab API."""

    def __init__(self, token: str, base_url: str):
        """Initialize GitLab collector with token and base URL."""
        self.token = token
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'PRIVATE-TOKEN': token,
        })

    def _make_request(
        self, url: str, endpoint: str
    ) -> Optional[Dict[str, Any]]:
        """
        Make a GET request to GitLab API.

        Args:
            url: Full URL to make request to
            endpoint: Endpoint name for error messages

        Returns:
            JSON response as dict or None on error
        """
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException:
            return None

    def get_profile(self) -> Optional[Dict[str, Any]]:
        """Get authenticated user profile."""
        url = f'{self.base_url}/user'
        return self._make_request(url, '/user')

    @staticmethod
    def count_filled_fields(
        profile: Optional[Dict[str, Any]]
    ) -> int:
        """
        Count how many of the 4 required fields are filled.

        Fields: username, state, location, public_email
        """
        if not profile:
            return 0

        fields = ['username', 'state', 'location', 'public_email']
        filled = 0
        for field in fields:
            value = profile.get(field)
            if value is not None and value != '':
                filled += 1
        return filled


def process_github_data(
    github: GitHubCollector,
    errors: List[str]
) -> Dict[str, Any]:
    """
    Process GitHub data and return summary.

    Args:
        github: GitHubCollector instance
        errors: List to append errors to

    Returns:
        Dictionary with GitHub-related summary data
    """
    result = {
        'github_username': None,
        'total_repos': 0,
        'total_stars': 0,
        'total_forks': 0,
        'most_popular_repo': None,
        'languages': [],
        'github_profile_filled': 0,
    }

    # Get profile
    profile = github.get_profile()
    if profile:
        result['github_username'] = profile.get('login')
        result['github_profile_filled'] = github.count_filled_fields(profile)
    else:
        errors.append('github /user: не удалось загрузить профиль')

    # Get repositories
    repos = github.get_repositories()
    if repos is None:
        errors.append(
            'github /user/repos: не удалось загрузить репозитории'
        )
        return result

    if not repos:
        return result

    result['total_repos'] = len(repos)

    languages_set = set()
    most_stars = -1
    most_popular = None

    for repo in repos:
        name = repo.get('name', '')
        stars = repo.get('stargazers_count', 0)
        forks = repo.get('forks_count', 0)

        result['total_stars'] += stars
        result['total_forks'] += forks

        if stars > most_stars:
            most_stars = stars
            most_popular = name

        languages_url = repo.get('languages_url')
        if languages_url:
            repo_languages = github.get_languages(languages_url, name)
            if repo_languages is not None:
                languages_set.update(repo_languages)
            else:
                errors.append(
                    f'github /repos/{name}/languages: '
                    f'не удалось загрузить €зыки'
                )

    result['most_popular_repo'] = most_popular
    result['languages'] = sorted(languages_set)

    return result


def process_gitlab_data(
    gitlab: GitLabCollector,
    errors: List[str]
) -> Dict[str, Any]:
    """
    Process GitLab data and return summary.

    Args:
        gitlab: GitLabCollector instance
        errors: List to append errors to

    Returns:
        Dictionary with GitLab-related summary data
    """
    result = {
        'gitlab_username': None,
        'gitlab_profile_filled': 0,
    }

    profile = gitlab.get_profile()
    if profile:
        result['gitlab_username'] = profile.get('username')
        result['gitlab_profile_filled'] = gitlab.count_filled_fields(profile)
    else:
        errors.append('gitlab /user: не удалось загрузить профиль')

    return result


def load_config() -> Dict[str, str]:
    """
    Load configuration from .env file.

    Returns:
        Dictionary with configuration values

    Raises:
        SystemExit: If required environment variables are missing
    """
    load_dotenv()

    github_token = os.getenv('GITHUB_TOKEN')
    gitlab_token = os.getenv('GITLAB_TOKEN')
    github_api_url = os.getenv('GITHUB_API_URL')
    gitlab_api_url = os.getenv('GITLAB_API_URL')

    missing = []
    if not github_token:
        missing.append('GITHUB_TOKEN')
    if not gitlab_token:
        missing.append('GITLAB_TOKEN')
    if not github_api_url:
        missing.append('GITHUB_API_URL')
    if not gitlab_api_url:
        missing.append('GITLAB_API_URL')

    if missing:
        error_msg = (
            f"ќшибка: отсутствуют переменные окружени€: "
            f"{', '.join(missing)}"
        )
        print(error_msg)
        sys.exit(1)

    return {
        'github_token': github_token,
        'gitlab_token': gitlab_token,
        'github_api_url': github_api_url.rstrip('/'),
        'gitlab_api_url': gitlab_api_url.rstrip('/'),
    }


def main() -> None:
    """Main function to collect data and generate result.json."""
    config = load_config()

    errors: List[str] = []

    # Collect GitHub data
    github = GitHubCollector(
        token=config['github_token'],
        base_url=config['github_api_url']
    )
    github_data = process_github_data(github, errors)

    # Collect GitLab data
    gitlab = GitLabCollector(
        token=config['gitlab_token'],
        base_url=config['gitlab_api_url']
    )
    gitlab_data = process_gitlab_data(gitlab, errors)

    # Combine results
    result = {
        'github_username': github_data['github_username'],
        'gitlab_username': gitlab_data['gitlab_username'],
        'total_repos': github_data['total_repos'],
        'total_stars': github_data['total_stars'],
        'total_forks': github_data['total_forks'],
        'most_popular_repo': github_data['most_popular_repo'],
        'languages': github_data['languages'],
        'github_profile_filled': github_data['github_profile_filled'],
        'gitlab_profile_filled': gitlab_data['gitlab_profile_filled'],
        'errors': errors,
    }

    # Write to file
    import json
    with open('result.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("ƒанные успешно сохранены в result.json")


if __name__ == '__main__':
    main()
