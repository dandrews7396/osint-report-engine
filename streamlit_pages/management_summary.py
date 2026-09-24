from utils.auth import require_page_auth
from views.management_summary import show_management_summary


require_page_auth()
show_management_summary()
