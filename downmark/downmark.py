"""Convert dropped supported documents to Markdown files."""

# INT
from concurrent.futures import Future, ProcessPoolExecutor
from collections.abc import Iterable
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

# EXT
from tkinterdnd2 import DND_FILES, TkinterDnD


c_default_file_formats = (".pdf", ".docx")
c_default_max_processes = 8
c_progress_refresh_ms = 1000


def convert_file(a_source_path: str) -> str | None:
    """Convert one source file to Markdown and return a failure message when needed.

    This top-level function is run in a worker process so document conversion does
    not consume resources in the Tk application's process.
    """
    # EXT
    from markitdown import MarkItDown

    x_source_path = Path(a_source_path)
    x_output_path = x_source_path.with_suffix(".md")
    try:
        x_result = MarkItDown().convert(str(x_source_path))
        x_output_path.write_text(x_result.text_content, encoding="utf-8")
    # MarkItDown selects a converter at runtime, so conversion errors can have
    # different exception types. Return them to the GUI instead of stopping a worker.
    except Exception as x_exception:
        return str(x_exception)
    return None


class DownmarkApplication:
    """Provide a drag-and-drop interface for document-to-Markdown conversion."""

    def __init__(
        self,
        a_accepted_file_formats: Iterable[str] = c_default_file_formats,
        a_max_processes: int = c_default_max_processes,
    ) -> None:
        """Create the application window with its accepted formats and process limit."""
        self.x_accepted_file_formats = self._normalize_file_formats(a_accepted_file_formats)
        self.x_max_processes = self._validate_max_processes(a_max_processes)
        self.x_files: list[Path] = []
        self.x_pending_futures: dict[Future[str | None], tuple[str, Path]] = {}
        self.x_executor: ProcessPoolExecutor | None = None
        self.x_batch_file_count = 0
        self.x_success_count = 0
        self.x_failures: list[str] = []
        self.x_root = TkinterDnD.Tk()
        self.x_root.title("Downmark")
        self.x_root.minsize(620, 380)

        self.x_status = tk.StringVar(value=self._build_drop_prompt())
        self._build_window()

    @staticmethod
    def _normalize_file_formats(a_file_formats: Iterable[str]) -> frozenset[str]:
        """Normalize configured extensions and reject an empty configuration."""
        x_formats = frozenset(
            x_normalized_format
            if x_normalized_format.startswith(".")
            else f".{x_normalized_format}"
            for x_file_format in a_file_formats
            if (x_normalized_format := x_file_format.strip().lower())
        )
        if not x_formats:
            raise ValueError("At least one accepted file format is required.")
        return x_formats

    @staticmethod
    def _validate_max_processes(a_max_processes: int) -> int:
        """Ensure the configured process limit can start at least one worker."""
        if a_max_processes < 1:
            raise ValueError("The maximum process count must be at least one.")
        return a_max_processes

    def _build_window(self) -> None:
        """Create controls and register the window as a file drop target."""
        self.x_root.columnconfigure(0, weight=1)
        self.x_root.rowconfigure(1, weight=1)

        x_instruction = ttk.Label(
            self.x_root,
            text=self._build_drop_prompt(),
            padding=(16, 16, 16, 8),
        )
        x_instruction.grid(row=0, column=0, sticky="w")

        x_table_frame = ttk.Frame(self.x_root, padding=(16, 0, 16, 8))
        x_table_frame.grid(row=1, column=0, sticky="nsew")
        x_table_frame.columnconfigure(0, weight=1)
        x_table_frame.rowconfigure(0, weight=1)

        self.x_file_table = ttk.Treeview(
            x_table_frame,
            columns=("file_name", "status"),
            show="headings",
        )
        self.x_file_table.heading("file_name", text="File name")
        self.x_file_table.heading("status", text="Status")
        self.x_file_table.column("file_name", width=420, minwidth=180, stretch=True)
        self.x_file_table.column("status", width=130, minwidth=100, stretch=False)
        self.x_file_table.grid(row=0, column=0, sticky="nsew")
        x_scrollbar = ttk.Scrollbar(
            x_table_frame,
            orient=tk.VERTICAL,
            command=self.x_file_table.yview,
        )
        x_scrollbar.grid(row=0, column=1, sticky="ns")
        self.x_file_table.configure(yscrollcommand=x_scrollbar.set)

        x_status_label = ttk.Label(self.x_root, textvariable=self.x_status, padding=(16, 0, 16, 8))
        x_status_label.grid(row=2, column=0, sticky="w")

        x_button_frame = ttk.Frame(self.x_root, padding=(16, 0, 16, 16))
        x_button_frame.grid(row=3, column=0, sticky="e")
        self.x_process_button = ttk.Button(x_button_frame, text="Process", command=self.process_files)
        self.x_process_button.grid(row=0, column=0, padx=(0, 8))
        ttk.Button(x_button_frame, text="Exit", command=self.exit_application).grid(row=0, column=1)

        # Register the root window so files can be released anywhere in the interface.
        self.x_root.drop_target_register(DND_FILES)
        self.x_root.dnd_bind("<<Drop>>", self.add_dropped_files)
        self.x_root.protocol("WM_DELETE_WINDOW", self.exit_application)

    def _build_drop_prompt(self) -> str:
        """Describe the configured file types in the interface."""
        x_formats = ", ".join(sorted(self.x_accepted_file_formats))
        return f"Drop supported files here ({x_formats})."

    def add_dropped_files(self, a_event: tk.Event[tk.Misc]) -> str:
        """Add supported, existing files from a Tk drag-and-drop event."""
        x_drop_data = getattr(a_event, "data", "")
        x_dropped_paths = (Path(x_path) for x_path in self.x_root.tk.splitlist(x_drop_data))
        x_added_count = 0
        x_rejected_count = 0

        for x_path in x_dropped_paths:
            if not x_path.is_file() or x_path.suffix.lower() not in self.x_accepted_file_formats:
                x_rejected_count += 1
                continue
            if x_path in self.x_files:
                continue

            self.x_files.append(x_path)
            self.x_file_table.insert("", tk.END, values=(x_path.name, "Queued"))
            x_added_count += 1

        self.x_status.set(self._build_drop_status(x_added_count, x_rejected_count))
        return "break"

    @staticmethod
    def _build_drop_status(a_added_count: int, a_rejected_count: int) -> str:
        """Build clear feedback after a drop operation."""
        x_message_parts = []
        if a_added_count:
            x_message_parts.append(f"Added {a_added_count} file(s).")
        if a_rejected_count:
            x_message_parts.append(f"Ignored {a_rejected_count} unsupported or missing file(s).")
        return " ".join(x_message_parts) or "Files already in the list were ignored."

    def process_files(self) -> None:
        """Submit every listed file to a bounded worker-process pool."""
        if not self.x_files:
            self.x_status.set("Drop at least one supported file before processing.")
            return

        # Start a new pool for this batch and leave the Tk event loop free to poll results.
        x_executor = ProcessPoolExecutor(max_workers=self.x_max_processes)
        self.x_executor = x_executor
        x_source_files = tuple(self.x_files)
        x_table_items = self.x_file_table.get_children()
        self.x_batch_file_count = len(x_source_files)
        self.x_success_count = 0
        self.x_failures = []
        self.x_process_button.configure(state=tk.DISABLED)

        for x_source_path, x_table_item in zip(x_source_files, x_table_items, strict=True):
            x_future = x_executor.submit(convert_file, str(x_source_path))
            self.x_pending_futures[x_future] = (x_table_item, x_source_path)
            self._set_file_status(x_table_item, x_source_path, "Processing")

        self.x_status.set(
            f"Processing {self.x_batch_file_count} file(s) with up to {self.x_max_processes} process(es)."
        )
        self.x_root.after(c_progress_refresh_ms, self.update_conversion_progress)

    def update_conversion_progress(self) -> None:
        """Display results from completed workers without blocking the Tk event loop."""
        for x_future in tuple(self.x_pending_futures):
            if not x_future.done():
                continue

            x_table_item, x_source_path = self.x_pending_futures.pop(x_future)
            try:
                x_error_message = x_future.result()
            except Exception as x_exception:
                x_error_message = str(x_exception)
            else:
                if not x_error_message:
                    self.x_success_count += 1
                    self._set_file_status(x_table_item, x_source_path, "Complete")
                    continue

            self.x_failures.append(f"{x_source_path.name}: {x_error_message}")
            self._set_file_status(x_table_item, x_source_path, "Failed")

        x_completed_count = self.x_batch_file_count - len(self.x_pending_futures)
        self.x_status.set(f"Converted {x_completed_count} of {self.x_batch_file_count} file(s).")
        if self.x_pending_futures:
            self.x_root.after(c_progress_refresh_ms, self.update_conversion_progress)
            return

        self._finish_conversion_batch()

    def _set_file_status(self, a_table_item: str, a_source_path: Path, a_status: str) -> None:
        """Update the status cell for a source file's table row."""
        self.x_file_table.item(a_table_item, values=(a_source_path.name, a_status))

    def _finish_conversion_batch(self) -> None:
        """Release idle workers and present the completed batch result."""
        if self.x_executor is not None:
            self.x_executor.shutdown(wait=False)
            self.x_executor = None

        self.x_process_button.configure(state=tk.NORMAL)
        self.x_status.set(f"Converted {self.x_success_count} of {self.x_batch_file_count} file(s).")
        if self.x_failures:
            messagebox.showerror("Conversion failed", "\n".join(self.x_failures))
        else:
            messagebox.showinfo("Downmark", "All files were converted successfully.")

    def exit_application(self) -> None:
        """Stop active workers, if any, and close the application window."""
        if self.x_executor is not None:
            self.x_executor.terminate_workers()
        self.x_root.destroy()

    def run(self) -> None:
        """Start the application's Tk event loop."""
        self.x_root.mainloop()


def main() -> None:
    """Create and start the default Downmark application."""
    x_application = DownmarkApplication()
    x_application.run()


if __name__ == "__main__":
    main()