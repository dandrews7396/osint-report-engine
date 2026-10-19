from utils.auth import require_page_auth

require_page_auth()

from views.manage_subjects import show_manage_subjects

show_manage_subjects()
