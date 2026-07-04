#!/usr/bin/env python3

import argparse
import copy
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = Path('/Users/spencer/projects/pirate-orb')
RADARR_CONFIG = ROOT / 'radarr/config/config.xml'
SLSKD_API_KEY = 'pirate-orb-slskd-api-key-2026'
RADARR_BASE = 'http://localhost:7878/api/v3'
SLSKD_BASE = 'http://localhost:5030/api/v0'
SOULSEEK_COMPLETE_ROOT = Path('/Volumes/Raiju/downloads/complete/soulseek')
VIDEO_EXTENSIONS = {'.mkv', '.mp4', '.avi', '.m4v', '.mov', '.wmv', '.mpg', '.mpeg', '.iso'}
SUBTITLE_EXTENSIONS = {'.srt', '.ass', '.ssa', '.sub', '.idx'}
JUNK_NAME_TOKENS = {'sample', 'trailer', 'extras', 'featurette'}
DEFAULT_TORRENT_DELAY_MINUTES = 60
PROFILE_NAMES = {
    'normal': 'Custom - Normal',
    'cinematic': 'Custom - Cinematic',
    'rare': 'Custom - Rare',
}

PROFILE_RULES = {
    'normal': {
        'name': PROFILE_NAMES['normal'],
        'cutoff': 7,  # Bluray-1080p
        'upgradeAllowed': True,
        'allowed': {
            'DVD',
            'WEBDL-480p', 'WEBRip-480p', 'Bluray-480p', 'Bluray-576p',
            'HDTV-720p', 'WEBDL-720p', 'WEBRip-720p', 'Bluray-720p',
            'HDTV-1080p', 'WEBDL-1080p', 'WEBRip-1080p', 'Bluray-1080p', 'Remux-1080p',
        },
    },
    'cinematic': {
        'name': PROFILE_NAMES['cinematic'],
        'cutoff': 19,  # Bluray-2160p
        'upgradeAllowed': True,
        'allowed': {
            'HDTV-720p', 'WEBDL-720p', 'WEBRip-720p', 'Bluray-720p',
            'HDTV-1080p', 'WEBDL-1080p', 'WEBRip-1080p', 'Bluray-1080p', 'Remux-1080p', 'BR-DISK',
            'HDTV-2160p', 'WEBDL-2160p', 'WEBRip-2160p', 'Bluray-2160p', 'Remux-2160p',
        },
    },
    'rare': {
        'name': PROFILE_NAMES['rare'],
        'cutoff': 7,  # stop upgrading once solid 1080p exists, but accept lower now
        'upgradeAllowed': True,
        'allowed': {
            'SDTV', 'DVD', 'DVD-R', 'REGIONAL',
            'WEBDL-480p', 'WEBRip-480p', 'Bluray-480p', 'Bluray-576p',
            'HDTV-720p', 'WEBDL-720p', 'WEBRip-720p', 'Bluray-720p',
            'HDTV-1080p', 'WEBDL-1080p', 'WEBRip-1080p', 'Bluray-1080p', 'Remux-1080p',
        },
    },
}

POLICIES = {
    'normal': {
        'release_buckets': ['1080', '720', '576', '480', 'sd', 'unknown'],
        'source_order': ['usenet', 'torrent', 'soulseek'],
    },
    'cinematic': {
        'release_buckets': ['2160', '1080', '720', '576', '480', 'sd', 'unknown'],
        'source_order': ['usenet', 'torrent', 'soulseek'],
    },
    'rare': {
        'release_buckets': ['1080', '720', '576', '480', 'sd', 'unknown'],
        'source_order': ['usenet', 'torrent', 'soulseek'],
    },
}


def load_radarr_api_key() -> str:
    root = ET.parse(RADARR_CONFIG).getroot()
    api_key = root.findtext('ApiKey')
    if not api_key:
        raise RuntimeError(f'Could not read Radarr API key from {RADARR_CONFIG}')
    return api_key


def request_json(method: str, url: str, headers: Optional[Dict[str, str]] = None, data: Any = None, timeout: int = 60) -> Any:
    payload = None
    request_headers = dict(headers or {})
    if data is not None:
        payload = json.dumps(data).encode()
        request_headers.setdefault('Content-Type', 'application/json')
    req = urllib.request.Request(url, data=payload, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read()
            if not body:
                return None
            content_type = response.headers.get('Content-Type', '')
            if 'application/json' in content_type or body[:1] in (b'{', b'['):
                return json.loads(body.decode())
            return body.decode()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors='replace')
        raise RuntimeError(f'{method} {url} failed with HTTP {exc.code}: {detail}') from exc


