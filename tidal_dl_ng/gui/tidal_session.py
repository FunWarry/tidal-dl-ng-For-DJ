"""Tidal session mixin for MainWindow.

Handles Tidal authentication and session management.
"""

import sys

from requests.exceptions import HTTPError
from tidalapi.session import LinkLogin

from tidal_dl_ng.config import Tidal
from tidal_dl_ng.dialog import DialogLogin
from tidal_dl_ng.logger import logger_gui


class TidalSessionMixin:
    """Mixin containing Tidal session management methods."""

    def init_tidal(self, tidal: Tidal | None = None):
        """Initialize Tidal session and handle login flow."""
        result: bool = False

        if tidal:
            self.tidal = tidal
            result = True
        else:
            self.tidal = Tidal(self.settings)
            result = self.tidal.login_token()

            if not result:
                hint: str = "After you have finished the TIDAL login via web browser click the 'OK' button."

                while not result:
                    link_login: LinkLogin = self.tidal.session.get_link_login()
                    expires_in = int(link_login.expires_in) if hasattr(link_login, "expires_in") else 0
                    d_login: DialogLogin = DialogLogin(
                        url_login=link_login.verification_uri_complete,
                        hint=hint,
                        expires_in=expires_in,
                        parent=self,
                    )

                    if d_login.return_code == 1:
                        try:
                            self.tidal.session.process_link_login(link_login, until_expiry=False)
                            self.tidal.login_finalize()

                            result = True
                            logger_gui.info("Login successful. Have fun!")
                        except (HTTPError, Exception):
                            hint = "Something was wrong with your redirect url. Please try again!"
                            logger_gui.warning("Login not successful. Try again...")
                    else:
                        sys.exit(1)

        if result:
            self._init_dl()
            self.thread_it(self.playlist_manager.tidal_user_lists)
            # Initialize playlist membership manager
            self.init_playlist_membership_manager()

    def on_logout(self) -> None:
        """Log out from TIDAL and close the application."""
        result: bool = self.tidal.logout()
        if result:
            sys.exit(0)
