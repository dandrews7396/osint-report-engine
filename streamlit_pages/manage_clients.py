from utils.auth import require_page_auth

require_page_auth()

from views.manage_clients import show_manage_clients

show_manage_clients()
