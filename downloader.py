import json
import logging
import re
from pathlib import Path
from time import sleep
from typing import List, Optional

import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.exceptions import RequestException, Timeout

# Configure module‐level logger. You can override level in main.py if desired.
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class UnityScraper:
    """
    A class to fetch Xbox cover art and title updates given Title IDs
    from xboxunity.net endpoints. It saves both JSON metadata and binary
    files into a directory tree under `unityscrape/{title_id}/...`.
    """

    # Base directory for all outputs
    BASE_DIR = Path("unityscrape")

    # Endpoints for xboxunity.net (hardcode once, so changes are easy)
    ENDPOINTS = {
        "cover_info":   "http://xboxunity.net/Resources/Lib/CoverInfo.php",
        "cover_fetch":  "http://xboxunity.net/Resources/Lib/Cover.php",
        "update_info":  "http://xboxunity.net/Resources/Lib/TitleUpdateInfo.php",
        "update_fetch": "http://xboxunity.net/Resources/Lib/TitleUpdate.php",
    }

    # How many times to retry a failed HTTP request
    MAX_RETRIES = 3
    # Exponential backoff factor (2^n seconds)
    BACKOFF_FACTOR = 2
    # Maximum backoff (in seconds)
    MAX_BACKOFF = 30
    # Number of threads for parallel downloads (per TitleID)
    MAX_WORKERS = 4

    def __init__(self, session: Optional[requests.Session] = None):
        """
        Initialize the UnityScraper.

        :param session: Optional requests.Session instance. If not provided,
                        a new Session() is created, which enables connection pooling.
        """
        self.session = session or requests.Session()

    def _make_request(
        self, url: str, stream: bool = False, timeout: float = 10.0
    ) -> Optional[requests.Response]:
        """
        Internal helper: Perform a GET request with retries and exponential backoff.

        :param url: Full URL to fetch.
        :param stream: If True, allow streaming response (for large binaries).
        :param timeout: Timeout in seconds (connect + read).
        :return: requests.Response on success, or None if all retries failed.
        """
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                resp = self.session.get(url, timeout=timeout, stream=stream)
                resp.raise_for_status()
                return resp
            except (RequestException, Timeout) as exc:
                wait = min(self.BACKOFF_FACTOR ** (attempt - 1), self.MAX_BACKOFF)
                logger.warning(
                    "Request to %s failed (attempt %d/%d): %s. Retrying in %d seconds...",
                    url,
                    attempt,
                    self.MAX_RETRIES,
                    exc,
                    wait,
                )
                sleep(wait)

        logger.error("Exceeded retries for URL: %s", url)
        return None

    def _save_json(self, title_id: str, payload: dict, json_type: str) -> None:
        """
        Save JSON payload to a file under BASE_DIR/{title_id}/{json_type}_data.json.

        :param title_id: The Title ID (e.g. '555308C5').
        :param payload: A dict representing JSON data.
        :param json_type: Either 'covers' or 'updates' (used in filename).
        """
        out_dir = self.BASE_DIR / title_id
        out_dir.mkdir(parents=True, exist_ok=True)

        file_path = out_dir / f"{json_type}_data.json"
        try:
            with file_path.open("w", encoding="utf-8") as fp:
                json.dump(payload, fp, indent=4)
            logger.info(
                "Saved %s JSON for title %s at %s",
                json_type,
                title_id,
                file_path,
            )
        except Exception as exc:
            logger.error(
                "Failed to write %s JSON for title %s: %s", json_type, title_id, exc
            )

    def _extract_filename(self, content_disposition: Optional[str]) -> Optional[str]:
        """
        Parse the 'Content-Disposition' header to extract the filename.

        :param content_disposition: e.g. 'attachment; filename="image.jpg"'
        :return: 'image.jpg' or None if not found.
        """
        if not content_disposition:
            return None

        matches = re.findall(r'filename="?(.+)"?', content_disposition)
        if matches:
            return matches[0].strip().strip('"')
        return None

    def download_covers(self, title_id: str) -> bool:
        """
        Fetch cover metadata JSON, save it, then download each cover image in parallel.

        :param title_id: Xbox Title ID, e.g. '555308C5'.
        :return: True if all steps succeeded or no covers exist; False if any failures occurred.
        """
        logger.info("Fetching cover metadata for Title ID %s...", title_id)
        info_url = f"{self.ENDPOINTS['cover_info']}?titleid={title_id}"
        resp = self._make_request(info_url)

        if not resp:
            logger.error("Failed to fetch cover info for %s", title_id)
            return False

        # Parse JSON
        try:
            covers_data = resp.json()
        except ValueError as exc:
            logger.error("Invalid JSON response for %s cover info: %s", title_id, exc)
            return False

        self._save_json(title_id, covers_data, "covers")

        covers_list = covers_data.get("Covers", [])
        if not isinstance(covers_list, list) or not covers_list:
            logger.info("No covers found for Title ID %s; skipping downloads.", title_id)
            return True

        # Ensure output directory for covers exists
        cover_dir = self.BASE_DIR / title_id / "covers"
        cover_dir.mkdir(parents=True, exist_ok=True)

        # Worker function for a single cover download
        def _download_single_cover(cover: dict) -> bool:
            cover_id = cover.get("CoverID")
            if not cover_id:
                logger.warning(
                    "Missing CoverID in one of the entries for Title %s; skipping.", title_id
                )
                return True  # skip but not fatal

            logger.info("Downloading cover %s for Title %s...", cover_id, title_id)
            image_url = f"{self.ENDPOINTS['cover_fetch']}?size=large&cid={cover_id}"
            img_resp = self._make_request(image_url, stream=True)
            if not img_resp:
                logger.error(
                    "Failed to download cover %s for Title %s", cover_id, title_id
                )
                return False

            # Try extracting filename from headers
            cd_header = img_resp.headers.get("content-disposition")
            filename = self._extract_filename(cd_header)
            if not filename:
                # Fallback: use MIME type to choose extension
                content_type = img_resp.headers.get("Content-Type", "")
                ext = content_type.split("/")[-1] if "/" in content_type else "jpg"
                filename = f"{cover_id}.{ext}"

            out_file = cover_dir / filename
            try:
                with out_file.open("wb") as fp:
                    for chunk in img_resp.iter_content(chunk_size=8192):
                        fp.write(chunk)
                logger.info(
                    "Saved cover %s for Title %s to %s", cover_id, title_id, out_file
                )
                return True
            except Exception as write_exc:
                logger.error(
                    "Error writing cover %s for Title %s: %s", cover_id, title_id, write_exc
                )
                return False

        # Download covers in parallel
        success = True
        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            future_to_cover = {
                executor.submit(_download_single_cover, cover): cover.get("CoverID")
                for cover in covers_list
            }
            for future in as_completed(future_to_cover):
                cover_id = future_to_cover[future]
                try:
                    result = future.result()
                    if not result:
                        success = False
                except Exception as exc:
                    logger.error(
                        "Unexpected exception downloading cover %s for %s: %s",
                        cover_id,
                        title_id,
                        exc,
                    )
                    success = False

        return success

    def download_updates(self, title_id: str) -> bool:
        """
        Fetch update metadata JSON, save it, then download each Title Update binary in parallel.

        :param title_id: Xbox Title ID, e.g. '555308C5'.
        :return: True if all steps succeeded or no updates exist; False if any failures occurred.
        """
        logger.info("Fetching update metadata for Title ID %s...", title_id)
        info_url = f"{self.ENDPOINTS['update_info']}?titleid={title_id}"
        resp = self._make_request(info_url)

        if not resp:
            logger.error("Failed to fetch update info for %s", title_id)
            return False

        # Parse JSON
        try:
            updates_data = resp.json()
        except ValueError as exc:
            logger.error("Invalid JSON response for %s update info: %s", title_id, exc)
            return False

        self._save_json(title_id, updates_data, "updates")

        media_list = updates_data.get("MediaIDS", [])
        if not isinstance(media_list, list) or not media_list:
            logger.info("No Title Update metadata under MediaIDS for Title %s; skipping.", title_id)
            return True

        # Worker function for a single update download
        def _download_single_update(media: dict, update_entry: dict) -> bool:
            media_id = media.get("MediaID")
            tuid = update_entry.get("TitleUpdateID")
            version = update_entry.get("Version")

            if not media_id or not tuid or version is None:
                logger.warning(
                    "Invalid media/update entry under Title %s: %s / %s. Skipping.",
                    title_id,
                    media,
                    update_entry,
                )
                return True  # skip but not fatal

            logger.info(
                "Downloading update %s (version %s) for Media %s under Title %s...",
                tuid,
                version,
                media_id,
                title_id,
            )
            update_url = f"{self.ENDPOINTS['update_fetch']}?tuid={tuid}"
            upd_resp = self._make_request(update_url, stream=True)
            if not upd_resp:
                logger.error(
                    "Failed to download update %s (Title %s)", tuid, title_id
                )
                return False

            # Determine filename
            cd_header = upd_resp.headers.get("content-disposition")
            filename = self._extract_filename(cd_header) or f"update_{tuid}.bin"

            out_dir = self.BASE_DIR / title_id / str(media_id) / f"updateversion{version}"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / filename

            try:
                with out_file.open("wb") as fp:
                    for chunk in upd_resp.iter_content(chunk_size=8192):
                        fp.write(chunk)
                logger.info(
                    "Saved update %s (Title %s) to %s", tuid, title_id, out_file
                )
                return True
            except Exception as write_exc:
                logger.error(
                    "Error writing update %s (Title %s): %s", tuid, title_id, write_exc
                )
                return False

        # Collect all (media, update_entry) pairs
        tasks = []
        for media in media_list:
            updates_sublist = media.get("Updates", [])
            if not isinstance(updates_sublist, list):
                continue
            for upd in updates_sublist:
                tasks.append((media, upd))

        if not tasks:
            logger.info("No valid Updates entries for Title %s; skipping downloads.", title_id)
            return True

        # Download all updates in parallel
        success = True
        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            future_to_ident = {}
            for media, upd in tasks:
                future = executor.submit(_download_single_update, media, upd)
                # We store (mediaID, tuid) just for logging on exception
                future_to_ident[future] = (
                    media.get("MediaID"),
                    upd.get("TitleUpdateID"),
                )

            for future in as_completed(future_to_ident):
                media_id, tuid = future_to_ident[future]
                try:
                    result = future.result()
                    if not result:
                        success = False
                except Exception as exc:
                    logger.error(
                        "Unexpected exception downloading update %s (Media %s) for Title %s: %s",
                        tuid,
                        media_id,
                        title_id,
                        exc,
                    )
                    success = False

        return success

    def scrape_multiple(self, title_ids: List[str]) -> List[str]:
        """
        Given a list of Title IDs, download covers & updates for each in sequence.

        :param title_ids: e.g. ['555308C5', '00000155', ...]
        :return: A list of Title IDs that failed (empty if all succeeded).
        """
        failed = []
        for idx, tid in enumerate(title_ids, start=1):
            tid = tid.strip()
            if not tid:
                continue
            logger.info("=== (%d/%d) Processing Title ID %s ===", idx, len(title_ids), tid)
            ok1 = self.download_covers(tid)
            ok2 = self.download_updates(tid)
            if not (ok1 and ok2):
                failed.append(tid)
            logger.info(
                "=== Finished Title ID %s (covers: %s, updates: %s) ===",
                tid,
                ok1,
                ok2,
            )
        return failed
