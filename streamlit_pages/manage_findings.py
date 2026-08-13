from utils.auth import require_page_auth

require_page_auth()

from views.manage_findings import show_manage_findings

show_manage_findings()
