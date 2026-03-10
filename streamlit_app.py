import os
import requests
import streamlit as st

API_URL = os.environ.get("API_URL", "http://localhost:8000")

st.set_page_config(page_title="MediAssist Pro", page_icon="🧪", layout="wide")

# ── session state defaults ────────────────────────────────────────────────────
for key, default in [("token", None), ("username", None), ("role", None)]:
    if key not in st.session_state:
        st.session_state[key] = default


def auth_headers():
    return {"Authorization": f"Bearer {st.session_state.token}"}


# ── auth helpers ──────────────────────────────────────────────────────────────
def login(username, password):
    r = requests.post(f"{API_URL}/auth/login",
                      data={"username": username, "password": password})
    if r.status_code == 200:
        token = r.json()["access_token"]
        st.session_state.token = token
        me = requests.get(f"{API_URL}/auth/me",
                          headers={"Authorization": f"Bearer {token}"}).json()
        st.session_state.username = me["username"]
        st.session_state.role = me["role"]
        return True, None
    return False, r.json().get("detail", "Login failed")


def register(username, email, password):
    r = requests.post(f"{API_URL}/auth/register",
                      json={"username": username, "email": email, "password": password})
    if r.status_code == 200:
        return True, None
    return False, r.json().get("detail", "Registration failed")


# ── pages ─────────────────────────────────────────────────────────────────────
def page_login():
    st.title("MediAssist Pro")
    tab_login, tab_register = st.tabs(["Login", "Register"])

    with tab_login:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Login", use_container_width=True):
                ok, err = login(username, password)
                if ok:
                    st.rerun()
                else:
                    st.error(err)

    with tab_register:
        with st.form("register_form"):
            username = st.text_input("Username")
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Register", use_container_width=True):
                ok, err = register(username, email, password)
                if ok:
                    st.success("Registered! You can now log in.")
                else:
                    st.error(err)


def page_chat():
    st.title("Ask a Question")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    question = st.chat_input("Ask about lab equipment...")
    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                r = requests.post(f"{API_URL}/query/",
                                  json={"question": question},
                                  headers=auth_headers())
            if r.status_code == 200:
                answer = r.json()["reponse"]
                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
            else:
                err = r.json().get("detail", "Error")
                st.error(err)


def page_history():
    st.title("Query History")
    r = requests.get(f"{API_URL}/query/history", headers=auth_headers())
    if r.status_code != 200:
        st.error("Failed to load history.")
        return
    history = r.json()
    if not history:
        st.info("No queries yet.")
        return
    for item in history:
        with st.expander(f"**Q:** {item['query'][:80]}..."):
            st.markdown(f"**Question:** {item['query']}")
            st.markdown(f"**Answer:** {item['reponse']}")
            st.caption(item.get("created_at", ""))


def page_admin():
    st.title("Admin Panel")

    stats_r = requests.get(f"{API_URL}/admin/stats", headers=auth_headers())
    if stats_r.status_code == 200:
        stats = stats_r.json()
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Users", stats["total_users"])
        c2.metric("Total Queries", stats["total_queries"])
        c3.metric("Admins", stats["admin_count"])

    st.divider()
    st.subheader("Users")
    users_r = requests.get(f"{API_URL}/admin/users", headers=auth_headers())
    if users_r.status_code != 200:
        st.error("Failed to load users.")
        return
    for user in users_r.json():
        col1, col2, col3 = st.columns([3, 2, 1])
        col1.write(f"**{user['username']}** — {user['email']}")
        col2.write(user["role"])
        if user["username"] != st.session_state.username:
            if col3.button("Delete", key=f"del_{user['id']}"):
                requests.delete(f"{API_URL}/admin/users/{user['id']}",
                                headers=auth_headers())
                st.rerun()


# ── layout ────────────────────────────────────────────────────────────────────
if not st.session_state.token:
    page_login()
else:
    with st.sidebar:
        st.markdown(f"**{st.session_state.username}** ({st.session_state.role})")
        page = st.radio("Navigate", ["Chat", "History"] +
                        (["Admin"] if st.session_state.role == "admin" else []))
        st.divider()
        if st.button("Logout"):
            for key in ["token", "username", "role", "messages"]:
                st.session_state.pop(key, None)
            st.rerun()

    if page == "Chat":
        page_chat()
    elif page == "History":
        page_history()
    elif page == "Admin":
        page_admin()
