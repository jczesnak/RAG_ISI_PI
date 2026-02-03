import streamlit as st
import db_utils, rag_core, os, config
import extra_streamlit_components as stx
import time

st.set_page_config(page_title="RAG DataRoom", layout="wide")

# --- MENEDŻER CIASTECZEK ---
cookie_manager = stx.CookieManager()

# CSS
st.markdown("""
<style>
    .stApp { background-color: #0e1117; }
    .login-card { background: #1e2130; padding: 2rem; border-radius: 12px; border: 1px solid #333; }
    .stChatMessage { border-radius: 10px; padding: 10px; margin-bottom: 5px; }
</style>
""", unsafe_allow_html=True)

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'view' not in st.session_state: st.session_state.view = 'dashboard'

# --- AUTOMATYCZNE LOGOWANIE ---
if not st.session_state.logged_in:
    cookies = cookie_manager.get_all()
    if "rag_user_token" in cookies:
        st.session_state.logged_in = True
        st.session_state.user = cookies["rag_user_token"]
        st.rerun()


# --- WIDOK LOGOWANIA ---
def login_view():
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        st.title("🛡️ RAG DataRoom")
        t1, t2 = st.tabs(["Logowanie", "Rejestracja"])
        with t1:
            u = st.text_input("Użytkownik", key="l_user")
            p = st.text_input("Hasło", type="password", key="l_pass")
            if st.button("Zaloguj", use_container_width=True):
                ok, adm = db_utils.verify_user(u, p)
                if ok:
                    cookie_manager.set("rag_user_token", u, key="set_cookie_login")
                    st.session_state.logged_in = True
                    st.session_state.user = u
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("Błędne dane")
        with t2:
            nu = st.text_input("Nowy Login", key="r_user")
            np = st.text_input("Hasło", type="password", key="r_pass")
            if st.button("Stwórz konto", use_container_width=True):
                s, m = db_utils.create_user(nu, np);
                st.info(m)
        st.markdown('</div>', unsafe_allow_html=True)


