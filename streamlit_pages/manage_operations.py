from utils.auth import require_page_auth

require_page_auth()

from views.manage_operations import show_manage_operations

show_manage_operations()
