from utils.auth import require_page_auth
from views.case_evidence import render_manager_evidence_browser


require_page_auth()
render_manager_evidence_browser()