# --- WIDOK DASHBOARD ---
def dashboard_view(user):
    st.title("Centrum Projektów")

    c1, c2, c3 = st.columns([6, 1, 1])
    if c2.button("📜 Historia", use_container_width=True): st.session_state.view = 'history'; st.rerun()
    if c3.button("🚪 Wyjdź", use_container_width=True):
        cookie_manager.delete("rag_user_token")
        st.session_state.clear()
        time.sleep(0.5)
        st.rerun()

    all_cols = db_utils.get_accessible_collections(user)
    # Krotki: (id, name, owner_username)
    owned_cols = [c for c in all_cols if c[2] == user]
    shared_cols = [c for c in all_cols if c[2] != user]

    tab1, tab2 = st.tabs([f"Twoje Kolekcje ({len(owned_cols)})", f"Współdzielone ze mną ({len(shared_cols)})"])

    # --- ZAKŁADKA 1: TWOJE KOLEKCJE ---
    with tab1:
        if st.button("➕ Utwórz nowy projekt", use_container_width=True):
            st.session_state.view = 'create_col'
            st.rerun()

        if not owned_cols: st.info("Nie masz jeszcze własnych projektów.")

        grid = st.columns(3)
        for i, (cid, name, owner) in enumerate(owned_cols):
            with grid[i % 3]:
                with st.container(border=True):
                    c_head, c_del = st.columns([5, 1])
                    c_head.subheader(f"📁 {name}")
                    c_head.caption(f"👤 Właściciel: **{owner}**")

                    if c_del.button("❌", key=f"del_{cid}", help="Usuń cały projekt"):
                        db_utils.delete_collection(cid)
                        st.rerun()

                    # --- ZARZĄDZANIE PLIKAMI (Dla Właściciela) ---
                    files = db_utils.get_collection_files(cid)
                    with st.expander(f"📄 Pliki ({len(files)})"):
                        for f in files:
                            f1, f2 = st.columns([4, 1])
                            f1.write(f)
                            if f2.button("🗑️", key=f"f_{cid}_{f}"):
                                rag_core.delete_file_from_storage(owner, f)
                                db_utils.remove_file_from_collection(cid, f)
                                st.rerun()

                        st.write("---")
                        new_files = st.file_uploader("Dodaj pliki", accept_multiple_files=True, key=f"up_{cid}")
                        if new_files and st.button("Wgraj", key=f"btn_up_{cid}"):
                            with st.spinner("Przetwarzanie..."):
                                for nf in new_files:
                                    path = os.path.join(config.TEMP_UPLOAD_DIR, nf.name)
                                    os.makedirs(config.TEMP_UPLOAD_DIR, exist_ok=True)
                                    with open(path, "wb") as bf: bf.write(nf.getvalue())
                                    # Procesujemy jako właściciel (owner)
                                    rag_core.process_file(path, nf.name, owner)
                                    db_utils.add_file_to_collection(cid, nf.name)
                                st.success("Dodano!")
                                time.sleep(0.5)
                                st.rerun()

                    with st.expander("📤 Udostępnianie"):
                        target_u = st.text_input("Dodaj login", key=f"share_in_{cid}")
                        if st.button("Dodaj", key=f"share_btn_{cid}"):
                            ok, msg = db_utils.share_collection_with_user(user, cid, target_u)
                            if ok:
                                st.success(msg); st.rerun()
                            else:
                                st.error(msg)

                        st.write("---")
                        st.caption("Mają dostęp:")
                        permitted_users = db_utils.get_collection_permissions(cid)
                        if not permitted_users:
                            st.caption("(Tylko Ty)")
                        else:
                            for pu in permitted_users:
                                p1, p2 = st.columns([4, 1])
                                p1.write(f"👤 {pu}")
                                if p2.button("❌", key=f"revoke_{cid}_{pu}", help="Zabierz dostęp"):
                                    db_utils.revoke_permission(cid, pu)
                                    st.rerun()

                    if st.button("💬 Czat", key=f"open_{cid}", use_container_width=True):
                        st.session_state.active_col = (cid, name)
                        st.session_state.messages = db_utils.load_active_chat(cid, user)
                        st.session_state.view = 'chat'
                        st.rerun()

    # --- ZAKŁADKA 2: WSPÓŁDZIELONE ---
    with tab2:
        if not shared_cols: st.info("Brak udostępnionych projektów.")
        grid_s = st.columns(3)
        for i, (cid, name, owner) in enumerate(shared_cols):
            with grid_s[i % 3]:
                with st.container(border=True):
                    st.subheader(f"📂 {name}")
                    st.caption(f"👤 Właściciel: **{owner}**")

                    # --- ZARZĄDZANIE PLIKAMI (Dla Gościa) ---
                    files = db_utils.get_collection_files(cid)
                    with st.expander(f"📄 Pliki ({len(files)})"):
                        for f in files:
                            f1, f2 = st.columns([4, 1])
                            f1.write(f)
                            if f2.button("🗑️", key=f"sh_del_{cid}_{f}"):
                                rag_core.delete_file_from_storage(owner, f)
                                db_utils.remove_file_from_collection(cid, f)
                                st.rerun()

                        st.write("---")
                        guest_files = st.file_uploader("Dodaj pliki", accept_multiple_files=True, key=f"sh_up_{cid}")
                        if guest_files and st.button("Wgraj", key=f"btn_sh_up_{cid}"):
                            with st.spinner("Wgrywanie do projektu właściciela..."):
                                for gf in guest_files:
                                    path = os.path.join(config.TEMP_UPLOAD_DIR, gf.name)
                                    os.makedirs(config.TEMP_UPLOAD_DIR, exist_ok=True)
                                    with open(path, "wb") as bf: bf.write(gf.getvalue())
                                    # TU JEST MAGIA: Zapisujemy wektory jako 'owner'
                                    rag_core.process_file(path, gf.name, owner)
                                    db_utils.add_file_to_collection(cid, gf.name)
                                st.success("Dodano plik do współdzielonego projektu!")
                                time.sleep(0.5)
                                st.rerun()

                    b_join, b_leave = st.columns([3, 1])
                    with b_join:
                        if st.button("💬 Dołącz", key=f"open_shared_{cid}", use_container_width=True):
                            st.session_state.active_col = (cid, name)
                            st.session_state.messages = db_utils.load_active_chat(cid, user)
                            st.session_state.view = 'chat'
                            st.rerun()
                    with b_leave:
                        if st.button("🚪", key=f"leave_{cid}", help="Opuść ten projekt"):
                            db_utils.revoke_permission(cid, user)
                            st.success("Opuszczono projekt.")
                            time.sleep(0.5)
                            st.rerun()


