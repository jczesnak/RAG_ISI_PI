import os, config, db_utils, uuid
from langchain_postgres.vectorstores import PGVector
from langchain_ollama import OllamaLLM, OllamaEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

embeddings = OllamaEmbeddings(model=config.EMBEDDING_MODEL)
llm = OllamaLLM(model=config.LLM_MODEL, temperature=0.1)

# Pojedyncza globalna instancja vector store
_vector_store = None


def get_vector_store():
    global _vector_store
    if _vector_store is None:
        _vector_store = PGVector(
            connection=config.DATABASE_URL,
            embeddings=embeddings,
            collection_name=config.COLLECTION_NAME,
            use_jsonb=True
        )
    return _vector_store


def process_file(path, name, user):
    try:
        loader = PyPDFLoader(path) if name.lower().endswith('.pdf') else TextLoader(path, encoding='utf-8')
        docs = loader.load()
        splitter = RecursiveCharacterTextSplitter(chunk_size=config.CHUNK_SIZE, chunk_overlap=config.CHUNK_OVERLAP)
        chunks = splitter.split_documents(docs)

        if not chunks:
            return False

        texts = []
        metadatas = []
        ids = []

        for c in chunks:
            texts.append(c.page_content)
            metadatas.append({"username": user, "source_file": name})
            ids.append(str(uuid.uuid4()))

        # Użyj pojedynczej instancji
        vs = get_vector_store()
        vs.add_texts(texts=texts, metadatas=metadatas, ids=ids)
        return True

    except Exception as e:
        print(f"Błąd przetwarzania pliku {name}: {e}")
        return False


def get_collection_chain(cid):
    files = db_utils.get_collection_files(cid)
    if not files:
        return None

    sql_filter = {"source_file": {"$in": files}}
    retriever = get_vector_store().as_retriever(search_kwargs={'filter': sql_filter, 'k': 15})

    template = """[INST] <<SYS>> Jesteś ekspertem analizującym dokumenty. Odpowiadaj TYLKO po polsku. Jak nie mozesz znalezc informacji to pisz "nie wiem"
Zawsze wskazuj nazwę pliku źródłowego. <</SYS>>
KONTEKST: {context}
PYTANIE: {question} [/INST]"""

    def format_docs(docs):
        return "\n\n".join([f"--- PLIK: {d.metadata['source_file']} ---\n{d.page_content}" for d in docs])

    return (
            {"context": retriever | format_docs, "question": RunnablePassthrough()}
            | ChatPromptTemplate.from_template(template)
            | llm
            | StrOutputParser()
    )


def get_all_user_files(user):
    try:
        conn = db_utils.get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT cmetadata ->> 'source_file' FROM langchain_pg_embedding WHERE cmetadata ->> 'username' = %s",
            (user,))
        res = [r[0] for r in cur.fetchall()]
        conn.close()
        return res
    except Exception as e:
        print(f"Błąd pobierania plików: {e}")
        return []


def delete_file_from_storage(user, filename):
    try:
        conn = db_utils.get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM langchain_pg_embedding WHERE cmetadata ->> 'source_file' = %s AND cmetadata ->> 'username' = %s",
            (filename, user)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Błąd usuwania pliku: {e}")
        return False