from utils.auth import require_page_auth

require_page_auth()

from views.risk_library import show_risk_library

show_risk_library()
