from utils.auth import require_page_auth

require_page_auth()

from views.admin import show_admin_users

show_admin_users()
