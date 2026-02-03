import streamlit as st
import os
import sys
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_ollama import OllamaLLM
from langchain_ollama.embeddings import OllamaEmbeddings
from langchain_postgres.vectorstores import PGVector

# Importy do ładowania i dzielenia dokumentów
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter  # Poprawiony import

# --- 1. Konfiguracja (Stałe) ---

CONNECTION_STRING = "postgresql+psycopg2://postgres:1234@localhost:5433/Baza"
COLLECTION_NAME = "rag_app_docs"

# Inicjalizacja modeli
try:
    embeddings = OllamaEmbeddings(model="nomic-embed-text")
    llm = OllamaLLM(model="llama2")
    print("INFO: Modele Ollama załadowane pomyślnie.")
except Exception as e:
    st.error(f"KRYTYCZNY BŁĄD: Nie można połączyć się z Ollama. Upewnij się, że jest uruchomiona. Błąd: {e}")
    sys.exit()


# --- 2. Funkcja do przetwarzania i indeksowania pliku ---

def process_and_embed_file(file_path):
    """Wczytuje PDF, dzieli go i zapisuje wektory w bazie danych."""

    st.info("Krok 1/4: Wczytywanie dokumentu PDF...")
    loader = PyPDFLoader(file_path)
    docs = loader.load()

    if not docs:
        st.error("Nie udało się wczytać żadnych stron z tego PDFa.")
        return False

    st.info(f"Krok 2/4: Dzielenie tekstu na fragmenty (załadowano {len(docs)} stron)...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = text_splitter.split_documents(docs)

    if not chunks:
        st.error("Nie udało się wyodrębnić tekstu z tego PDFa.")
        return False

    st.info("Krok 3/4: Tworzenie połączenia z bazą wektorową...")
    try:
        vectorstore = PGVector(
            connection=CONNECTION_STRING,
            embeddings=embeddings,
            collection_name=COLLECTION_NAME,
            create_extension=False
        )

        st.info("Krok 3.5/4: Czyszczenie starej kolekcji (jeśli istnieje)...")
        vectorstore.delete_collection()

        # --- !!! POPRAWKA TUTAJ !!! ---
        st.info("Krok 3.6/4: Tworzenie nowej, pustej kolekcji...")
        vectorstore.create_collection()
        # --- ---------------------- ---

        st.info(f"Krok 4/4: Dodawanie {len(chunks)} fragmentów tekstu do bazy...")
        vectorstore.add_documents(documents=chunks)

        return True
    except Exception as e:
        st.error(f"Wystąpił błąd podczas dodawania dokumentów do bazy: {e}")
        import traceback
        traceback.print_exc()
        return False


# --- 3. Główny Interfejs Streamlit ---
st.title("Lokalny System RAG 🤖📄")
st.markdown("Wgraj dokument PDF, aby móc zadawać mu pytania.")

# --- Panel Boczny (Sidebar) do wgrywania plików ---
with st.sidebar:
    st.header("1. Wgraj Dokument")
    uploaded_file = st.file_uploader("Wybierz plik PDF...", type=["pdf"])

    if uploaded_file:
        temp_dir = "temp_uploads"
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, uploaded_file.name)

        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getvalue())

        st.info("Rozpoczynanie przetwarzania pliku...")

        file_id = f"processed_{uploaded_file.name}"

        if file_id not in st.session_state:
            with st.spinner("Przetwarzanie pliku... (ładowanie, dzielenie, embedding)"):
                success = process_and_embed_file(temp_path)
                if success:
                    st.session_state[file_id] = True
                    st.session_state['file_ready'] = True
                    st.success(f"Plik '{uploaded_file.name}' jest gotowy!")
                else:
                    st.error("Przetwarzanie pliku nie powiodło się.")
        else:
            st.success(f"Plik '{uploaded_file.name}' został już przetworzony.")
            st.session_state['file_ready'] = True

# --- Główny Interfejs (Czat) ---
st.header("2. Zadaj Pytanie")

user_question = st.text_input("Twoje pytanie:", placeholder="np. Kto jest klientem na fakturze 456?")

if st.button("Wyślij Pytanie"):
    if not st.session_state.get('file_ready'):
        st.error("Proszę najpierw wgrać i przetworzyć dokument w panelu bocznym.")
    elif not user_question:
        st.warning("Proszę wpisać pytanie.")
    else:
        with st.spinner("Myślę... 🧠 (Przeszukuję bazę i generuję odpowiedź)"):
            try:
                vectorstore_read = PGVector(
                    connection=CONNECTION_STRING,
                    embeddings=embeddings,
                    collection_name=COLLECTION_NAME,
                    create_extension=False
                )

                retriever = vectorstore_read.as_retriever(search_kwargs={'k': 3})

                template = """
                Odpowiedz na pytanie bazując wyłącznie na poniższym kontekście.
                Jeśli kontekst nie zawiera odpowiedzi, napisz "Nie wiem".

                Kontekst:
                {context}

                Pytanie:
                {question}
                """
                prompt = ChatPromptTemplate.from_template(template)

                chain = (
                        {"context": retriever, "question": RunnablePassthrough()}
                        | prompt
                        | llm
                        | StrOutputParser()
                )

                response = chain.invoke(user_question)
                st.success("Odpowiedź wygenerowana:")
                st.markdown(response)

            except Exception as e:
                st.error(f"Wystąpił błąd podczas generowania odpowiedzi: {e}")
                import traceback

                traceback.print_exc()