from utils.auth import require_page_auth

require_page_auth()

from views.settings import show_settings

show_settings()
