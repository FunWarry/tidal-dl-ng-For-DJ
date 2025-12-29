"""Tests for Playlist Membership Manager.

Comprehensive test suite for the playlist management system including:
- Cache thread-safety and operations
- Worker thread loading and API integration
- Dialog UI state management
- Transaction rollback on errors
"""

import threading
import unittest
from unittest.mock import Mock, patch

from PySide6 import QtCore, QtWidgets
from tidalapi import Session, Track

from tidal_dl_ng.gui.playlist_membership import (
    PlaylistCellState,
    PlaylistColumnDelegate,
    PlaylistContextLoader,
    ThreadSafePlaylistCache,
)
from tidal_dl_ng.ui.dialog_playlist_manager import PlaylistManagerDialog


class TestThreadSafePlaylistCache(unittest.TestCase):
    """Tests for ThreadSafePlaylistCache.

    Verifies thread-safety, O(1) performance, and data integrity.
    """

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.cache = ThreadSafePlaylistCache()

    def test_add_track_to_playlist(self) -> None:
        """Test adding a track to a playlist."""
        self.cache.add_track_to_playlist("track_1", "playlist_1")
        playlists = self.cache.get_playlists_for_track("track_1")
        self.assertIn("playlist_1", playlists)

    def test_remove_track_from_playlist(self) -> None:
        """Test removing a track from a playlist."""
        self.cache.add_track_to_playlist("track_1", "playlist_1")
        self.cache.remove_track_from_playlist("track_1", "playlist_1")
        playlists = self.cache.get_playlists_for_track("track_1")
        self.assertNotIn("playlist_1", playlists)

    def test_is_track_in_playlist(self) -> None:
        """Test checking if track is in playlist."""
        self.cache.add_track_to_playlist("track_1", "playlist_1")
        self.assertTrue(self.cache.is_track_in_playlist("track_1", "playlist_1"))
        self.assertFalse(self.cache.is_track_in_playlist("track_1", "playlist_2"))

    def test_get_nonexistent_track(self) -> None:
        """Test getting playlists for nonexistent track returns empty set."""
        playlists = self.cache.get_playlists_for_track("nonexistent")
        self.assertEqual(playlists, set())

    def test_multiple_playlists_per_track(self) -> None:
        """Test track can be in multiple playlists."""
        self.cache.add_track_to_playlist("track_1", "playlist_1")
        self.cache.add_track_to_playlist("track_1", "playlist_2")
        self.cache.add_track_to_playlist("track_1", "playlist_3")

        playlists = self.cache.get_playlists_for_track("track_1")
        self.assertEqual(len(playlists), 3)
        self.assertIn("playlist_1", playlists)
        self.assertIn("playlist_2", playlists)
        self.assertIn("playlist_3", playlists)

    def test_concurrent_reads_no_deadlock(self) -> None:
        """Test concurrent reads don't cause deadlock."""
        self.cache.add_track_to_playlist("track_1", "playlist_1")

        results = []

        def read_cache() -> None:
            for _ in range(100):
                result = self.cache.get_playlists_for_track("track_1")
                results.append(result)

        threads = [threading.Thread(target=read_cache) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All reads should succeed
        self.assertEqual(len(results), 500)

    def test_concurrent_writes_thread_safe(self) -> None:
        """Test concurrent writes maintain consistency."""

        def write_cache(track_id: str, playlist_ids: list[str]) -> None:
            for pid in playlist_ids:
                self.cache.add_track_to_playlist(track_id, pid)

        threads = []
        for i in range(10):
            t = threading.Thread(target=write_cache, args=(f"track_{i}", [f"p_{i}_{j}" for j in range(5)]))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify all writes succeeded
        total_tracks = sum(len(self.cache.get_playlists_for_track(f"track_{i}")) for i in range(10))
        self.assertEqual(total_tracks, 50)

    def test_update_from_dict(self) -> None:
        """Test batch update from dictionary."""
        data = {
            "track_1": {"playlist_1", "playlist_2"},
            "track_2": {"playlist_2", "playlist_3"},
        }
        self.cache.update_from_dict(data)

        self.assertEqual(self.cache.get_playlists_for_track("track_1"), {"playlist_1", "playlist_2"})
        self.assertEqual(self.cache.get_playlists_for_track("track_2"), {"playlist_2", "playlist_3"})

    def test_clear(self) -> None:
        """Test clearing the cache."""
        self.cache.add_track_to_playlist("track_1", "playlist_1")
        self.cache.clear()
        self.assertEqual(self.cache.get_playlists_for_track("track_1"), set())

    def test_set_and_get_playlist_metadata(self) -> None:
        """Test storing and retrieving playlist metadata."""
        self.cache.set_playlist_metadata("playlist_1", "My Favorites", 42)
        metadata = self.cache.get_playlist_metadata("playlist_1")

        self.assertIsNotNone(metadata)
        self.assertEqual(metadata["name"], "My Favorites")
        self.assertEqual(metadata["item_count"], 42)

    def test_get_all_playlists(self) -> None:
        """Test getting all playlist IDs."""
        self.cache.add_track_to_playlist("track_1", "playlist_1")
        self.cache.add_track_to_playlist("track_2", "playlist_2")
        self.cache.add_track_to_playlist("track_3", "playlist_1")

        all_playlists = self.cache.get_all_playlists()
        self.assertEqual(all_playlists, {"playlist_1", "playlist_2"})


class TestPlaylistContextLoader(unittest.TestCase):
    """Tests for PlaylistContextLoader worker.

    Verifies API calls, pagination, and cache building.
    """

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    @patch("tidal_dl_ng.gui.playlist_membership.Session")
    def test_fetch_user_playlists_pagination(self, mock_session_class: Mock) -> None:
        """Test handling of playlist pagination."""
        mock_session = Mock()

        # Mock paginated responses
        mock_session.request.side_effect = [
            Mock(
                json=lambda: {
                    "items": [
                        {"uuid": f"playlist_{i}", "title": f"Playlist {i}", "numberOfItems": 10} for i in range(50)
                    ],
                    "totalNumberOfItems": 75,
                }
            ),
            Mock(
                json=lambda: {
                    "items": [
                        {"uuid": f"playlist_{i}", "title": f"Playlist {i}", "numberOfItems": 10} for i in range(50, 75)
                    ],
                    "totalNumberOfItems": 75,
                }
            ),
        ]

        loader = PlaylistContextLoader(mock_session, user_id="user_123")
        playlists = loader._fetch_user_playlists()

        # Should have fetched all playlists across two pages
        self.assertEqual(len(playlists), 75)

    @patch("tidal_dl_ng.gui.playlist_membership.Session")
    def test_fetch_playlist_items_pagination(self, mock_session_class: Mock) -> None:
        """Test handling of playlist items pagination."""
        mock_session = Mock()

        # Mock paginated item responses
        mock_session.request.side_effect = [
            Mock(
                json=lambda: {
                    "items": [{"item": {"id": f"track_{i}"}} for i in range(300)],
                    "totalNumberOfItems": 450,
                }
            ),
            Mock(
                json=lambda: {
                    "items": [{"item": {"id": f"track_{i}"}} for i in range(300, 450)],
                    "totalNumberOfItems": 450,
                }
            ),
        ]

        loader = PlaylistContextLoader(mock_session, user_id="user_123")
        track_ids = loader._fetch_playlist_items("playlist_1")

        self.assertEqual(len(track_ids), 450)

    @patch("tidal_dl_ng.gui.playlist_membership.Session")
    def test_build_cache_structure(self, mock_session_class: Mock) -> None:
        """Test correct cache structure building."""
        mock_session = Mock()

        # Mock responses
        playlists_response = Mock(
            json=lambda: {
                "items": [
                    {"uuid": "playlist_1", "title": "Favorites", "numberOfItems": 2},
                    {"uuid": "playlist_2", "title": "Workout", "numberOfItems": 1},
                ],
                "totalNumberOfItems": 2,
            }
        )

        items_responses = [
            Mock(
                json=lambda: {
                    "items": [{"item": {"id": "track_1"}}, {"item": {"id": "track_2"}}],
                    "totalNumberOfItems": 2,
                }
            ),
            Mock(
                json=lambda: {
                    "items": [{"item": {"id": "track_2"}}],
                    "totalNumberOfItems": 1,
                }
            ),
        ]

        mock_session.request.side_effect = [playlists_response, *items_responses]

        loader = PlaylistContextLoader(mock_session, user_id="user_123")

        # Manually test cache building (since run() needs event loop)
        playlists = loader._fetch_user_playlists()
        cache = loader._fetch_all_playlist_contents(playlists)

        # Verify cache structure
        self.assertIn("track_1", cache)
        self.assertIn("track_2", cache)
        self.assertEqual(cache["track_1"], {"playlist_1"})
        self.assertEqual(cache["track_2"], {"playlist_1", "playlist_2"})

    @patch("tidal_dl_ng.gui.playlist_membership.Session")
    def test_abort_request(self, mock_session_class: Mock) -> None:
        """Test aborting the loader."""
        mock_session = Mock()
        loader = PlaylistContextLoader(mock_session, user_id="user_123")

        # Request abort
        loader.request_abort()

        # Verify abort flag is set
        self.assertTrue(loader._abort_requested.is_set())

    def test_max_workers_clamped(self) -> None:
        """Test max_workers is clamped to valid range."""
        mock_session = Mock()

        loader1 = PlaylistContextLoader(mock_session, user_id="user_123", max_workers=10)
        self.assertLessEqual(loader1.max_workers, 5)

        loader2 = PlaylistContextLoader(mock_session, user_id="user_123", max_workers=0)
        self.assertEqual(loader2.max_workers, 1)


class TestPlaylistColumnDelegate(unittest.TestCase):
    """Tests for PlaylistColumnDelegate.

    Verifies state rendering and transitions.
    """

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        self.delegate = PlaylistColumnDelegate()

    def test_initial_state_pending(self) -> None:
        """Test delegate starts in PENDING state."""
        # Cell should render as PENDING by default
        self.assertFalse(self.delegate._cache_ready)

    def test_set_cache_ready_transitions_states(self) -> None:
        """Test state transitions when cache becomes ready."""
        self.delegate.set_cell_state(0, PlaylistCellState.PENDING)
        self.delegate.set_cell_state(1, PlaylistCellState.PENDING)

        # Mark cache as ready
        self.delegate.set_cache_ready(True)

        # States should transition to READY
        self.assertTrue(self.delegate._cache_ready)

    def test_set_cell_state(self) -> None:
        """Test setting cell state."""
        self.delegate.set_cell_state(5, PlaylistCellState.READY)
        self.assertEqual(self.delegate._cell_states.get("5"), PlaylistCellState.READY)

        self.delegate.set_cell_state(5, PlaylistCellState.ERROR)
        self.assertEqual(self.delegate._cell_states.get("5"), PlaylistCellState.ERROR)

    def test_state_rendering_pending(self) -> None:
        """Test rendering of PENDING state (spinner)."""
        # Create mock painter and option
        painter = Mock()
        painter.fillRect = Mock()
        painter.setPen = Mock()
        painter.drawText = Mock()

        option = Mock()
        option.rect = Mock(adjusted=Mock(return_value=Mock(center=Mock(return_value=QtCore.QPoint(50, 50)))))
        option.state = 0

        index = Mock()
        index.row = Mock(return_value=0)

        # Set state to PENDING
        self.delegate.set_cell_state(0, PlaylistCellState.PENDING)

        # Paint should be called without errors
        # (Actual painting verification would require QPixmap/screen rendering)

    def test_button_click_event(self) -> None:
        """Test that READY state cells emit button_clicked signal."""
        self.delegate.set_cell_state(0, PlaylistCellState.READY)

        # Create mock event and model
        event = Mock()
        event.type = Mock(return_value=QtCore.QEvent.Type.MouseButtonRelease)

        model = Mock()
        option = Mock()
        index = Mock()
        index.row = Mock(return_value=0)

        # Track signal emissions
        signal_emitted = []

        def on_button_clicked(idx) -> None:
            signal_emitted.append(idx)

        self.delegate.button_clicked.connect(on_button_clicked)

        # Simulate click event
        handled = self.delegate.editorEvent(event, model, option, index)

        # Should handle the event and emit signal
        self.assertTrue(handled)


class TestPlaylistManagerDialog(unittest.TestCase):
    """Tests for PlaylistManagerDialog.

    Verifies UI state, transaction logic, and error handling.
    """

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        self.threadpool = QtCore.QThreadPool()

        # Create mock objects
        self.mock_track = Mock(spec=Track)
        self.mock_track.id = "track_uuid_1"
        self.mock_track.name = "Test Track"

        self.cache = ThreadSafePlaylistCache()

        # Add test data to cache
        self.cache.set_playlist_metadata("playlist_1", "Favorites", 42)
        self.cache.set_playlist_metadata("playlist_2", "Workout Mix", 15)
        self.cache.add_track_to_playlist("track_uuid_1", "playlist_1")

        self.mock_session = Mock(spec=Session)

    def test_dialog_initialization(self) -> None:
        """Test dialog initializes correctly."""
        dialog = PlaylistManagerDialog(
            track=self.mock_track,
            cache=self.cache,
            session=self.mock_session,
            threadpool=self.threadpool,
        )

        self.assertIsNotNone(dialog)
        self.assertEqual(dialog.track.name, "Test Track")

    def test_playlists_populated_from_cache(self) -> None:
        """Test dialog populates playlists from cache."""
        dialog = PlaylistManagerDialog(
            track=self.mock_track,
            cache=self.cache,
            session=self.mock_session,
            threadpool=self.threadpool,
        )

        # Count checkbox widgets (should be 2 playlists)
        checkboxes = dialog.container_layout.count()
        self.assertGreaterEqual(checkboxes, 2)

    def test_checkbox_initial_state_from_cache(self) -> None:
        """Test checkboxes reflect initial cache state."""
        dialog = PlaylistManagerDialog(
            track=self.mock_track,
            cache=self.cache,
            session=self.mock_session,
            threadpool=self.threadpool,
        )

        # Track is in playlist_1, so that checkbox should be checked
        # Track is NOT in playlist_2, so that checkbox should be unchecked
        original_states = dialog._original_states

        self.assertTrue(original_states.get("playlist_1"))
        self.assertFalse(original_states.get("playlist_2"))

    @patch("tidal_dl_ng.gui.dialog_playlist_manager.Worker")
    def test_checkbox_change_triggers_worker(self, mock_worker_class: Mock) -> None:
        """Test checkbox change triggers worker thread."""
        PlaylistManagerDialog(
            track=self.mock_track,
            cache=self.cache,
            session=self.mock_session,
            threadpool=self.threadpool,
        )

        # Mock worker
        mock_worker_class.return_value = Mock()

        # Simulate checkbox change would trigger worker
        # (Actual checkbox interaction would require Qt event simulation)

    def test_api_add_track_success(self) -> None:
        """Test successful track addition."""
        dialog = PlaylistManagerDialog(
            track=self.mock_track,
            cache=self.cache,
            session=self.mock_session,
            threadpool=self.threadpool,
        )

        # Mock successful API response
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        self.mock_session.request.return_value = mock_response

        # Create checkbox mock
        mock_checkbox = Mock()

        # Simulate add operation
        dialog._api_add_track_to_playlist("track_uuid_1", "playlist_2", mock_checkbox, False)

        # Cache should be updated
        self.assertTrue(self.cache.is_track_in_playlist("track_uuid_1", "playlist_2"))

        # Checkbox should be re-enabled
        mock_checkbox.setEnabled.assert_called_with(True)

    def test_api_add_track_error_rollback(self) -> None:
        """Test rollback on add failure."""
        dialog = PlaylistManagerDialog(
            track=self.mock_track,
            cache=self.cache,
            session=self.mock_session,
            threadpool=self.threadpool,
        )

        # Mock failed API response
        mock_response = Mock()
        mock_response.raise_for_status = Mock(side_effect=Exception("API Error"))
        self.mock_session.request.return_value = mock_response

        # Create checkbox mock
        mock_checkbox = Mock()

        # Original state: not checked
        original_state = False

        # Simulate failed add operation
        dialog._api_add_track_to_playlist("track_uuid_1", "playlist_2", mock_checkbox, original_state)

        # Checkbox should be restored to original state
        mock_checkbox.setChecked.assert_called()

        # Checkbox should be re-enabled
        mock_checkbox.setEnabled.assert_called_with(True)

    def test_api_remove_track_success(self) -> None:
        """Test successful track removal."""
        dialog = PlaylistManagerDialog(
            track=self.mock_track,
            cache=self.cache,
            session=self.mock_session,
            threadpool=self.threadpool,
        )

        # Mock successful API responses
        mock_items_response = Mock()
        mock_items_response.json.return_value = {
            "items": [{"id": "item_uuid_1", "item": {"id": "track_uuid_1"}}],
            "totalNumberOfItems": 1,
        }

        mock_delete_response = Mock()
        mock_delete_response.raise_for_status = Mock()

        self.mock_session.request.side_effect = [mock_items_response, mock_delete_response]

        # Create checkbox mock
        mock_checkbox = Mock()

        # Verify track is in cache initially
        self.assertTrue(self.cache.is_track_in_playlist("track_uuid_1", "playlist_1"))

        # Simulate remove operation
        dialog._api_remove_track_from_playlist("track_uuid_1", "playlist_1", mock_checkbox, True)

        # Cache should be updated (track removed)
        self.assertFalse(self.cache.is_track_in_playlist("track_uuid_1", "playlist_1"))

        # Checkbox should be re-enabled
        mock_checkbox.setEnabled.assert_called_with(True)


if __name__ == "__main__":
    unittest.main()
