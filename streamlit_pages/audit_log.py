from utils.auth import require_admin_page_auth
from views.audit_log import show_audit_log


require_admin_page_auth()
show_audit_log()