def radarr_request(method: str, path: str, data: Any = None) -> Any:
    return request_json(method, f'{RADARR_BASE}{path}', headers={'X-Api-Key': load_radarr_api_key()}, data=data)


def slskd_request(method: str, path: str, data: Any = None) -> Any:
    return request_json(method, f'{SLSKD_BASE}{path}', headers={'X-API-Key': SLSKD_API_KEY}, data=data)


def _set_profile_items(items: List[Dict[str, Any]], allowed_names: set[str]) -> bool:
    any_allowed = False
    for item in items:
        if item.get('items'):
            child_allowed = _set_profile_items(item['items'], allowed_names)
            item['allowed'] = child_allowed
            any_allowed = any_allowed or child_allowed
        else:
            quality = item.get('quality', {})
            quality_name = quality.get('name')
            allowed = quality_name in allowed_names
            item['allowed'] = allowed
            any_allowed = any_allowed or allowed
    return any_allowed


def build_profile_payload(template: Dict[str, Any], profile_key: str, existing_id: Optional[int] = None) -> Dict[str, Any]:
    rule = PROFILE_RULES[profile_key]
    profile = copy.deepcopy(template)
    profile['name'] = rule['name']
    profile['upgradeAllowed'] = rule['upgradeAllowed']
    profile['cutoff'] = rule['cutoff']
    profile['items'] = copy.deepcopy(template['items'])
    _set_profile_items(profile['items'], set(rule['allowed']))
    if existing_id is None:
        profile.pop('id', None)
    else:
        profile['id'] = existing_id
    return profile


def ensure_profiles() -> Dict[str, int]:
    profiles = radarr_request('GET', '/qualityprofile')
    by_name = {profile['name']: profile for profile in profiles}
    template = by_name.get('Any')
    if not template:
        raise RuntimeError('Could not find Radarr quality profile template named Any')

    resolved: Dict[str, int] = {}
    for key in ('normal', 'cinematic', 'rare'):
        name = PROFILE_RULES[key]['name']
        existing = by_name.get(name)
        payload = build_profile_payload(template, key, existing_id=existing['id'] if existing else None)
        if existing:
            updated = radarr_request('PUT', f"/qualityprofile/{existing['id']}", payload)
            resolved[key] = updated['id']
            print(f'Updated quality profile: {name} (id={updated["id"]})')
        else:
            created = radarr_request('POST', '/qualityprofile', payload)
            resolved[key] = created['id']
            print(f'Created quality profile: {name} (id={created["id"]})')
    return resolved


def ensure_delay_profile(torrent_delay_minutes: int = DEFAULT_TORRENT_DELAY_MINUTES) -> int:
    profiles = radarr_request('GET', '/delayprofile')
    default = None
    for profile in profiles:
        if not profile.get('tags'):
            default = profile
            break
    if default is None:
        default = {
            'enableUsenet': True,
            'enableTorrent': True,
            'preferredProtocol': 'usenet',
            'usenetDelay': 0,
            'torrentDelay': torrent_delay_minutes,
            'bypassIfHighestQuality': False,
            'bypassIfAboveCustomFormatScore': False,
            'minimumCustomFormatScore': 0,
            'order': 2147483647,
            'tags': [],
        }
        created = radarr_request('POST', '/delayprofile', default)
        print(f'Created default delay profile (id={created["id"]})')
        return created['id']

    default['enableUsenet'] = True
    default['enableTorrent'] = True
    default['preferredProtocol'] = 'usenet'
    default['usenetDelay'] = 0
    default['torrentDelay'] = torrent_delay_minutes
    default['bypassIfHighestQuality'] = False
    default['bypassIfAboveCustomFormatScore'] = False
    default['minimumCustomFormatScore'] = 0
    updated = radarr_request('PUT', f"/delayprofile/{default['id']}", default)
    print(f'Updated default delay profile: id={updated["id"]}, torrentDelay={torrent_delay_minutes}m, preferredProtocol=usenet')
    return updated['id']


def get_movie(movie_id: int) -> Dict[str, Any]:
    return radarr_request('GET', f'/movie/{movie_id}')


def get_all_movies() -> List[Dict[str, Any]]:
    return radarr_request('GET', '/movie')


def set_movie_profile(movie_id: int, profile_id: int) -> Dict[str, Any]:
    movie = get_movie(movie_id)
    movie['qualityProfileId'] = profile_id
    return radarr_request('PUT', f'/movie/{movie_id}', movie)


