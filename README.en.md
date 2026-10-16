[🇵🇱 Polski](README.md) | **🇬🇧 English**

# RAG Project – Installation and Setup Guide

## Requirements

Before running the app you need three things installed:

| Program                     | Purpose                                                  | Download                                                        |
| :-------------------------- | :------------------------------------------------------- | :-------------------------------------------------------------- |
| **Python 3.11**             | Running the application and managing scripts             | [python.org/downloads](https://www.python.org/downloads/)       |
| **PostgreSQL (w/ pgvector)** | Main database and vector storage                        | [postgresql.org/download](https://www.postgresql.org/download/) |
| **Ollama**                  | Running and serving large language models (LLMs) locally | [ollama.com/download](https://ollama.com/download)              |

---

## Specification – software versions

The project was developed and tested with the versions below. Other versions may work but have not been tested.

### Programs

| Program        | Version      |
| :------------- | :----------- |
| Python         | **3.11**     |
| PostgreSQL     | **17**       |
| pgvector       | **0.8.0**    |
| Ollama         | **0.31.2**   |

### Models (Ollama)

| Model                                         | Role                                    | Size    |
| :-------------------------------------------- | :-------------------------------------- | :------ |
| `SpeakLeash/bielik-11b-v2.3-instruct:Q4_K_M`  | Language model (Bielik 11B v2.3, Q4_K_M quantization) | ~7 GB |
| `nomic-embed-text` (tag `latest`)             | Embedding model (768-dimensional vectors) | ~274 MB |

### Main Python libraries

| Library                      | Version  |
| :--------------------------- | :------- |
| streamlit                    | 1.52.2   |
| extra-streamlit-components   | 0.1.81   |
| langchain-core               | 1.2.6    |
| langchain-community          | 0.4.1    |
| langchain-classic            | 1.0.1    |
| langchain-text-splitters     | 1.1.0    |
| langchain-ollama             | 1.0.1    |
| langchain-postgres           | 0.0.16   |
| ollama                       | 0.6.1    |
| pgvector                     | 0.3.6    |
| SQLAlchemy                   | 2.0.45   |
| psycopg2                     | 2.9.11   |
| psycopg / psycopg-binary     | 3.3.2    |
| pypdf                        | 6.5.0    |
| bcrypt                       | 5.0.0    |
| python-dotenv                | 1.2.1    |

The full list of dependencies with exact versions is in [requirements.txt](requirements.txt).

---

## Step-by-step configuration

### 1. PostgreSQL database

After installing PostgreSQL, create the database and enable the `pgvector` extension.

In **pgAdmin** (Query Tool) or **psql**, run:

```sql
CREATE DATABASE rag_project_db;
```

![Creating the database](img/create_database.png)

Then **connect to the `rag_project_db` database** and run:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

![Creating the vector extension](img/create_extension.png)

> If you get the error `could not open extension control file ... vector` at this point,
> it means the **pgvector** extension is not installed. See the
> [Installing pgvector](#installing-pgvector-if-missing) section at the end of this file.

> The application creates its tables automatically on first run – you don't need to create them manually.

### 2. Set the database credentials

Open **`config.py`** and put **your** PostgreSQL password and port in the `DATABASE_URL` line:

```python
DATABASE_URL="postgresql+psycopg2://postgres:YOUR_PASSWORD@localhost:5433/rag_project_db"
```

- `postgres` – database user name
- `YOUR_PASSWORD` – the password you set when installing PostgreSQL
- `5433` – database port. **Note:** a default PostgreSQL install usually runs on `5432` –
  if you didn't change the port during installation, use `5432`.

> ⚠️ Most common error: `password authentication failed` (in Polish:
> `autoryzacja hasłem nie powiodła się`) – it means the password in `config.py`
> doesn't match your PostgreSQL password. Fix it here.

### 3. Ollama models

Make sure Ollama is running (tray icon), then pull both models:

```powershell
ollama pull nomic-embed-text
ollama pull SpeakLeash/bielik-11b-v2.3-instruct:Q4_K_M
```

![Pulling the embedding model](img/pull_nomic.png)
![Pulling Bielik](img/pull_bielik.png)

Verify with `ollama list` – both models should be listed.

(Bielik is ~7 GB, so the download will take a while.)

While running the commands above you may get this error:

```powershell
ollama : The term 'ollama' is not recognized as the name of a cmdlet, function, script file, or operable program. Check
 the spelling of the name, or if a path was included, verify that the path is correct and try again.
At line:1 char:1
+ ollama pull nomic-embed-text
+ ~~~~~~
    + CategoryInfo          : ObjectNotFound: (ollama:String) [], CommandNotFoundException
    + FullyQualifiedErrorId : CommandNotFoundException
```

Check whether Ollama is installed with:

```powershell
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" --version
```

You should see the Ollama version:

```powershell
ollama version is 0.31.2
```

If no version is shown, Ollama needs to be installed:

```powershell
irm https://ollama.com/install.ps1 | iex
```

Now add Ollama to your PATH:

```powershell
$env:Path += ";$env:LOCALAPPDATA\Programs\Ollama"
```

---

## Running the app

### Manually in a terminal (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

![Starting the application](img/start_app.png)

---

## Usage

The application opens in your browser at **http://localhost:8501**

- **Admin login:** `admin` / `admin123`
- You can also create your own account in the "Rejestracja" (Registration) tab.

To get started: create a project, upload files (PDF / TXT) and ask questions in the chat.

---

## Subsequent runs

Just run `streamlit run app.py` again with `.venv` activated.

Requirement: **PostgreSQL** and **Ollama** must be running.

---

## Troubleshooting

| Symptom                                       | Solution                                                                                                       |
| :-------------------------------------------- | :------------------------------------------------------------------------------------------------------------- |
| **Password authentication failed**            | Fix the password in `config.py` (see step 2).                                                                  |
| **`streamlit` is not recognized**             | Activate the virtual environment: `.\.venv\Scripts\Activate.ps1`.                                              |
| **Error about missing vector extension**      | Run `CREATE EXTENSION vector;` in the `rag_project_db` database (step 1).                                      |
| **Chat doesn't respond / model error**        | Check that **Ollama** is running in the background and that `ollama list` shows the installed models.          |
| **First answer takes a long time**            | This is normal – the *Bielik* model has to load into RAM/VRAM on the first query.                              |

---

## Installing pgvector (if missing)

`pgvector` is a PostgreSQL extension for storing vectors. The app won't start without it.

**First check whether it's already available** – in pgAdmin/psql:

```sql
SELECT * FROM pg_available_extensions WHERE name = 'vector';
```

If the query returns a row, the extension is ready – just run `CREATE EXTENSION vector;`.
If it returns nothing, install it for your system:

### Windows

On Windows pgvector has to be compiled (there's no official installer). You need
**Build Tools for Visual Studio**:

https://visualstudio.microsoft.com/visual-cpp-build-tools/

Then open **"x64 Native Tools Command Prompt for VS"** (from the Start menu) and run the following,
replacing `17` with your PostgreSQL version (e.g. `16`):

```cmd
set "PGROOT=C:\Program Files\PostgreSQL\17"
cd %TEMP%
git clone --branch v0.8.0 https://github.com/pgvector/pgvector.git
cd pgvector
nmake /F Makefile.win
nmake /F Makefile.win install
```

Afterwards go back to the database and run `CREATE EXTENSION vector;`.

Details and the latest version: https://github.com/pgvector/pgvector
