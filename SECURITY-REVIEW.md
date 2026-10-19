# Streamlit Dependency Security Review

Reviewed: 2026-09-25

## Scope

This review covers the Streamlit version pinned in `requirements.txt`:

```text
streamlit==1.42.0
```

## Findings

| Severity | Dependency | Finding | Resolution |
| --- | --- | --- | --- |
| High | Streamlit 1.42.0 | On Windows, versions before 1.54.0 can resolve attacker-controlled UNC paths through component endpoints, creating an unauthenticated SSRF/NTLM exposure when the app is attacker reachable. | Upgrade to Streamlit 1.54.0 or later. |
| Medium | Streamlit 1.42.0 | Versions before 1.53.1 have a cache hash-collision weakness. Exploitation requires local, low-privilege access and high attack complexity. | Upgrade to Streamlit 1.53.1 or later. |

## Recommendation

Upgrade to `streamlit==1.55.0`. It includes fixes for both findings and provides the
stateful expander API needed for a native accordion implementation. The review found
no disclosed Streamlit-core vulnerability affecting 1.55.0 as of the review date.

## References

- [GHSA-7p48-42j8-8846](https://github.com/streamlit/streamlit/security/advisories/GHSA-7p48-42j8-8846)
- [GHSA-vqwp-45wm-r9r5](https://github.com/advisories/GHSA-vqwp-45wm-r9r5)
- [GHSA-rxff-vr5r-8cj5](https://github.com/streamlit/streamlit/security/advisories/GHSA-rxff-vr5r-8cj5)
