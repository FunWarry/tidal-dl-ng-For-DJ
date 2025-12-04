# tidal_dl_ng/search.py

from typing import TYPE_CHECKING, Any

from tidalapi import Album, Artist, Mix, Playlist, Track, Video
from tidalapi import VideoQuality as QualityVideo
from tidalapi.media import AudioMode, Quality
from tidalapi.playlist import Folder
from tidalapi.session import SearchTypes

from tidal_dl_ng.constants import QueueDownloadStatus
from tidal_dl_ng.helper.tidal import (
    get_tidal_media_id,
    get_tidal_media_type,
    instantiate_media,
    name_builder_artist,
    name_builder_title,
    quality_audio_highest,
    search_results_all,
    url_ending_clean,
)
from tidal_dl_ng.logger import logger_gui
from tidal_dl_ng.model.gui_data import QueueDownloadItem, ResultItem

if TYPE_CHECKING:
    from tidal_dl_ng.gui import MainWindow


class GuiSearchManager:
    """Manages the search GUI and logic."""

    def __init__(self, main_window: "MainWindow"):
        """Initialize the search manager."""
        self.main_window: "MainWindow" = main_window

    def search_populate_results(self, query: str, type_media: Any) -> None:
        """Populate the results tree with search results."""
        results = self.search(query, [type_media])
        self.main_window.populate_tree_results(results)

    def search(self, query: str, types_media: list[Any]) -> list[ResultItem]:
        """Perform a search and return a list of ResultItems.

        Args:
            query (str): The search query.
            types_media (list[Any]): The types of media to search for.

        Returns:
            list[ResultItem]: The search results.
        """
        query_clean: str = query.strip()

        # If a direct link was searched for, skip search and create the object from the link directly.
        if "http" in query_clean:
            query_clean: str = url_ending_clean(query_clean)
            media_type = get_tidal_media_type(query_clean)
            item_id = get_tidal_media_id(query_clean)

            try:
                media = instantiate_media(self.main_window.tidal.session, media_type, item_id)
            except:
                logger_gui.error(f"Media not found (ID: {item_id}). Maybe it is not available anymore.")

                media = None

            result_search = {"direct": [media]}
        else:
            result_search: dict[str, list[SearchTypes]] = search_results_all(
                session=self.main_window.tidal.session, needle=query_clean, types_media=types_media
            )

        result: list[ResultItem] = []

        for _media_type, l_media in result_search.items():
            if isinstance(l_media, list):
                result = result + self.search_result_to_model(l_media)

        return result

    def search_result_to_model(self, items: list[SearchTypes]) -> list[ResultItem]:
        """Convert search results to ResultItem models.

        Args:
            items (list[SearchTypes]): List of search result items.

        Returns:
            list[ResultItem]: List of ResultItem models.
        """
        result: list[ResultItem] = []

        for idx, item in enumerate(items):
            result_item = self._to_result_item(idx, item)

            if result_item is not None:
                result.append(result_item)

        return result

    def _to_result_item(self, idx: int, item) -> ResultItem | None:
        """Helper to convert a single item to ResultItem, or None if not valid.

        Args:
            idx (int): Index of the item.
            item: The item to convert.

        Returns:
            ResultItem | None: The converted ResultItem or None if not valid.
        """
        if not item or (hasattr(item, "available") and not item.available):
            return None

        # Prepare common data
        explicit = " 🅴" if isinstance(item, Track | Video | Album) and item.explicit else ""
        date_user_added = (
            item.user_date_added.strftime("%Y-%m-%d_%H:%M") if getattr(item, "user_date_added", None) else ""
        )
        date_release = self._get_date_release(item)

        # Map item types to their conversion methods
        type_handlers = {
            Track: lambda: self._result_item_from_track(idx, item, explicit, date_user_added, date_release),
            Video: lambda: self._result_item_from_video(idx, item, explicit, date_user_added, date_release),
            Playlist: lambda: self._result_item_from_playlist(idx, item, date_user_added, date_release),
            Album: lambda: self._result_item_from_album(idx, item, explicit, date_user_added, date_release),
            Mix: lambda: self._result_item_from_mix(idx, item, date_user_added, date_release),
            Artist: lambda: self._result_item_from_artist(idx, item, date_user_added, date_release),
            Folder: lambda: self._result_item_from_folder(idx, item, date_user_added),
        }

        # Find and execute the appropriate handler
        for item_type, handler in type_handlers.items():
            if isinstance(item, item_type):
                return handler()

        return None

    def _get_date_release(self, item) -> str:
        """Get the release date string for an item.

        Args:
            item: The item to extract the release date from.

        Returns:
            str: The formatted release date or empty string.
        """
        if hasattr(item, "album") and item.album and getattr(item.album, "release_date", None):
            return item.album.release_date.strftime("%Y-%m-%d_%H:%M")

        if hasattr(item, "release_date") and item.release_date:
            return item.release_date.strftime("%Y-%m-%d_%H:%M")

        return ""

    def _result_item_from_track(
        self, idx: int, item, explicit: str, date_user_added: str, date_release: str
    ) -> ResultItem:
        """Create a ResultItem from a Track.

        Args:
            idx (int): Index of the item.
            item: The Track item.
            explicit (str): Explicit tag.
            date_user_added (str): Date user added.
            date_release (str): Release date.

        Returns:
            ResultItem: The constructed ResultItem.
        """

        final_quality = quality_audio_highest(item)
        if hasattr(item, "audio_modes") and AudioMode.dolby_atmos.value in item.audio_modes:
            final_quality = f"{final_quality} / Dolby Atmos"

        return ResultItem(
            position=idx,
            artist=name_builder_artist(item),
            title=f"{name_builder_title(item)}{explicit}",
            album=item.album.name,
            duration_sec=item.duration,
            obj=item,
            quality=final_quality,
            explicit=bool(item.explicit),
            date_user_added=date_user_added,
            date_release=date_release,
        )

    def _result_item_from_video(
        self, idx: int, item, explicit: str, date_user_added: str, date_release: str
    ) -> ResultItem:
        """Create a ResultItem from a Video.

        Args:
            idx (int): Index of the item.
            item: The Video item.
            explicit (str): Explicit tag.
            date_user_added (str): Date user added.
            date_release (str): Release date.

        Returns:
            ResultItem: The constructed ResultItem.
        """
        return ResultItem(
            position=idx,
            artist=name_builder_artist(item),
            title=f"{name_builder_title(item)}{explicit}",
            album=item.album.name if item.album else "",
            duration_sec=item.duration,
            obj=item,
            quality=item.video_quality,
            explicit=bool(item.explicit),
            date_user_added=date_user_added,
            date_release=date_release,
        )

    def _result_item_from_playlist(self, idx: int, item, date_user_added: str, date_release: str) -> ResultItem:
        """Create a ResultItem from a Playlist.

        Args:
            idx (int): Index of the item.
            item: The Playlist item.
            date_user_added (str): Date user added.
            date_release (str): Release date.

        Returns:
            ResultItem: The constructed ResultItem.
        """
        return ResultItem(
            position=idx,
            artist=", ".join(artist.name for artist in item.promoted_artists) if item.promoted_artists else "",
            title=item.name,
            album="",
            duration_sec=item.duration,
            obj=item,
            quality="",
            explicit=False,
            date_user_added=date_user_added,
            date_release=date_release,
        )

    def _result_item_from_album(
        self, idx: int, item, explicit: str, date_user_added: str, date_release: str
    ) -> ResultItem:
        """Create a ResultItem from an Album.

        Args:
            idx (int): Index of the item.
            item: The Album item.
            explicit (str): Explicit tag.
            date_user_added (str): Date user added.
            date_release (str): Release date.

        Returns:
            ResultItem: The constructed ResultItem.
        """
        return ResultItem(
            position=idx,
            artist=name_builder_artist(item),
            title="",
            album=f"{item.name}{explicit}",
            duration_sec=item.duration,
            obj=item,
            quality=quality_audio_highest(item),
            explicit=bool(item.explicit),
            date_user_added=date_user_added,
            date_release=date_release,
        )

    def _result_item_from_mix(self, idx: int, item, date_user_added: str, date_release: str) -> ResultItem:
        """Create a ResultItem from a Mix.

        Args:
            idx (int): Index of the item.
            item: The Mix item.
            date_user_added (str): Date user added.
            date_release (str): Release date.

        Returns:
            ResultItem: The constructed ResultItem.
        """
        return ResultItem(
            position=idx,
            artist=item.sub_title,
            title=item.title,
            album="",
            duration_sec=-1,  # TODO: Calculate total duration.
            obj=item,
            quality="",
            explicit=False,
            date_user_added=date_user_added,
            date_release=date_release,
        )

    def _result_item_from_artist(self, idx: int, item, date_user_added: str, date_release: str) -> ResultItem:
        """Create a ResultItem from an Artist.

        Args:
            idx (int): Index of the item.
            item: The Artist item.
            date_user_added (str): Date user added.
            date_release (str): Release date.

        Returns:
            ResultItem: The constructed ResultItem.
        """
        return ResultItem(
            position=idx,
            artist=item.name,
            title="",
            album="",
            duration_sec=-1,
            obj=item,
            quality="",
            explicit=False,
            date_user_added=date_user_added,
            date_release=date_release,
        )

    def _result_item_from_folder(self, idx: int, item: Folder, date_user_added: str) -> ResultItem:
        """Create a ResultItem from a Folder.

        Args:
            idx (int): Index of the item.
            item (Folder): The Folder item.
            date_user_added (str): Date user added.

        Returns:
            ResultItem: The constructed ResultItem.
        """
        total_items: int = item.total_number_of_items if hasattr(item, "total_number_of_items") else 0
        return ResultItem(
            position=idx,
            artist="",
            title=f"📁 {item.name} ({total_items} items)",
            album="",
            duration_sec=-1,
            obj=item,
            quality="",
            explicit=False,
            date_user_added=date_user_added,
            date_release="",
        )

    def media_to_queue_download_model(
        self, media: Artist | Track | Video | Album | Playlist | Mix
    ) -> QueueDownloadItem | bool:
        """Convert a media object to a QueueDownloadItem for the download queue.

        Args:
            media (Artist | Track | Video | Album | Playlist | Mix): The media object.

        Returns:
            QueueDownloadItem | bool: The queue item or False if not available.
        """
        result: QueueDownloadItem | False
        name: str = ""
        quality_audio: Quality = self.main_window.settings.data.quality_audio
        quality_video: QualityVideo = self.main_window.settings.data.quality_video
        explicit: str = ""

        # Check if item is available on TIDAL.
        # Note: Some albums have available=None, which should be treated as available
        if hasattr(media, "available") and media.available is False:
            return False

        # Set "Explicit" tag
        if isinstance(media, Track | Video | Album):
            explicit = " 🅴" if media.explicit else ""

        # Build name and set quality
        if isinstance(media, Track | Video):
            name = f"{name_builder_artist(media)} - {name_builder_title(media)}{explicit}"
        elif isinstance(media, Playlist | Artist):
            name = media.name
        elif isinstance(media, Album):
            name = f"{name_builder_artist(media)} - {media.name}{explicit}"
        elif isinstance(media, Mix):
            name = media.title

        # Determine actual quality.
        if isinstance(media, Track | Album):
            quality_highest: Quality = quality_audio_highest(media)

            if (
                self.main_window.settings.data.quality_audio == quality_highest
                or self.main_window.settings.data.quality_audio == Quality.hi_res_lossless
            ):
                quality_audio = quality_highest

        if name:
            result = QueueDownloadItem(
                name=name,
                quality_audio=quality_audio,
                quality_video=quality_video,
                type_media=type(media).__name__,
                status=QueueDownloadStatus.Waiting,
                obj=media,
            )
        else:
            result = False

        return result
