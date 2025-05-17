import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time
import psycopg2
from datetime import datetime
from queue import Queue
from ping3 import ping, verbose_ping
from concurrent.futures import ThreadPoolExecutor, as_completed
import socket

class DarkModeTheme:
    @staticmethod
    def apply(root):
        root.tk_setPalette(
            background='#1a1a1a', foreground='#ffffff',
            activeBackground='#404040', activeForeground='#ffffff',
            selectColor='#3a3a3a', selectBackground='#3a3a3a',
            insertBackground='#ffffff'
        )
        
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure colors
        style.configure('.', background='#1a1a1a', foreground='#ffffff')
        style.configure('TFrame', background='#1a1a1a')
        style.configure('TLabel', background='#1a1a1a', foreground='#ffffff')
        style.configure('TButton', background='#3a3a3a', foreground='#ffffff', borderwidth=1)
        style.configure('TEntry', fieldbackground='#2a2a2a', foreground='#ffffff')
        style.configure('TCombobox', fieldbackground='#2a2a2a', foreground='#ffffff')
        style.map('TButton', 
                background=[('active', '#404040'), ('pressed', '#505050')],
                foreground=[('active', '#ffffff'), ('pressed', '#ffffff')])
        style.map('TCombobox', 
                fieldbackground=[('readonly', '#2a2a2a')],
                foreground=[('readonly', '#ffffff')])
        
        # Scrollbar style
        style.configure('Vertical.TScrollbar', background='#2a2a2a', troughcolor='#1a1a1a')
        style.configure('Horizontal.TScrollbar', background='#2a2a2a', troughcolor='#1a1a1a')
        
        # Treeview style
        style.configure("Treeview", 
                      background="#2a2a2a", 
                      foreground="#ffffff",
                      fieldbackground="#2a2a2a",
                      rowheight=25)
        style.map('Treeview', background=[('selected', '#3a3a3a')])
        style.configure("Treeview.Heading", 
                      background="#3a3a3a", 
                      foreground="#ffffff",
                      relief="flat")
        style.map("Treeview.Heading", 
                background=[('active', '#4a4a4a')])

class PingMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("VICS Ping Monitor")
        self.root.geometry("1200x800")
        
        # Database connection parameters
        self.db_params = {
            "host": "172.20.200.253",
            "database": "postgres",
            "user": "postgres",
            "password": "yamaha1*"
        }
        
        # Initialize variables
        self.targets = []
        self.ping_thread = None
        self.stop_ping = False
        self.message_queue = Queue()
        self.ttl_days = 30
        self.ping_interval = 3  # Ping interval in seconds
        self.max_workers = 50   # Max concurrent ping threads
        self.ping_attempts = 2  # Number of ping attempts before declaring failure
        self.ping_timeout = 0.5   # Timeout in seconds for each ping
        
        # Thread pool for concurrent pinging
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        
        # Setup UI
        self.setup_ui()
        
        # Check for messages from other threads
        self.check_queue()
        
        # Initialize database
        self.initialize_database()
        
        # Load targets from database
        self.load_targets_from_db()
    
    def setup_ui(self):
        # Apply dark mode
        DarkModeTheme.apply(self.root)
        
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left panel (controls)
        left_panel = ttk.Frame(main_frame, width=350)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        # Right panel (results)
        right_panel = ttk.Frame(main_frame)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Targets section
        targets_frame = ttk.LabelFrame(left_panel, text="Target Management", padding="10")
        targets_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Target entry
        ttk.Label(targets_frame, text="Target (IP/Hostname):").pack(anchor=tk.W)
        self.target_entry = ttk.Entry(targets_frame)
        self.target_entry.pack(fill=tk.X, pady=(0, 5))
        
        # Add/Remove buttons
        button_frame = ttk.Frame(targets_frame)
        button_frame.pack(fill=tk.X)
        
        add_btn = ttk.Button(button_frame, text="Add Target", command=self.add_target)
        add_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        remove_btn = ttk.Button(button_frame, text="Remove Selected", command=self.remove_target)
        remove_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Targets list
        self.targets_listbox = tk.Listbox(
            targets_frame, 
            height=10,
            bg="#2a2a2a", 
            fg="#ffffff", 
            selectbackground="#3a3a3a",
            selectforeground="#ffffff"
        )
        self.targets_listbox.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        
        # Control buttons
        control_frame = ttk.LabelFrame(left_panel, text="Monitoring Control", padding="10")
        control_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.start_btn = ttk.Button(control_frame, text="Start Monitoring", command=self.start_monitoring)
        self.start_btn.pack(fill=tk.X, pady=(0, 5))
        
        self.stop_btn = ttk.Button(control_frame, text="Stop Monitoring", command=self.stop_monitoring, state=tk.DISABLED)
        self.stop_btn.pack(fill=tk.X)
        
        # Settings frame
        settings_frame = ttk.LabelFrame(left_panel, text="Ping Settings", padding="10")
        settings_frame.pack(fill=tk.X, pady=(10, 0))
        
        # TTL settings
        ttk.Label(settings_frame, text="Data Retention (days):").pack(anchor=tk.W)
        self.ttl_var = tk.IntVar(value=self.ttl_days)
        ttk.Spinbox(
            settings_frame, 
            from_=1, 
            to=365, 
            textvariable=self.ttl_var,
            command=self.update_ttl
        ).pack(fill=tk.X)
        
        # Ping attempts
        ttk.Label(settings_frame, text="Ping Attempts:").pack(anchor=tk.W)
        self.attempts_var = tk.IntVar(value=self.ping_attempts)
        ttk.Spinbox(
            settings_frame, 
            from_=1, 
            to=5, 
            textvariable=self.attempts_var,
            command=self.update_attempts
        ).pack(fill=tk.X)
        
        # Ping timeout
        ttk.Label(settings_frame, text="Ping Timeout (sec):").pack(anchor=tk.W)
        self.timeout_var = tk.IntVar(value=self.ping_timeout)
        ttk.Spinbox(
            settings_frame, 
            from_=1, 
            to=10, 
            textvariable=self.timeout_var,
            command=self.update_timeout
        ).pack(fill=tk.X)
        
        # Log section
        log_frame = ttk.LabelFrame(left_panel, text="Activity Log", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            height=10,
            bg="#2a2a2a",
            fg="#ffffff",
            insertbackground="#ffffff"
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Status section
        status_frame = ttk.LabelFrame(right_panel, text="Current Status", padding="10")
        status_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create treeview with scrollbars
        tree_frame = ttk.Frame(status_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Vertical scrollbar
        tree_scroll_y = ttk.Scrollbar(tree_frame)
        tree_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Horizontal scrollbar
        tree_scroll_x = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)
        tree_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Create treeview
        self.status_tree = ttk.Treeview(
            tree_frame,
            columns=("target", "status", "last_response", "last_check", "success_rate", "attempts"),
            show="headings",
            selectmode="extended",
            yscrollcommand=tree_scroll_y.set,
            xscrollcommand=tree_scroll_x.set
        )
        
        # Configure columns
        self.status_tree.heading("target", text="Target", anchor=tk.W)
        self.status_tree.heading("status", text="Status", anchor=tk.CENTER)
        self.status_tree.heading("last_response", text="Response (ms)", anchor=tk.CENTER)
        self.status_tree.heading("last_check", text="Last Check", anchor=tk.CENTER)
        self.status_tree.heading("success_rate", text="Success Rate", anchor=tk.CENTER)
        self.status_tree.heading("attempts", text="Attempts", anchor=tk.CENTER)
        
        self.status_tree.column("target", width=200, stretch=tk.YES)
        self.status_tree.column("status", width=100, stretch=tk.NO, anchor=tk.CENTER)
        self.status_tree.column("last_response", width=100, stretch=tk.NO, anchor=tk.CENTER)
        self.status_tree.column("last_check", width=150, stretch=tk.NO, anchor=tk.CENTER)
        self.status_tree.column("success_rate", width=100, stretch=tk.NO, anchor=tk.CENTER)
        self.status_tree.column("attempts", width=80, stretch=tk.NO, anchor=tk.CENTER)
        
        self.status_tree.pack(fill=tk.BOTH, expand=True)
        
        # Configure scrollbars
        tree_scroll_y.config(command=self.status_tree.yview)
        tree_scroll_x.config(command=self.status_tree.xview)
        
        # Status bar
        self.status_bar = ttk.Label(right_panel, text="Ready", relief=tk.SUNKEN)
        self.status_bar.pack(fill=tk.X, pady=(5, 0))
    
    def initialize_database(self):
        conn = None
        try:
            conn = self.get_db_connection()
            conn.autocommit = True
            
            with conn.cursor() as cur:
                # Create targets table if not exists
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS ping_targets (
                        id SERIAL PRIMARY KEY,
                        target VARCHAR(255) NOT NULL UNIQUE,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create results table if not exists
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS ping_results (
                        id SERIAL PRIMARY KEY,
                        target VARCHAR(255) NOT NULL,
                        status BOOLEAN NOT NULL,
                        response_time FLOAT,
                        attempts INTEGER NOT NULL,
                        timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create indexes
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_ping_results_timestamp 
                    ON ping_results(timestamp)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_ping_results_target 
                    ON ping_results(target)
                """)
                
                # Create cleanup function
                cur.execute(f"""
                    CREATE OR REPLACE FUNCTION clean_old_ping_results()
                    RETURNS TRIGGER AS $$
                    BEGIN
                        DELETE FROM ping_results 
                        WHERE timestamp < NOW() - INTERVAL '{self.ttl_days} days';
                        RETURN NULL;
                    END;
                    $$ LANGUAGE plpgsql
                """)
                
                # Create or replace trigger
                cur.execute("""
                    DROP TRIGGER IF EXISTS trigger_clean_old_ping_results ON ping_results
                """)
                
                cur.execute("""
                    CREATE TRIGGER trigger_clean_old_ping_results
                    AFTER INSERT ON ping_results
                    EXECUTE FUNCTION clean_old_ping_results()
                """)
                
                self.log("Database initialized successfully")
                
        except Exception as e:
            self.log(f"Database initialization error: {str(e)}")
            messagebox.showerror("Database Error", f"Cannot initialize database:\n{str(e)}")
        finally:
            if conn:
                conn.close()
    
    def update_ttl(self):
        self.ttl_days = self.ttl_var.get()
        self.initialize_database()
    
    def update_attempts(self):
        self.ping_attempts = self.attempts_var.get()
    
    def update_timeout(self):
        self.ping_timeout = self.timeout_var.get()
    
    def get_db_connection(self):
        return psycopg2.connect(**self.db_params)
    
    def load_targets_from_db(self):
        conn = None
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT target FROM ping_targets ORDER BY target")
                self.targets = [row[0] for row in cur.fetchall()]
                
                # Update listbox
                self.targets_listbox.delete(0, tk.END)
                for target in self.targets:
                    self.targets_listbox.insert(tk.END, target)
                    # Add to status tree with default values
                    self.status_tree.insert("", tk.END, values=(
                        target, 
                        "Unknown", 
                        "N/A", 
                        "Never", 
                        "N/A",
                        "0"
                    ))
                
                self.log(f"Loaded {len(self.targets)} targets from database")
                
        except Exception as e:
            self.log(f"Error loading targets: {str(e)}")
        finally:
            if conn:
                conn.close()
    
    def add_target(self):
        target = self.target_entry.get().strip()
        if not target:
            return
            
        if target in self.targets:
            self.log(f"Target already exists: {target}")
            return
            
        conn = None
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO ping_targets (target) VALUES (%s)",
                    (target,)
                )
                conn.commit()
                
                self.targets.append(target)
                self.targets_listbox.insert(tk.END, target)
                self.target_entry.delete(0, tk.END)
                self.log(f"Added target: {target}")
                
                # Add to status tree with default values
                self.status_tree.insert("", tk.END, values=(
                    target, 
                    "Unknown", 
                    "N/A", 
                    "Never", 
                    "N/A",
                    "0"
                ))
                
        except psycopg2.IntegrityError:
            self.log(f"Target already exists in database: {target}")
        except Exception as e:
            self.log(f"Error adding target: {str(e)}")
        finally:
            if conn:
                conn.close()
    
    def remove_target(self):
        selection = self.targets_listbox.curselection()
        if not selection:
            return
            
        index = selection[0]
        target = self.targets_listbox.get(index)
        
        conn = None
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cur:
                # Remove from targets table
                cur.execute(
                    "DELETE FROM ping_targets WHERE target = %s",
                    (target,)
                )
                
                # Remove from results table
                cur.execute(
                    "DELETE FROM ping_results WHERE target = %s",
                    (target,)
                )
                
                conn.commit()
                
                # Update UI
                self.targets_listbox.delete(index)
                self.targets.remove(target)
                
                # Remove from status tree
                for item in self.status_tree.get_children():
                    if self.status_tree.item(item, 'values')[0] == target:
                        self.status_tree.delete(item)
                        break
                
                self.log(f"Removed target: {target}")
                
        except Exception as e:
            self.log(f"Error removing target: {str(e)}")
        finally:
            if conn:
                conn.close()
    
    def reliable_ping(self, target):
        attempts = 0
        response_time = None
        start_time = time.time()
        
        # Try multiple attempts
        for attempt in range(self.ping_attempts):
            try:
                # First try with DNS resolution
                response_time = ping(target, timeout=self.ping_timeout, unit='ms')
                if response_time is not None:
                    attempts = attempt + 1
                    break
                
                # If failed, try with direct IP if it's a hostname
                try:
                    ip_addr = socket.gethostbyname(target)
                    if ip_addr != target:  # Only try if we got a different IP
                        response_time = ping(ip_addr, timeout=self.ping_timeout, unit='ms')
                        if response_time is not None:
                            attempts = attempt + 1
                            break
                except socket.gaierror:
                    pass
                
            except Exception as e:
                self.log(f"Ping attempt {attempt+1} failed for {target}: {str(e)}")
            
            if attempt < self.ping_attempts - 1:
                time.sleep(0.5)  # Small delay between attempts
        
        status = response_time is not None
        duration = int((time.time() - start_time) * 1000)
        
        return {
            "target": target,
            "status": status,
            "response_time": response_time if status else None,
            "attempts": attempts,
            "duration": duration
        }
    
    def ping_all_targets(self):
        while not self.stop_ping:
            cycle_start = time.time()
            
            # Submit all ping tasks to thread pool
            futures = {self.executor.submit(self.reliable_ping, target): target for target in self.targets}
            
            # Process results as they complete
            for future in as_completed(futures):
                result = future.result()
                target = result["target"]
                status = result["status"]
                response_time = result["response_time"]
                attempts = result["attempts"]
                duration = result["duration"]
                
                # Save to database
                self.save_ping_result(target, status, response_time, attempts)
                
                # Get success rate
                success_rate = self.get_success_rate(target)
                
                # Prepare UI update
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                response_str = f"{response_time:.2f}" if status else "Timeout"
                status_str = "Online" if status else "Offline"
                
                self.message_queue.put(("update_status", (
                    target,
                    status_str,
                    response_str,
                    timestamp,
                    f"{success_rate:.1f}%",
                    f"{attempts}/{self.ping_attempts}"
                )))
                
                # Log the result
                log_msg = (f"Ping {target}: {'Success' if status else 'Timeout'} "
                         f"(Response: {response_str}ms, Attempts: {attempts}, Duration: {duration}ms)")
                self.message_queue.put(("log", log_msg))
            
            # Calculate time taken and adjust sleep time
            cycle_time = time.time() - cycle_start
            sleep_time = max(0, self.ping_interval - cycle_time)
            time.sleep(sleep_time)
    
    def save_ping_result(self, target, status, response_time, attempts):
        conn = None
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cur:
                if response_time is not None:
                    cur.execute(
                        """INSERT INTO ping_results 
                        (target, status, response_time, attempts) 
                        VALUES (%s, %s, %s, %s)""",
                        (target, status, float(response_time), attempts)
                    )
                else:
                    cur.execute(
                        """INSERT INTO ping_results 
                        (target, status, response_time, attempts) 
                        VALUES (%s, %s, NULL, %s)""",
                        (target, status, attempts)
                    )
                conn.commit()
        except Exception as e:
            self.message_queue.put(("log", f"Database error: {str(e)}"))
        finally:
            if conn:
                conn.close()
    
    def get_success_rate(self, target):
        conn = None
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cur:
                # Get total pings in last 24 hours
                cur.execute("""
                    SELECT COUNT(*) FROM ping_results 
                    WHERE target = %s 
                    AND timestamp >= NOW() - INTERVAL '24 hours'
                """, (target,))
                total = cur.fetchone()[0]
                
                if total == 0:
                    return 0.0
                
                # Get successful pings
                cur.execute("""
                    SELECT COUNT(*) FROM ping_results 
                    WHERE target = %s 
                    AND status = TRUE
                    AND timestamp >= NOW() - INTERVAL '24 hours'
                """, (target,))
                success = cur.fetchone()[0]
                
                return (success / total) * 100
                
        except Exception as e:
            self.log(f"Error calculating success rate: {str(e)}")
            return 0.0
        finally:
            if conn:
                conn.close()
    
    def update_status_display(self, target, status, response_time, timestamp, success_rate, attempts):
        # Find the item in the treeview
        for item in self.status_tree.get_children():
            values = self.status_tree.item(item, 'values')
            if values[0] == target:
                # Update the values
                self.status_tree.item(item, values=(
                    target,
                    status,
                    response_time,
                    timestamp,
                    success_rate,
                    attempts
                ))
                
                # Update color based on status
                if status == "Online":
                    self.status_tree.tag_configure('online', foreground='#7e57c2')
                    self.status_tree.item(item, tags=('online',))
                else:
                    self.status_tree.tag_configure('offline', foreground='#ff5252')
                    self.status_tree.item(item, tags=('offline',))
                
                # Bring to top to show most recent first
                self.status_tree.move(item, '', 0)
                break
    
    def start_monitoring(self):
        if not self.targets:
            messagebox.showwarning("Warning", "Please add at least one target to monitor.")
            return
            
        if self.ping_thread and self.ping_thread.is_alive():
            return
            
        self.stop_ping = False
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        
        self.ping_thread = threading.Thread(target=self.ping_all_targets, daemon=True)
        self.ping_thread.start()
        
        self.log("Monitoring started (concurrent mode with retries)")
        self.status_bar.config(text="Monitoring active - concurrent pinging with retries")
    
    def stop_monitoring(self):
        self.stop_ping = True
        if self.ping_thread and self.ping_thread.is_alive():
            self.ping_thread.join(timeout=1)
            
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.log("Monitoring stopped")
        self.status_bar.config(text="Monitoring stopped")
    
    def log(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
    
    def check_queue(self):
        while not self.message_queue.empty():
            message_type, content = self.message_queue.get()
            
            if message_type == "log":
                self.log(content)
            elif message_type == "update_status":
                self.update_status_display(*content)
        
        self.root.after(100, self.check_queue)
    
    def on_closing(self):
        self.stop_ping = True
        if self.ping_thread and self.ping_thread.is_alive():
            self.ping_thread.join(timeout=1)
        self.executor.shutdown(wait=False)
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = PingMonitorApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()