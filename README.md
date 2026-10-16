**🇵🇱 Polski** | [🇬🇧 English](README.en.md)

# Instrukcja instalacji i uruchomienia projektu RAG

## Wymagania

  

Przed uruchomieniem musisz mieć zainstalowane trzy rzeczy:

  

| Program                     | Do czego                                                  | Skąd pobrać                                                     |
| :-------------------------- | :-------------------------------------------------------- | :-------------------------------------------------------------- |
| **Python 3.11**             | Uruchomienie aplikacji i zarządzanie skryptami            | [python.org/downloads](https://www.python.org/downloads/)       |
| **PostgreSQL (z pgvector)** | Główna baza danych oraz przechowywanie wektorów           | [postgresql.org/download](https://www.postgresql.org/download/) |
| **Ollama**                  | Lokalne uruchamianie i serwowanie modeli językowych (LLM) | [ollama.com/download](https://ollama.com/download)              |

  

---

## Specyfikacja – wersje oprogramowania

Projekt był tworzony i testowany na poniższych wersjach. Inne wersje mogą działać, ale nie były sprawdzane.

### Programy

| Program        | Wersja       |
| :------------- | :----------- |
| Python         | **3.11**     |
| PostgreSQL     | **17**       |
| pgvector       | **0.8.0**    |
| Ollama         | **0.31.2**   |

### Modele (Ollama)

| Model                                         | Rola                                   | Rozmiar |
| :-------------------------------------------- | :------------------------------------- | :------ |
| `SpeakLeash/bielik-11b-v2.3-instruct:Q4_K_M`  | Model językowy (Bielik 11B v2.3, kwantyzacja Q4_K_M) | ~7 GB |
| `nomic-embed-text` (tag `latest`)             | Model embeddingów (wektory 768-wymiarowe) | ~274 MB |

### Główne biblioteki Pythona

| Biblioteka                   | Wersja   |
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

Pełna lista zależności z dokładnymi wersjami jest w pliku [requirements.txt](requirements.txt).

  

---

  

## Instalacja automatyczna (Windows)

Zamiast wykonywać ręcznie kroki opisane niżej, możesz uruchomić instalator:

1. Kliknij dwukrotnie **`install.bat`** i zgódź się na uprawnienia administratora (okno UAC).
2. Instalator sam pobierze i skonfiguruje wszystko z sekcji [Specyfikacja](#specyfikacja--wersje-oprogramowania):
   Python 3.11, PostgreSQL 17 (z hasłem i portem z `config.py`), Build Tools for Visual Studio + Git (do skompilowania pgvector 0.8.0),
   Ollama 0.31.2 z oboma modelami, bazę `rag_project_db` z rozszerzeniem `vector` oraz środowisko `.venv` z pakietami.
3. Na końcu zapyta, czy uruchomić aplikację.

Kolejne uruchomienia: **`start.bat`**. Sprawdza on, czy działają PostgreSQL i Ollama, i startuje aplikację.

> Pierwsza instalacja pobiera ok. 15 GB (Build Tools, modele, pakiety Pythona) i może potrwać od 30 minut do godziny.
> Instalator można uruchamiać wielokrotnie, bo pomija to, co jest już zainstalowane. Przebieg zapisuje do pliku `install.log`.
> Wymaga programu `winget` (jest domyślnie w Windows 10/11 jako „Instalator aplikacji”).

> Jeśli PostgreSQL 17 był zainstalowany wcześniej, instalator go nie ruszy. Wtedy hasło i port w `config.py` muszą pasować do Twojej instalacji (krok 2 poniżej).

Jeśli wolisz zrobić wszystko ręcznie, wykonaj poniższe kroki.

---

## Konfiguracja krok po kroku

  

### 1. Baza danych PostgreSQL

  

Po zainstalowaniu PostgreSQL utwórz bazę i włącz rozszerzenie `pgvector`.

W **pgAdmin** (Query Tool) lub **psql** wykonaj:

  

```sql

CREATE DATABASE rag_project_db;

```

![Tworzenie bazy danych](img/create_database.png)

Następnie **połącz się z bazą `rag_project_db`** i wykonaj:

  

```sql

CREATE EXTENSION IF NOT EXISTS vector;

```

  ![Tworzenie rozszerzenia vector](img/create_extension.png)

> Jeśli w tym miejscu pojawi się błąd `could not open extension control file ... vector` -

> to znaczy, że rozszerzenie **pgvector** nie jest zainstalowane. Zobacz sekcję

> [Instalacja pgvector](#instalacja-pgvector-gdy-go-brakuje) na końcu tego pliku.

  

> Tabele aplikacja tworzy sama przy pierwszym uruchomieniu - nie trzeba ich robić ręcznie.

  

### 2. Ustaw dane dostępowe do bazy

  

Otwórz plik **`config.py`** i w linii `DATABASE_URL` wpisz **swoje** hasło i port PostgreSQL:

  

```python

DATABASE_URL="postgresql+psycopg2://postgres:TWOJE_HASLO@localhost:5433/rag_project_db"

```

  

- `postgres` - nazwa użytkownika bazy

- `TWOJE_HASLO` - hasło ustawione przy instalacji PostgreSQL

- `5433` - port bazy. **Uwaga:** domyślny PostgreSQL działa zwykle na `5432` -

  jeśli nie zmieniałeś portu przy instalacji, wpisz `5432`.

  

> ⚠️ Najczęstszy błąd: `autoryzacja hasłem nie powiodła się` - oznacza, że hasło w `config.py`

> nie zgadza się z hasłem Twojego PostgreSQL. Popraw je tutaj.

  

### 3. Modele Ollama

  

Upewnij się, że Ollama działa (ikona w zasobniku), a następnie pobierz oba modele:

  

```powershell

ollama pull nomic-embed-text

ollama pull SpeakLeash/bielik-11b-v2.3-instruct:Q4_K_M

```

![Pull embendingu](img/pull_nomic.png)
![Pull bielika](img/pull_bielik.png)

Sprawdź poleceniem `ollama list` - powinny być widoczne oba modele.

(Bielik waży ~7 GB, pobieranie chwilę potrwa.)

Podczas wpisywania powyższych poleceń może pojawić się błąd:

```powershell

ollama : The term 'ollama' is not recognized as the name of a cmdlet, function, script file, or operable program. Check
 the spelling of the name, or if a path was included, verify that the path is correct and try again.
At line:1 char:1
+ ollama pull nomic-embed-text
+ ~~~~~~
    + CategoryInfo          : ObjectNotFound: (ollama:String) [], CommandNotFoundException
    + FullyQualifiedErrorId : CommandNotFoundException

```

jeśli Ollama jest zainstalowana sprawdzamy to poleceniem: 

```powershell

 & "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" --version

```

powinniśmy otrzymać wersję Ollamy:

```powershell
ollama version is 0.31.2
```

Jeżeli jednak nie mamy wersji Ollamy, oznacza to że trzeba ją doinstalować:

```powershell
irm https://ollama.com/install.ps1 | iex
```

teraz dodajemy Ollamę do PATH 

```powershell
$env:Path += ";$env:LOCALAPPDATA\Programs\Ollama"
```



---

  

## Uruchomienie

  
 ### Ręcznie w terminalu (PowerShell)

  

```powershell

python -m venv .venv

.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt

streamlit run app.py

```

![Uruchomienie aplikacji](img/start_app.png)
  

---

  

## Korzystanie

  

Aplikacja otworzy się w przeglądarce pod adresem **http://localhost:8501**

  

- **Logowanie administratora:** `admin` / `admin123`

- Możesz też założyć własne konto w zakładce „Rejestracja".

  

Aby zacząć: utwórz projekt, wgraj pliki (PDF / TXT) i zadawaj pytania w czacie.

  

---

  

## Kolejne uruchomienia

  

Wystarczy ponownie odpalić  `streamlit run app.py` z aktywnym `.venv`.

Warunek: **PostgreSQL** i **Ollama** muszą być uruchomione.

  

---

  

## Najczęstsze problemy

  

| Objaw                                      | Rozwiązanie                                                                                                            |
| :----------------------------------------- | :--------------------------------------------------------------------------------------------------------------------- |
| **Autoryzacja hasłem nie powiodła się**    | Popraw hasło w pliku `config.py` (patrz krok 2).                                                                       |
| **`streamlit` : nie rozpoznano polecenia** | Aktywuj środowisko wirtualne: `.\.venv\Scripts\Activate.ps1`.                                                          |
| **Błąd o braku rozszerzenia vector**       | Wykonaj zapytanie `CREATE EXTENSION vector;` w bazie `rag_project_db` (krok 1).                                        |
| **Czat nie odpowiada / błąd modelu**       | Sprawdź, czy program **Ollama** działa w tle oraz czy komenda `ollama list` w terminalu pokazuje zainstalowane modele. |
| **Pierwsza odpowiedź długo się generuje**  | To normalne zjawisko – model *Bielik* musi po raz pierwszy załadować się do pamięci RAM/VRAM przy pierwszym zapytaniu. |

  

---

  

## Instalacja pgvector (gdy go brakuje)

  

`pgvector` to rozszerzenie PostgreSQL do przechowywania wektorów. Bez niego aplikacja nie ruszy.

  

**Najpierw sprawdź, czy nie masz go już dostępnego** - w pgAdmin/psql:

  

```sql

SELECT * FROM pg_available_extensions WHERE name = 'vector';

```

  

Jeśli zapytanie zwróci wiersz - rozszerzenie jest gotowe, wystarczy `CREATE EXTENSION vector;`.

Jeśli nic nie zwróci - zainstaluj je zależnie od systemu:

  

### Windows

  

Na Windows pgvector trzeba skompilować (nie ma oficjalnego instalatora). Potrzebujesz

**Build Tools for Visual Studio**:

https://visualstudio.microsoft.com/visual-cpp-build-tools/

  

Następnie otwórz **„x64 Native Tools Command Prompt for VS”** (z menu Start) i wykonaj -

podmieniając `17` na swoją wersję PostgreSQL (np. `16`):

  

```cmd

set "PGROOT=C:\Program Files\PostgreSQL\17"

cd %TEMP%

git clone --branch v0.8.0 https://github.com/pgvector/pgvector.git

cd pgvector

nmake /F Makefile.win

nmake /F Makefile.win install

```

  

Po tym wróć do bazy i wykonaj `CREATE EXTENSION vector;`.

Szczegóły i najnowsza wersja: https://github.com/pgvector/pgvector
