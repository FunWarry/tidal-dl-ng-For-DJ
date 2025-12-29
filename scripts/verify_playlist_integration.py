"""Verification script for playlist membership integration.

Checks that all components are properly integrated into MainWindow.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def _check_import(module_path: str, component_name: str, check_num: int) -> tuple[int, int]:
    """Check if a component can be imported.

    Args:
        module_path: The module path to import from
        component_name: The component name to import
        check_num: The check number for display

    Returns:
        tuple[int, int]: (passed, failed) counts
    """
    try:
        __import__(module_path, fromlist=[component_name])
    except ImportError as e:
        print(f"❌ Check {check_num}: {component_name} import failed: {e}")
        return (0, 1)
    else:
        print(f"✅ Check {check_num}: {component_name} importable")
        return (1, 0)


def _run_all_import_checks() -> tuple[int, int]:
    """Run all import checks.

    Returns:
        tuple[int, int]: (passed, failed) counts
    """
    checks = [
        ("tidal_dl_ng.gui.playlist_membership_mixin", "PlaylistMembershipMixin", 1),
        ("tidal_dl_ng.gui.playlist_membership", "PlaylistContextLoader", 2),
        ("tidal_dl_ng.gui.playlist_membership", "ThreadSafePlaylistCache", 3),
        ("tidal_dl_ng.gui.playlist_membership", "PlaylistColumnDelegate", 4),
        ("tidal_dl_ng.ui.dialog_playlist_manager", "PlaylistManagerDialog", 5),
    ]

    total_passed = 0
    total_failed = 0

    for module_path, component_name, check_num in checks:
        passed, failed = _check_import(module_path, component_name, check_num)
        total_passed += passed
        total_failed += failed

    return total_passed, total_failed


def _check_mainwindow_inheritance() -> tuple[int, int]:
    """Check if MainWindow inherits from PlaylistMembershipMixin.

    Returns:
        tuple[int, int]: (passed, failed) counts
    """
    try:
        from tidal_dl_ng.gui.main_window import MainWindow
        from tidal_dl_ng.gui.playlist_membership_mixin import PlaylistMembershipMixin

        if issubclass(MainWindow, PlaylistMembershipMixin):
            print("✅ Check 6: MainWindow has PlaylistMembershipMixin")
            return (1, 0)
    except Exception as e:
        print(f"❌ Check 6: MainWindow inheritance check failed: {e}")
        return (0, 1)
    else:
        print("❌ Check 6: MainWindow does not inherit PlaylistMembershipMixin")
        return (0, 1)


def _check_method_exists() -> tuple[int, int]:
    """Check if init_playlist_membership_manager method exists.

    Returns:
        tuple[int, int]: (passed, failed) counts
    """
    try:
        from tidal_dl_ng.gui.main_window import MainWindow

        if hasattr(MainWindow, "init_playlist_membership_manager"):
            print("✅ Check 7: init_playlist_membership_manager method exists")
            return (1, 0)
    except Exception as e:
        print(f"❌ Check 7: Method check failed: {e}")
        return (0, 1)
    else:
        print("❌ Check 7: init_playlist_membership_manager method not found")
        return (0, 1)


def _check_file_content(
    file_path: Path, search_str: str, check_num: int, success_msg: str, fail_msg: str
) -> tuple[int, int]:
    """Check if a file contains a specific string.

    Args:
        file_path: Path to the file to check
        search_str: String to search for
        check_num: Check number for display
        success_msg: Message to display on success
        fail_msg: Message to display on failure

    Returns:
        tuple[int, int]: (passed, failed) counts
    """
    try:
        with open(file_path) as f:
            content = f.read()
            if search_str in content:
                print(f"✅ Check {check_num}: {success_msg}")
                return (1, 0)
            print(f"❌ Check {check_num}: {fail_msg}")
            return (0, 1)
    except Exception as e:
        print(f"❌ Check {check_num}: File check failed: {e}")
        return (0, 1)


def check_integration() -> int:
    """Verify all components are integrated.

    Returns:
        int: 0 if all checks pass, 1 otherwise
    """
    checks_passed = 0
    checks_failed = 0

    print("🔍 Vérification de l'intégration du Playlist Membership Manager\n")
    print("=" * 70)

    # Run all import checks
    passed, failed = _run_all_import_checks()
    checks_passed += passed
    checks_failed += failed

    # Check 6: MainWindow has PlaylistMembershipMixin
    passed, failed = _check_mainwindow_inheritance()
    checks_passed += passed
    checks_failed += failed

    # Check 7: init_playlist_membership_manager method exists
    passed, failed = _check_method_exists()
    checks_passed += passed
    checks_failed += failed

    # Check 8: TreesResultsMixin has playlists column
    passed, failed = _check_file_content(
        project_root / "tidal_dl_ng" / "gui" / "trees_results.py",
        "child_playlists",
        8,
        "child_playlists column added to TreesResultsMixin",
        "child_playlists column NOT found in TreesResultsMixin",
    )
    checks_passed += passed
    checks_failed += failed

    # Check 9: tidal_session.py calls init_playlist_membership_manager
    passed, failed = _check_file_content(
        project_root / "tidal_dl_ng" / "gui" / "tidal_session.py",
        "init_playlist_membership_manager",
        9,
        "init_playlist_membership_manager called in init_tidal",
        "init_playlist_membership_manager NOT called in init_tidal",
    )
    checks_passed += passed
    checks_failed += failed

    # Check 10: PlaylistMembershipMixin imports PlaylistCellState
    passed, failed = _check_file_content(
        project_root / "tidal_dl_ng" / "gui" / "playlist_membership_mixin.py",
        "PlaylistCellState",
        10,
        "PlaylistCellState imported in mixin",
        "PlaylistCellState NOT imported in mixin",
    )
    checks_passed += passed
    checks_failed += failed

    # Print summary
    print("\n" + "=" * 70)
    print(f"\n📊 Résultat: {checks_passed} ✅  /  {checks_failed} ❌\n")

    if checks_failed == 0:
        print("🎉 INTÉGRATION COMPLÈTE - Tous les checks sont passés!")
        return 0

    print(f"⚠️  {checks_failed} problème(s) détecté(s)")
    return 1


if __name__ == "__main__":
    exit_code = check_integration()
    sys.exit(exit_code)
