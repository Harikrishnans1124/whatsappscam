"""Streamlit Admin Dashboard for TrustShop AI.

Allows administrators to:
1. Inspect the official brand registry and sources.
2. Add new brands and update/re-verify existing brands with mandatory source URL and verification date.
3. Monitor registry freshness and identify stale entries (> 90 days).
4. Review community reports queue and distinct reporter counts.
"""

import datetime as dt
import os

import requests
import streamlit as st

# Page Configuration
st.set_page_config(
    page_title="TrustShop AI - Admin Dashboard",
    page_icon="🛡️",
    layout="wide",
)

st.title("🛡️ TrustShop AI — Admin Control Center")

# Sidebar Configuration
st.sidebar.header("⚙️ Configuration")
api_base_url = st.sidebar.text_input(
    "API Base URL",
    value=os.getenv("API_BASE_URL", "http://localhost:8000"),
    help="Target TrustShop AI backend API server",
)
admin_api_key = st.sidebar.text_input(
    "Admin API Key (X-API-Key)",
    value=os.getenv("ADMIN_API_KEY", "dev-admin-key-change-me"),
    type="password",
    help="Secret key required for administrative write and review operations",
)

headers = {
    "X-API-Key": admin_api_key,
    "Content-Type": "application/json",
}

# Health Check
try:
    health_resp = requests.get(f"{api_base_url}/healthz", timeout=3)
    if health_resp.status_code == 200:
        st.sidebar.success("🟢 API Server Connected")
    else:
        st.sidebar.warning(f"🟡 API Server returned HTTP {health_resp.status_code}")
except Exception as e:  # noqa: BLE001
    st.sidebar.error(f"🔴 API Server Offline ({e})")

# Navigation Tabs
tab1, tab2, tab3, tab4 = st.tabs(
    ["📋 Brand Registry", "➕ Add / Update Brand", "⏰ Stale Entries & Freshness", "🚨 Reports Queue"]
)

# -------------------------------------------------------------
# TAB 1: Brand Registry
# -------------------------------------------------------------
with tab1:
    st.subheader("Official Brand Registry")
    st.write("Browse official verified brands, domains, helplines, and source audit trails.")

    try:
        resp = requests.get(f"{api_base_url}/v1/brands", timeout=5)
        if resp.status_code == 200:
            brands = resp.json()
            st.metric("Total Registered Brands", len(brands))

            search = st.text_input("🔍 Search Brand by Name or Slug", "")
            filtered = [
                b for b in brands
                if search.lower() in b["name"].lower() or search.lower() in b["slug"].lower()
            ] if search else brands

            for b in filtered:
                with st.expander(f"**{b['name']}** (`{b['slug']}`)", expanded=False):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**Official Domains:**")
                        for d in b.get("official_domains", []):
                            st.write(f"- `{d}`")
                        st.markdown("**Official Phones:**")
                        phones = b.get("official_phones", [])
                        if phones:
                            for p in phones:
                                st.write(f"- `{p}`")
                        else:
                            st.write("*(None published)*")
                    with col2:
                        st.markdown("**Payment Policy:**")
                        st.write(b.get("payment_policy") or "*(No specific policy)*")
                        st.markdown("**Verified Sources:**")
                        for src in b.get("sources", []):
                            st.write(f"- [{src['url']}]({src['url']}) (Verified: `{src['verified_on']}`)")
        else:
            st.error(f"Failed to fetch brands: HTTP {resp.status_code}")
    except Exception as exc:  # noqa: BLE001
        st.error(f"Error fetching brands: {exc}")

# -------------------------------------------------------------
# TAB 2: Add / Update Brand
# -------------------------------------------------------------
with tab2:
    st.subheader("Add or Update Brand Entry")
    st.write("Mandatory Rule: Every brand entry must include at least one official source URL and a verified_on date.")

    with st.form("brand_form", clear_on_submit=False):
        col_a, col_b = st.columns(2)
        with col_a:
            slug = st.text_input("Brand Slug *", placeholder="e.g. apple-india").strip().lower()
            name = st.text_input("Brand Name *", placeholder="e.g. Apple India").strip()
            aliases = st.text_input("Aliases (comma separated)", placeholder="e.g. Apple, Apple Store")
            legal_names = st.text_input("Legal Entity Names (comma separated)", placeholder="e.g. Apple India Private Limited")
        with col_b:
            domains = st.text_input("Official Domains * (comma separated)", placeholder="e.g. apple.com, apple.com/in")
            phones = st.text_input("Official Phones (comma separated, E.164)", placeholder="e.g. +91 1800 165 4321")
            payment_policy = st.text_area("Payment Policy", placeholder="e.g. Pays only through official web checkout. Never asks for UPI transfer.")

        st.markdown("#### 📜 Source Verification (Mandatory)")
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            source_url = st.text_input("Source URL *", placeholder="e.g. https://www.apple.com/in/contact/")
        with col_s2:
            verified_date = st.date_input("Verified Date *", value=dt.datetime.now(dt.UTC).date())

        is_update = st.checkbox("This is an update to an existing brand", value=False)
        submitted = st.form_submit_button("💾 Save Brand Entry")

        if submitted:
            if not slug or not name:
                st.error("Slug and Name are required.")
            elif not domains:
                st.error("At least one official domain is required.")
            elif not source_url:
                st.error("Source URL is required to prevent registry poisoning.")
            else:
                payload = {
                    "slug": slug,
                    "name": name,
                    "aliases": [a.strip() for a in aliases.split(",") if a.strip()],
                    "legal_names": [ln.strip() for ln in legal_names.split(",") if ln.strip()],
                    "official_domains": [d.strip().lower() for d in domains.split(",") if d.strip()],
                    "official_phones": [p.strip() for p in phones.split(",") if p.strip()],
                    "payment_policy": payment_policy.strip(),
                    "sources": [
                        {
                            "url": source_url.strip(),
                            "verified_on": verified_date.isoformat(),
                        }
                    ],
                }

                try:
                    if is_update:
                        resp = requests.put(
                            f"{api_base_url}/v1/admin/brands/{slug}",
                            json=payload,
                            headers=headers,
                            timeout=5,
                        )
                    else:
                        resp = requests.post(
                            f"{api_base_url}/v1/admin/brands",
                            json=payload,
                            headers=headers,
                            timeout=5,
                        )

                    if resp.status_code in (200, 201):
                        action = "updated" if is_update else "created"
                        st.success(f"✅ Brand '{name}' successfully {action}!")
                    elif resp.status_code == 403:
                        st.error("❌ Forbidden: Admin API key is invalid.")
                    else:
                        st.error(f"❌ Error ({resp.status_code}): {resp.text}")
                except Exception as ex:  # noqa: BLE001
                    st.error(f"Request failed: {ex}")