def infer_policy_name(movie: Dict[str, Any], profiles: List[Dict[str, Any]]) -> str:
    profile_id = movie.get('qualityProfileId')
    profile_name = next((p['name'] for p in profiles if p['id'] == profile_id), '')
    for key, name in PROFILE_NAMES.items():
        if profile_name == name:
            return key
    return 'normal'


def quality_name_from_release(release: Dict[str, Any]) -> str:
    quality = release.get('quality', {})
    if 'quality' in quality:
        return quality['quality'].get('name', '')
    return quality.get('name', '')


def normalized_text(value: str) -> str:
    value = re.sub(r'[^a-z0-9]+', ' ', value.lower())
    return ' '.join(value.split())


def bucket_from_quality_name(name: str) -> str:
    lowered = name.lower()
    if '2160' in lowered or '4k' in lowered:
        return '2160'
    if '1080' in lowered:
        return '1080'
    if '720' in lowered:
        return '720'
    if '576' in lowered:
        return '576'
    if '480' in lowered or 'dvd' in lowered or 'bluray-480' in lowered or 'sdtv' in lowered or 'regional' in lowered:
        return '480'
    if lowered in {'cam', 'telesync', 'telecine', 'workprint'}:
        return 'sd'
    return 'unknown'


def quality_rank_within_bucket(name: str) -> int:
    lowered = name.lower()
    if 'remux' in lowered:
        return 0
    if 'bluray' in lowered or 'br-disk' in lowered:
        return 1
    if 'webdl' in lowered:
        return 2
    if 'webrip' in lowered:
        return 3
    if 'hdtv' in lowered or 'raw-hd' in lowered:
        return 4
    if 'dvd-r' in lowered:
        return 5
    if 'dvd' in lowered or 'regional' in lowered:
        return 6
    if 'sdtv' in lowered:
        return 7
    return 9


def choose_release(releases: List[Dict[str, Any]], policy_name: str) -> Optional[Dict[str, Any]]:
    policy = POLICIES[policy_name]
    bucket_order = {bucket: idx for idx, bucket in enumerate(policy['release_buckets'])}
    source_order = {source: idx for idx, source in enumerate(policy['source_order'])}

    candidates = []
    for release in releases:
        if not release.get('downloadAllowed'):
            continue
        if release.get('rejected'):
            continue
        quality_name = quality_name_from_release(release)
        bucket = bucket_from_quality_name(quality_name)
        protocol = release.get('protocol', 'unknown')
        score = (
            bucket_order.get(bucket, 999),
            source_order.get(protocol, 999),
            quality_rank_within_bucket(quality_name),
            -int(release.get('customFormatScore', 0) or 0),
            -int(release.get('size', 0) or 0),
        )
        candidates.append((score, release))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def issue_manual_grab(release: Dict[str, Any]) -> Dict[str, Any]:
    body = {
        'guid': release['guid'],
        'indexerId': release['indexerId'],
        'movieId': release.get('mappedMovieId') or release.get('movieId'),
    }
    return radarr_request('POST', '/release', body)


