from utils.auth import require_page_auth

require_page_auth()

from views.templates import show_templates

show_templates()
