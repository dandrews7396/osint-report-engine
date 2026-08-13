from utils.auth import require_page_auth

require_page_auth()

from views.generate_report import show_generate_report

show_generate_report()
