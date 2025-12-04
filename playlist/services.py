import os
from typing import Optional, Tuple, List

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .models import Movie


class TMDBError(Exception):
    pass


def _get_tmdb_config():
    api_key = getattr(settings, "TMDB_API_KEY", None) or os.environ.get("TMDB_API_KEY")
    base = getattr(settings, "TMDB_BASE_URL", None) or os.environ.get("TMDB_BASE_URL")
    image_base = getattr(settings, "TMDB_IMAGE_BASE", None) or os.environ.get("TMDB_IMAGE_BASE")
    if not api_key:
        raise ImproperlyConfigured("TMDB_API_KEY is not configured in settings or environment")
    if not base:
        base = "https://api.themoviedb.org/3"
    if not image_base:
        image_base = "https://image.tmdb.org/t/p/w500"
    return api_key, base.rstrip("/"), image_base.rstrip("/")


def search_tmdb(query: str, page: int = 1, media_type: str = "multi") -> dict:
    """Search TMDB for movies and/or TV shows.

    media_type options:
      - "movie": search movies only
      - "tv": search TV series only
      - "multi" (default): search both and filter out people results
    """
    api_key, base, _ = _get_tmdb_config()

    normalized_type = (media_type or "multi").lower()
    if normalized_type not in {"movie", "tv", "multi"}:
        normalized_type = "multi"

    endpoint = {
        "movie": "search/movie",
        "tv": "search/tv",
        "multi": "search/multi",
    }[normalized_type]

    url = f"{base}/{endpoint}"
    params = {"api_key": api_key, "query": query, "page": page}
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    results = data.get("results", [])
    if normalized_type == "multi":
        results = [
            {**item, "media_type": item.get("media_type", "movie")}
            for item in results
            if item.get("media_type") in {"movie", "tv"}
        ]
    else:
        for item in results:
            item.setdefault("media_type", normalized_type)

    data["results"] = results
    data["selected_media_type"] = normalized_type
    return data


def get_tmdb_movie_details(tmdb_id: int) -> dict:
    """Fetch TMDB movie details (including videos)."""
    api_key, base, _ = _get_tmdb_config()
    url = f"{base}/movie/{tmdb_id}"
    params = {"api_key": api_key, "append_to_response": "videos"}
    resp = requests.get(url, params=params, timeout=10)
    if resp.status_code == 404:
        raise TMDBError(f"Movie {tmdb_id} not found")
    resp.raise_for_status()
    return resp.json()


def get_tmdb_tv_details(tmdb_id: int) -> dict:
    """Fetch TMDB TV show details (including videos)."""
    api_key, base, _ = _get_tmdb_config()
    url = f"{base}/tv/{tmdb_id}"
    params = {"api_key": api_key, "append_to_response": "videos"}
    resp = requests.get(url, params=params, timeout=10)
    if resp.status_code == 404:
        raise TMDBError(f"TV show {tmdb_id} not found")
    resp.raise_for_status()
    return resp.json()


def get_tmdb_tv_season_details(tmdb_id: int, season_number: int) -> dict:
    """Fetch TMDB TV season details including episodes."""
    api_key, base, _ = _get_tmdb_config()
    url = f"{base}/tv/{tmdb_id}/season/{season_number}"
    params = {"api_key": api_key}
    resp = requests.get(url, params=params, timeout=10)
    if resp.status_code == 404:
        raise TMDBError(f"Season {season_number} for TV show {tmdb_id} not found")
    resp.raise_for_status()
    return resp.json()


def get_tmdb_popular(media_type: str = "movie", page: int = 1) -> dict:
    """Fetch popular movies or TV shows from TMDB."""
    api_key, base, _ = _get_tmdb_config()
    normalized_type = (media_type or "movie").lower()
    if normalized_type not in {"movie", "tv"}:
        normalized_type = "movie"

    endpoint = "movie/popular" if normalized_type == "movie" else "tv/popular"
    url = f"{base}/{endpoint}"
    params = {"api_key": api_key, "page": page}
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    for item in data.get("results", []):
        item.setdefault("media_type", normalized_type)
    data["selected_media_type"] = normalized_type
    return data


def get_tmdb_top_rated(media_type: str = "movie", page: int = 1) -> dict:
    """Fetch top-rated movies or TV shows from TMDB."""
    api_key, base, _ = _get_tmdb_config()
    normalized_type = (media_type or "movie").lower()
    if normalized_type not in {"movie", "tv"}:
        normalized_type = "movie"

    endpoint = "movie/top_rated" if normalized_type == "movie" else "tv/top_rated"
    url = f"{base}/{endpoint}"
    params = {"api_key": api_key, "page": page}
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    for item in data.get("results", []):
        item.setdefault("media_type", normalized_type)
    data["selected_media_type"] = normalized_type
    return data


def get_or_create_movie_from_tmdb(tmdb_id: int, media_type: str = Movie.MediaType.MOVIE) -> Tuple[Movie, bool]:
    """Get or create a local Movie/TV show by TMDB id and media type."""

    normalized_type = media_type or Movie.MediaType.MOVIE
    if normalized_type not in Movie.MediaType.values:
        normalized_type = Movie.MediaType.MOVIE

    try:
        movie = Movie.objects.get(tmdb_id=tmdb_id, media_type=normalized_type)
        return movie, False
    except Movie.DoesNotExist:
        pass

    if normalized_type == Movie.MediaType.TV:
        data = get_tmdb_tv_details(tmdb_id)
        title = data.get("name") or data.get("original_name") or ""
        release_date = data.get("first_air_date") or ""
    else:
        data = get_tmdb_movie_details(tmdb_id)
        title = data.get("title") or data.get("original_title") or ""
        release_date = data.get("release_date") or ""

    # Extract youtube_id from videos
    youtube_id = None
    videos = data.get("videos", {}).get("results", [])
    for v in videos:
        if v.get("site", "").lower() == "youtube" and v.get("key"):
            youtube_id = v.get("key")
            break

    # Build poster URL
    poster_path = data.get("poster_path")
    poster_url = None
    if poster_path:
        _, _, image_base = _get_tmdb_config()
        poster_url = f"{image_base}{poster_path}"

    # Parse release_year from release_date (e.g., "2010-07-15" -> 2010)
    release_year = None
    if release_date:
        try:
            release_year = int(release_date.split("-")[0])
        except (ValueError, IndexError):
            release_year = None

    # Create the movie
    movie = Movie.objects.create(
        tmdb_id=tmdb_id,
        title=title,
        poster_url=poster_url,
        description=data.get("overview") or "",
        release_year=release_year,
        media_type=normalized_type,
        youtube_id=youtube_id,
    )

    return movie, True
