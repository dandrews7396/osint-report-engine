from utils.auth import require_page_auth

require_page_auth()

from views.dashboard import show_dashboard

show_dashboard()
