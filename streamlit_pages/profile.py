from utils.auth import require_page_auth

require_page_auth()

from views.profile import show_profile

show_profile()
