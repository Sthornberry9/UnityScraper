import tkinter as tk
from tkinter import ttk, messagebox
import threading
import main  # This imports your main.py script

# Define the main application window
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Download Manager')
        self.geometry('600x400')

        # Input for title IDs
        self.title_id_label = tk.Label(self, text="Enter title IDs separated by commas:")
        self.title_id_label.pack()
        self.title_id_entry = tk.Entry(self, width=50)
        self.title_id_entry.pack()

        # Start button
        self.start_button = tk.Button(self, text="Start", command=self.start_download)
        self.start_button.pack()

        # History list
        self.history_label = tk.Label(self, text="Completed Title IDs:")
        self.history_label.pack()
        self.history_listbox = tk.Listbox(self, width=50, height=10)
        self.history_listbox.pack()

        # Overall progress bar
        self.overall_progress_label = tk.Label(self, text="Overall Progress:")
        self.overall_progress_label.pack()
        self.overall_progress = ttk.Progressbar(self, length=200, mode='determinate')
        self.overall_progress.pack()

    def start_download(self):
        title_ids = self.title_id_entry.get().split(',')
        threading.Thread(target=self.download_title_ids, args=(title_ids,), daemon=True).start()

    def download_title_ids(self, title_ids):
        for title_id in title_ids:
            title_id = title_id.strip()
            if title_id:
                main.download_covers(title_id)
                main.download_updates(title_id)
                self.history_listbox.insert(tk.END, title_id)
                self.history_listbox.update_idletasks()

    def on_closing(self):
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            self.destroy()

# Run the application
if __name__ == "__main__":
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()