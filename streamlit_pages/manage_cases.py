from utils.auth import require_page_auth

require_page_auth()

from views.manage_cases import show_manage_cases

show_manage_cases()
