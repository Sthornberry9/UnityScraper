import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from downloader import UnityScraper


class App(tk.Tk):
    """
    A simple Tkinter GUI for UnityScraper. Prompts for comma-separated
    Title IDs, then runs downloads in a background thread. Uses a queue
    to safely update the UI (listbox, progress bar, status).
    """

    def __init__(self):
        super().__init__()
        self.title("XboxUnity Download Manager")
        self.geometry("600x450")

        # ====== Top Input Frame ======
        input_frame = tk.Frame(self, pady=10)
        input_frame.pack(fill=tk.X)

        tk.Label(
            input_frame,
            text="Enter Xbox Title IDs (comma-separated):",
            font=("Segoe UI", 10),
        ).pack(anchor="w", padx=10)

        self.title_id_entry = tk.Entry(input_frame, width=60)
        self.title_id_entry.pack(anchor="w", padx=10, pady=(4, 8))

        self.start_button = tk.Button(
            input_frame, text="Start Download", command=self.start_download
        )
        self.start_button.pack(anchor="w", padx=10)

        # ====== Progress & Status Frame ======
        status_frame = tk.Frame(self, pady=5)
        status_frame.pack(fill=tk.X)

        tk.Label(status_frame, text="Status:", font=("Segoe UI", 10)).pack(
            anchor="w", padx=10
        )
        self.status_label = tk.Label(
            status_frame, text="Idle", anchor="w", font=("Segoe UI", 9, "italic")
        )
        self.status_label.pack(fill=tk.X, padx=10)

        tk.Label(status_frame, text="Overall Progress:", font=("Segoe UI", 10)).pack(
            anchor="w", padx=10, pady=(6, 0)
        )
        self.overall_progress = ttk.Progressbar(
            status_frame, length=400, mode="determinate"
        )
        self.overall_progress.pack(anchor="w", padx=10, pady=(2, 8))

        # ====== History Frame ======
        hist_frame = tk.Frame(self, pady=10)
        hist_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(hist_frame, text="Completed Title IDs:", font=("Segoe UI", 10)).pack(
            anchor="w", padx=10
        )

        self.history_listbox = tk.Listbox(hist_frame, width=60, height=10)
        self.history_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=(4, 0))

        # ====== Internal Variables ======
        self.queue = queue.Queue()  # for thread-safe UI updates
        self.scraper = UnityScraper()
        self.is_downloading = False
        self.total_to_download = 0
        self.completed_count = 0

        # Start polling the queue
        self.after(100, self.process_queue)

        # Bind window close event
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def start_download(self):
        """
        Handler for the 'Start Download' button. Parses Title IDs,
        initializes state, then spawns a background thread to run downloads.
        """
        if self.is_downloading:
            return  # Already running

        txt = self.title_id_entry.get().strip()
        if not txt:
            messagebox.showwarning("No Title IDs", "Please enter at least one Title ID.")
            return

        # Build list of Title IDs
        title_ids = [tid.strip() for tid in txt.split(",") if tid.strip()]
        if not title_ids:
            messagebox.showwarning("No Title IDs", "Please enter valid Title IDs.")
            return

        # Disable inputs
        self.is_downloading = True
        self.start_button.config(state=tk.DISABLED)
        self.title_id_entry.config(state=tk.DISABLED)
        self.history_listbox.delete(0, tk.END)

        # Initialize progress
        self.total_to_download = len(title_ids)
        self.completed_count = 0
        self.overall_progress["maximum"] = self.total_to_download
        self.overall_progress["value"] = 0

        # Launch download in another thread
        threading.Thread(
            target=self.download_title_ids, args=(title_ids,), daemon=True
        ).start()

    def download_title_ids(self, title_ids):
        """
        Background thread: For each Title ID, call scraper.download_covers
        and scraper.download_updates, then enqueue GUI updates.
        """
        for idx, tid in enumerate(title_ids, start=1):
            # Update status
            self.queue.put(
                (
                    "status",
                    f"({idx}/{len(title_ids)}) Processing Title ID: {tid}",
                )
            )

            # Download covers + updates
            ok_covers = self.scraper.download_covers(tid)
            ok_updates = self.scraper.download_updates(tid)
            success = ok_covers and ok_updates

            # Enqueue "history" update
            self.queue.put(("history", (tid, success)))

            # Enqueue progress bar increment
            self.queue.put(("progress", 1))

        # All done
        self.queue.put(("status", "All downloads complete."))
        self.queue.put(("done", None))

    def process_queue(self):
        """
        Periodically called (via after) to process items in the queue and update the UI.
        """
        try:
            while True:
                msg_type, data = self.queue.get_nowait()
                if msg_type == "status":
                    # Update status label
                    self.status_label.config(text=data)
                elif msg_type == "history":
                    # data is (title_id, success)
                    title_id, success = data
                    display_text = f"{title_id}  →  {'OK' if success else 'FAILED'}"
                    self.history_listbox.insert(tk.END, display_text)
                elif msg_type == "progress":
                    # data is an integer increment (usually 1)
                    self.completed_count += data
                    self.overall_progress["value"] = self.completed_count
                elif msg_type == "done":
                    # Re-enable inputs
                    self.is_downloading = False
                    self.start_button.config(state=tk.NORMAL)
                    self.title_id_entry.config(state=tk.NORMAL)
        except queue.Empty:
            pass
        finally:
            # Schedule next queue check
            self.after(100, self.process_queue)

    def on_closing(self):
        """
        Handler for window close. If a download is in progress, ask for confirmation.
        """
        if self.is_downloading:
            if not messagebox.askokcancel(
                "Downloads in progress",
                "Downloads are still running. Do you really want to quit?",
            ):
                return
        self.destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()