def search_slskd(query: str, timeout_ms: int = 5000, response_limit: int = 30, file_limit: int = 400) -> List[Dict[str, Any]]:
    search = slskd_request('POST', '/searches', {
        'searchText': query,
        'filterResponses': True,
        'maximumPeerQueueLength': 50,
        'minimumPeerUploadSpeed': 0,
        'minimumResponseFileCount': 1,
        'responseLimit': response_limit,
        'fileLimit': file_limit,
        'searchTimeout': timeout_ms,
    })
    search_id = search['id']
    for _ in range(max(10, timeout_ms // 1000 + 10)):
        state = slskd_request('GET', f'/searches/{search_id}?includeResponses=false')
        if 'InProgress' not in state.get('state', ''):
            break
        time.sleep(1)
    responses = slskd_request('GET', f'/searches/{search_id}/responses')
    try:
        slskd_request('DELETE', f'/searches/{search_id}')
    except Exception:
        pass
    return responses


def title_tokens(title: str) -> List[str]:
    tokens = normalized_text(title).split()
    return [token for token in tokens if token not in {'the', 'a', 'an', 'of', 'and', 'in', 'to'}]


def slskd_group_candidates(movie: Dict[str, Any], policy_name: str, responses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    tokens = title_tokens(movie['title'])
    year = str(movie.get('year') or '')
    bucket_order = {bucket: idx for idx, bucket in enumerate(POLICIES[policy_name]['release_buckets'])}
    candidates = []

    for response in responses:
        username = response.get('username')
        grouped: Dict[str, Dict[str, Any]] = {}
        for file in response.get('files', []):
            raw_name = file.get('filename', '')
            parts = raw_name.split('\\')
            if not parts:
                continue
            dirname = '\\'.join(parts[:-1]) if len(parts) > 1 else ''
            basename = parts[-1]
            ext = Path(basename).suffix.lower()
            if ext not in VIDEO_EXTENSIONS | SUBTITLE_EXTENSIONS:
                continue
            if any(token in normalized_text(basename) for token in JUNK_NAME_TOKENS):
                continue
            haystack = normalized_text(raw_name)
            if year and year not in haystack:
                continue
            if not all(token in haystack for token in tokens[: min(len(tokens), 5)]):
                continue
            key = dirname or basename
            bucket = bucket_from_quality_name(raw_name)
            group = grouped.setdefault(key, {
                'username': username,
                'directory': dirname,
                'files': [],
                'video_files': [],
                'subtitle_files': [],
                'bucket': bucket,
                'size': 0,
            })
            group['files'].append(file)
            group['size'] += int(file.get('size', 0) or 0)
            if ext in VIDEO_EXTENSIONS:
                group['video_files'].append(file)
            elif ext in SUBTITLE_EXTENSIONS:
                group['subtitle_files'].append(file)
            if bucket_order.get(bucket, 999) < bucket_order.get(group['bucket'], 999):
                group['bucket'] = bucket
        for group in grouped.values():
            if not group['video_files']:
                continue
            largest_video = max(group['video_files'], key=lambda item: int(item.get('size', 0) or 0))
            group['largest_video'] = largest_video
            group['quality_rank'] = quality_rank_within_bucket(largest_video.get('filename', ''))
            group['score'] = (
                bucket_order.get(group['bucket'], 999),
                quality_rank_within_bucket(largest_video.get('filename', '')),
                -int(largest_video.get('size', 0) or 0),
            )
            candidates.append(group)
    candidates.sort(key=lambda item: item['score'])
    return candidates


def enqueue_slskd_group(candidate: Dict[str, Any]) -> None:
    files = []
    largest = candidate['largest_video']['filename']
    largest_stem = Path(largest).stem.lower()
    for file in candidate['video_files']:
        files.append({'filename': file['filename'], 'size': file['size']})
    for file in candidate['subtitle_files']:
        stem = Path(file['filename']).stem.lower()
        if stem == largest_stem or largest_stem.startswith(stem) or stem.startswith(largest_stem):
            files.append({'filename': file['filename'], 'size': file['size']})
    slskd_request('POST', f"/transfers/downloads/{urllib.parse.quote(candidate['username'])}", files)


def wait_for_slskd_completion(candidate: Dict[str, Any], timeout_seconds: int = 3600) -> List[Dict[str, Any]]:
    deadline = time.time() + timeout_seconds
    wanted = {file['filename'] for file in candidate['video_files']}
    while time.time() < deadline:
        downloads = slskd_request('GET', f"/transfers/downloads/{urllib.parse.quote(candidate['username'])}")
        matched = []
        completed = []
        for directory in downloads.get('directories', []):
            for file in directory.get('files', []):
                if file.get('filename') in wanted:
                    matched.append(file)
                    state = file.get('state', '')
                    if 'Completed' in state and 'Errored' not in state:
                        completed.append(file)
        if matched and len(completed) == len(matched):
            return completed
        time.sleep(5)
    raise TimeoutError('Timed out waiting for Soulseek download completion')


def locate_completed_file(candidate: Dict[str, Any]) -> Path:
    target_names = {Path(file['filename']).name for file in candidate['video_files']}
    newest_matches = []
    for name in target_names:
        for path in SOULSEEK_COMPLETE_ROOT.rglob(name):
            if path.is_file():
                newest_matches.append(path)
    if not newest_matches:
        raise FileNotFoundError(f'Could not locate downloaded Soulseek file under {SOULSEEK_COMPLETE_ROOT}')
    newest_matches.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return newest_matches[0]


def import_file_to_movie(movie: Dict[str, Any], source_file: Path) -> Path:
    movie_dir = Path(movie['path'].replace('/movies-leviathan', '/Volumes/Leviathan/Movies'))
    movie_dir.mkdir(parents=True, exist_ok=True)
    destination = movie_dir / f"{movie['title']} ({movie['year']}){source_file.suffix.lower()}"
    if destination.exists():
        destination = movie_dir / source_file.name
    shutil.move(str(source_file), str(destination))
    radarr_request('POST', '/command', {'name': 'RefreshMovie', 'movieIds': [movie['id']]})
    radarr_request('POST', '/command', {'name': 'RescanMovie', 'movieIds': [movie['id']]})
    return destination


def run_fallback(movie_id: int, policy_name: Optional[str], dry_run: bool, soulseek_timeout: int) -> int:
    profiles = radarr_request('GET', '/qualityprofile')
    movie = get_movie(movie_id)
    chosen_policy = policy_name or infer_policy_name(movie, profiles)
    print(f"Movie: {movie['title']} ({movie['year']}) | policy={chosen_policy}")

    releases = radarr_request('GET', f'/release?movieId={movie_id}')
    best_release = choose_release(releases, chosen_policy)
    if best_release:
        quality_name = quality_name_from_release(best_release)
        print(f"Selected Radarr release: [{best_release['protocol']}] {quality_name} :: {best_release['title']}")
        if not dry_run:
            response = issue_manual_grab(best_release)
            print(json.dumps(response, indent=2))
        return 0

    print('No acceptable Radarr release found; falling back to Soulseek search...')
    queries = [
        f"{movie['title']} {movie['year']}",
        f"{movie['title'].replace(':', ' ')} {movie['year']} 1080p",
        f"{movie['title'].replace(':', ' ')} {movie['year']} 720p",
    ]
    slsk_candidates: List[Dict[str, Any]] = []
    for query in queries:
        print(f'Soulseek query: {query}')
        responses = search_slskd(query)
        slsk_candidates = slskd_group_candidates(movie, chosen_policy, responses)
        if slsk_candidates:
            break

    if not slsk_candidates:
        print('No qualifying Soulseek candidates found.')
        return 1

    candidate = slsk_candidates[0]
    print(
        'Selected Soulseek candidate:',
        json.dumps({
            'username': candidate['username'],
            'directory': candidate['directory'],
            'bucket': candidate['bucket'],
            'largest_video': candidate['largest_video']['filename'],
            'size': candidate['largest_video']['size'],
        }, indent=2)
    )
    if dry_run:
        return 0

    enqueue_slskd_group(candidate)
    print('Enqueued Soulseek download; waiting for completion...')
    wait_for_slskd_completion(candidate, timeout_seconds=soulseek_timeout)
    downloaded = locate_completed_file(candidate)
    destination = import_file_to_movie(movie, downloaded)
    print(f'Imported Soulseek file to {destination}')
    return 0


def parse_movie_ids(value: str) -> List[int]:
    return [int(part.strip()) for part in value.split(',') if part.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description='Radarr quality profile + rare-title fallback helper.')
    subparsers = parser.add_subparsers(dest='command', required=True)

    sync_parser = subparsers.add_parser('sync-radarr', help='Ensure custom Radarr quality profiles and default delay profile exist.')
    sync_parser.add_argument('--torrent-delay', type=int, default=DEFAULT_TORRENT_DELAY_MINUTES, help='Torrent delay in minutes for the default Radarr delay profile.')

    set_parser = subparsers.add_parser('set-profile', help='Assign a profile to one or more movie IDs.')
    set_parser.add_argument('--movie-ids', required=True, help='Comma-separated Radarr movie IDs.')
    set_parser.add_argument('--profile', choices=['normal', 'cinematic', 'rare'], required=True)

    fallback_parser = subparsers.add_parser('run-fallback', help='Run the explicit waterfall search for a movie.')
    fallback_parser.add_argument('--movie-id', type=int, required=True)
    fallback_parser.add_argument('--policy', choices=['normal', 'cinematic', 'rare'])
    fallback_parser.add_argument('--dry-run', action='store_true')
    fallback_parser.add_argument('--soulseek-timeout', type=int, default=3600)

    args = parser.parse_args()

    if args.command == 'sync-radarr':
        ensure_profiles()
        ensure_delay_profile(args.torrent_delay)
        return 0

    if args.command == 'set-profile':
        profiles = radarr_request('GET', '/qualityprofile')
        by_name = {profile['name']: profile for profile in profiles}
        target_name = PROFILE_NAMES[args.profile]
        if target_name not in by_name:
            raise RuntimeError(f'Profile {target_name} does not exist yet. Run sync-radarr first.')
        profile_id = by_name[target_name]['id']
        for movie_id in parse_movie_ids(args.movie_ids):
            movie = set_movie_profile(movie_id, profile_id)
            print(f"Set movie {movie['id']} -> profile {target_name} ({profile_id})")
        return 0

    if args.command == 'run-fallback':
        return run_fallback(args.movie_id, args.policy, args.dry_run, args.soulseek_timeout)

    raise RuntimeError('Unhandled command')


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        raise
