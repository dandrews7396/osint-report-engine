from utils.auth import require_page_auth
from views.review_reports import show_review_reports


require_page_auth()
show_review_reports()