# --- WIDOK KREATORA ---
def create_view(user):
    st.title("🛠️ Nowy Projekt")
    name = st.text_input("Nazwa projektu")
    t1, t2 = st.tabs(["Z bazy", "Wgraj nowe"])

    with t1:
        existing = rag_core.get_all_user_files(user)
        selected = []
        if not existing:
            st.info("Brak wgranych plików w bazie.")
        else:
            for f in existing:
                c1, c2 = st.columns([0.85, 0.15])
                with c1:
                    if st.checkbox(f, key=f"ex_{f}"):
                        selected.append(f)
                with c2:
                    if st.button("🗑️", key=f"del_g_{f}", help="Usuń trwale z bazy"):
                        rag_core.delete_file_from_storage(user, f)
                        st.rerun()

    with t2:
        up = st.file_uploader("Dodaj pliki", accept_multiple_files=True)

    if st.button("🚀 Utwórz"):
        with st.spinner("Przetwarzanie..."):
            all_f = selected.copy()
            if up:
                for f in up:
                    path = os.path.join(config.TEMP_UPLOAD_DIR, f.name)
                    os.makedirs(config.TEMP_UPLOAD_DIR, exist_ok=True)
                    with open(path, "wb") as bf: bf.write(f.getvalue())
                    rag_core.process_file(path, f.name, user)
                    all_f.append(f.name)
            db_utils.create_collection(name, user, all_f)
            st.session_state.view = 'dashboard';
            st.rerun()
    if st.button("Anuluj"): st.session_state.view = 'dashboard'; st.rerun()


# --- WIDOK CZATU ---
def chat_view(user):
    cid, name = st.session_state.active_col
    st.title(f"💬 Czat: {name}")

    b1, b2 = st.columns([1, 1])
    with b1:
        if st.button("⬅️ Wróć (Zachowaj)", use_container_width=True):
            db_utils.save_active_chat(cid, user, st.session_state.messages)
            st.session_state.view = 'dashboard'
            st.rerun()
    with b2:
        if st.button("🏁 Zakończ i Archiwizuj", use_container_width=True):
            if st.session_state.messages:
                db_utils.archive_chat(cid, user, st.session_state.messages)
                st.success("Zarchiwizowano!")
                time.sleep(1)
            st.session_state.view = 'dashboard'
            st.rerun()

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    p = st.chat_input("Zadaj pytanie...")

    if p:
        st.session_state.messages.append({"role": "user", "content": p})
        with st.chat_message("user"):
            st.markdown(p)

        with st.chat_message("assistant"):
            with st.spinner("Generowanie odpowiedzi..."):
                chain = rag_core.get_collection_chain(cid)
                if chain:
                    response = chain.invoke(p)
                    st.markdown(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    db_utils.save_active_chat(cid, user, st.session_state.messages)
                else:
                    st.error("Błąd: Nie można połączyć się z modelem RAG dla tej kolekcji.")


# --- WIDOK HISTORII ---
def history_view(user):
    c1, c2 = st.columns([4, 1])
    c1.title("📜 Historia Rozmów")

    if c2.button("⬅️ Wróć", use_container_width=True):
        st.session_state.view = 'dashboard'
        st.rerun()

    if st.button("🔥 Usuń całą historię", help="To działanie jest nieodwracalne!"):
        db_utils.delete_all_user_archives(user)
        st.success("Wyczyszczono historię.")
        st.rerun()

    archives = db_utils.get_user_history(user)

    if not archives:
        st.info("Brak zarchiwizowanych rozmów.")
    else:
        st.write("---")
        selected_ids = []
        for aid, name, date in archives:
            with st.container(border=True):
                col_check, col_info, col_btn = st.columns([0.5, 4, 1])
                with col_check:
                    if st.checkbox("", key=f"sel_arch_{aid}"):
                        selected_ids.append(aid)
                with col_info:
                    st.write(f"**Projekt: {name}**")
                    st.caption(f"Data: {date.strftime('%Y-%m-%d %H:%M')}")
                with col_btn:
                    if st.button("👁️", key=f"arch_{aid}", help="Zobacz szczegóły"):
                        st.session_state.selected_arch_id = aid
                        st.session_state.view = 'history_detail'
                        st.rerun()

        if selected_ids:
            st.write("---")
            if st.button(f"🗑️ Usuń zaznaczone ({len(selected_ids)})"):
                db_utils.delete_selected_archives(selected_ids)
                st.success("Usunięto wybrane rozmowy.")
                time.sleep(0.5)
                st.rerun()


# --- WIDOK SZCZEGÓŁÓW HISTORII ---
def history_detail_view():
    st.title("📖 Podgląd Rozmowy")
    if st.button("⬅️ Powrót do listy"): st.session_state.view = 'history'; st.rerun()

    messages = db_utils.get_archive_detail(st.session_state.selected_arch_id)
    st.warning("To jest widok archiwalny - nie możesz kontynuować tej rozmowy.")
    for m in messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])


# --- ROUTER ---
if not st.session_state.logged_in:
    login_view()
else:
    v = st.session_state.view
    if v == 'dashboard':
        dashboard_view(st.session_state.user)
    elif v == 'create_col':
        create_view(st.session_state.user)
    elif v == 'chat':
        chat_view(st.session_state.user)
    elif v == 'history':
        history_view(st.session_state.user)
    elif v == 'history_detail':
        history_detail_view()