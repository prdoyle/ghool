import requests

_GITHUB_API = "https://api.github.com"


class NetworkError(Exception):
    """Raised when the GitHub API call fails due to a network-level error."""


def list_repos(owner: str, token: str) -> tuple[int, list]:
    """GET /users/{owner}/repos?type=all&per_page=100.

    Returns (status_code, repos_list_or_empty). Used solely by `auth save` to
    validate that a token can access the expected owner's repositories.

    Raises NetworkError on connection failures or timeouts.
    """
    try:
        resp = requests.get(
            f"{_GITHUB_API}/users/{owner}/repos",
            params={"type": "all", "per_page": 100},
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=10,
        )
    except requests.RequestException as exc:
        raise NetworkError(str(exc)) from exc

    try:
        body = resp.json()
        if not isinstance(body, list):
            body = []
    except ValueError:
        body = []

    return resp.status_code, body