# -------------------------------------------------------------
# TAB 3: Stale Entries & Freshness
# -------------------------------------------------------------
with tab3:
    st.subheader("Registry Freshness & Stale Audit Check")
    st.write("Brands verified more than 90 days ago require re-verification to prevent stale data.")

    max_days = st.slider("Stale Threshold (Days)", min_value=30, max_value=180, value=90)

    try:
        resp = requests.get(
            f"{api_base_url}/v1/admin/freshness?max_age_days={max_days}",
            headers=headers,
            timeout=5,
        )
        if resp.status_code == 200:
            freshness_data = resp.json()
            stale_items = [f for f in freshness_data if f.get("is_stale")]
            fresh_items = [f for f in freshness_data if not f.get("is_stale")]

            col_m1, col_m2 = st.columns(2)
            col_m1.metric("Fresh Brands (Verified < 90d)", len(fresh_items))
            col_m2.metric("Stale Brands (Needs Audit)", len(stale_items), delta=-len(stale_items) if stale_items else 0)

            if stale_items:
                st.warning(f"⚠️ Found {len(stale_items)} brand(s) pending re-verification!")
                for s in stale_items:
                    st.write(
                        f"- **{s['name']}** (`{s['slug']}`): Last verified `{s['latest_verified_on']}` ({s['age_days']} days ago)"
                    )
            else:
                st.success("🎉 All registered brands are freshly verified within the threshold.")

            st.dataframe(
                freshness_data,
                use_container_width=True,
                column_config={
                    "slug": "Slug",
                    "name": "Brand",
                    "latest_verified_on": "Last Verified Date",
                    "age_days": "Age (Days)",
                    "is_stale": "Stale?",
                    "status": "Status",
                },
            )
        elif resp.status_code == 403:
            st.error("❌ Forbidden: Admin API key is required to view freshness.")
        else:
            st.error(f"Failed to fetch freshness report: HTTP {resp.status_code}")
    except Exception as exc:  # noqa: BLE001
        st.error(f"Error fetching freshness report: {exc}")

# -------------------------------------------------------------
# TAB 4: Reports Queue
# -------------------------------------------------------------
with tab4:
    st.subheader("Community Crowd Reports Queue")
    st.write("Aggregated reports submitted by shoppers. Identifiers are cryptographically anonymized via HMAC-SHA256.")

    try:
        resp = requests.get(
            f"{api_base_url}/v1/admin/reports?limit=100",
            headers=headers,
            timeout=5,
        )
        if resp.status_code == 200:
            reports = resp.json()
            if not reports:
                st.info("No community reports recorded yet.")
            else:
                st.metric("Total Reported Identifiers", len(reports))
                for rep in reports:
                    with st.expander(
                        f"**{rep['identifier_type'].upper()}**: `{rep['identifier_hash'][:16]}...` — {rep['distinct_reporters']} distinct reporter(s)"
                    ):
                        st.write(f"- **Identifier Type:** `{rep['identifier_type']}`")
                        st.write(f"- **HMAC Identifier Hash:** `{rep['identifier_hash']}`")
                        st.write(f"- **Distinct Reporters:** `{rep['distinct_reporters']}`")
                        st.write(f"- **Total Reports:** `{rep['total_reports']}`")
                        st.write(f"- **Category:** `{rep['category']}`")
                        st.write(f"- **Latest Report:** `{rep['latest_report_at']}`")
                        if rep.get("notes"):
                            st.write("**Reporter Notes:**")
                            for note in rep["notes"]:
                                st.write(f"  • \"{note}\"")
        elif resp.status_code == 403:
            st.error("❌ Forbidden: Admin API key is required to review reports queue.")
        else:
            st.error(f"Failed to fetch reports queue: HTTP {resp.status_code}")
    except Exception as exc:  # noqa: BLE001
        st.error(f"Error fetching reports queue: {exc}")
