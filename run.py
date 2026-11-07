import uvicorn
import webbrowser
import threading
import time

def open_browser():
    time.sleep(1.5)
    try:
        webbrowser.open("http://127.0.0.1:8000")
    except Exception:
        pass

if __name__ == "__main__":
    print("==================================================")
    print("  [+] DocuRAG Studio: Multi-Project PDF RAG System")
    print("  [*] Local URL: http://127.0.0.1:8000")
    print("==================================================")
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
