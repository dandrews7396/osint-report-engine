from utils.auth import require_page_auth

require_page_auth()

from views.manage_tasks import show_manage_tasks

show_manage_tasks()
