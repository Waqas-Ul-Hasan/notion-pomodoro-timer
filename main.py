import sys
import customtkinter as ctk
import threading
import queue
import json
import os
import uuid
import time
import requests
import ctypes
import subprocess

# --- 1. ROBUST CROSS-PLATFORM AUDIO PLAYER ---
class AudioPlayer:
    def __init__(self):
        self.platform = sys.platform
        self.process = None
        self.alias = "pomo_audio"
        self._mci = None
        if self.platform == "win32":
            try:
                self._mci = ctypes.windll.winmm.mciSendStringW
            except Exception:
                pass

    def play(self, file_path, loop=False):
        # Stop any existing sound first to prevent overlap or errors
        self.stop()
        
        if not os.path.exists(file_path):
            if not loop:
                if self.platform == "win32":
                    try:
                        import winsound
                        winsound.PlaySound("SystemHand", winsound.SND_ALIAS | winsound.SND_ASYNC)
                    except:
                        pass
                elif self.platform == "linux":
                    # Try to play a standard system notification sound
                    system_sounds = [
                        "/usr/share/sounds/zorin/stereo/bell.ogg",
                        "/usr/share/sounds/gnome/default/alerts/string.ogg",
                        "/usr/share/sounds/gnome/default/alerts/glass.ogg",
                        "/usr/share/sounds/speech-dispatcher/test.wav",
                        "/usr/share/sounds/alsa/Front_Center.wav"
                    ]
                    played = False
                    for sound in system_sounds:
                        if os.path.exists(sound):
                            try:
                                if os.path.exists("/usr/bin/paplay") and sound.endswith((".wav", ".ogg")):
                                    self.process = subprocess.Popen(["paplay", sound], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                else:
                                    self.process = subprocess.Popen(["cvlc", "--play-and-exit", "--no-video", sound], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                played = True
                                break
                            except Exception:
                                pass
                    if not played:
                        print("\a", end="", flush=True)
                elif self.platform == "darwin":
                    try:
                        self.process = subprocess.Popen(["afplay", "/System/Library/Sounds/Glass.aiff"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except Exception:
                        pass
            return

        if self.platform == "win32" and self._mci:
            try:
                cmd_open = f'open "{file_path}" type mpegvideo alias {self.alias}'
                self._mci(cmd_open, None, 0, 0)
                cmd_play = f'play {self.alias} from 0'
                if loop:
                    cmd_play += " repeat"
                self._mci(cmd_play, None, 0, 0)
            except Exception:
                pass
        elif self.platform == "linux":
            try:
                cmd = ["cvlc", "--no-video"]
                if loop:
                    cmd.append("--loop")
                else:
                    cmd.append("--play-and-exit")
                cmd.append(file_path)
                self.process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                print("\a", end="", flush=True)
        elif self.platform == "darwin":
            try:
                cmd = ["afplay", file_path]
                self.process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

    def stop(self):
        if self.platform == "win32" and self._mci:
            try:
                self._mci(f'stop {self.alias}', None, 0, 0)
                self._mci(f'close {self.alias}', None, 0, 0)
            except Exception:
                pass
        else:
            if self.process:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=0.2)
                except Exception:
                    try:
                        self.process.kill()
                    except Exception:
                        pass
                self.process = None

WindowsAudioPlayer = AudioPlayer
audio = AudioPlayer()

# --- 2. CONFIG & PATHS ---
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, "assets", relative_path)

DEFAULT_CONFIG = {
    "theme": "dark",
    "pomodoro_minutes": 25,
    "break_minutes": 5,
    "ticking_sound_path": resource_path("ticking.wav"),
    "finish_sound_path": resource_path("finish_sound.wav"),
    "break_finish_sound_path": resource_path("break_finish_sound.wav"),
    "secret_channel_id": "", 
    "start_keywords": ["Ongoing", "In Progress"],
    "stop_keywords": ["Done", "Completed", "Archived"],
    "pause_keywords": ["Paused", "On Hold"],
    "resume_keywords": ["Ongoing", "In Progress"]
}

app_config = {}
command_queue = queue.Queue()

def get_app_dir():
    if sys.platform == "win32":
        ap = os.getenv('APPDATA')
        path = os.path.join(ap, 'NotionPomodoro') if ap else os.path.join(os.path.expanduser('~'), '.NotionPomodoro')
    else:
        path = os.path.join(os.path.expanduser('~'), '.NotionPomodoro')
    try: os.makedirs(path, exist_ok=True)
    except: pass
    return path

def get_config_file():
    return os.path.join(get_app_dir(), 'config.json')

def load_config():
    global app_config
    f = get_config_file()
    if not os.path.exists(f):
        app_config = DEFAULT_CONFIG.copy()
        app_config["secret_channel_id"] = f"notion_pomo_{uuid.uuid4().hex}"
        save_config(app_config)
    else:
        try:
            with open(f, "r") as file:
                app_config = json.load(file)
                # Ensure all keys exist (merge defaults)
                for k, v in DEFAULT_CONFIG.items():
                    if "sound_path" not in k: 
                        app_config.setdefault(k, v)
                if not app_config.get("secret_channel_id"):
                    app_config["secret_channel_id"] = f"notion_pomo_{uuid.uuid4().hex}"
                    save_config(app_config)
        except:
            app_config = DEFAULT_CONFIG.copy()
            app_config["secret_channel_id"] = f"notion_pomo_{uuid.uuid4().hex}"
    
    # Always enforce correct asset paths
    app_config["ticking_sound_path"] = resource_path("ticking.wav")
    app_config["finish_sound_path"] = resource_path("finish_sound.wav")
    app_config["break_finish_sound_path"] = resource_path("break_finish_sound.wav")
    
    return app_config

def save_config(data):
    try:
        # Don't save absolute paths to config to keep it portable
        to_save = data.copy()
        keys_to_remove = [k for k in to_save if "sound_path" in k]
        for k in keys_to_remove: del to_save[k]
        
        with open(get_config_file(), "w") as f: json.dump(to_save, f, indent=4)
    except: pass
    load_config()

# --- 3. LISTENER ---
def ntfy_listener(stop_event):
    while not stop_event.is_set():
        cid = app_config.get("secret_channel_id")
        if not cid: time.sleep(1); continue
        current_cid = cid
        try:
            # Set read timeout to 45 seconds to detect dead streams and reconnect cleanly
            with requests.get(f"https://ntfy.sh/{cid}/json", stream=True, timeout=45) as r:
                for line in r.iter_lines():
                    if stop_event.is_set(): break
                    # Reconnect if user changes the channel ID in settings
                    if app_config.get("secret_channel_id") != current_cid:
                        break
                    if line:
                        try:
                            obj = json.loads(line)
                            if obj.get("event") == "message": process_payload(obj.get("message", ""))
                        except: pass
        except: time.sleep(5)

def process_payload(raw_json):
    try:
        data = json.loads(raw_json)
        properties = data.get("data", {}).get("properties", {})
        status = None
        task = "Unnamed"
        
        for prop_name, prop_val in properties.items():
            if isinstance(prop_val, dict):
                if "title" in prop_val:
                    title_list = prop_val.get("title", [])
                    if title_list and isinstance(title_list, list) and len(title_list) > 0:
                        task = title_list[0].get("plain_text", "Unnamed")
                elif "status" in prop_val:
                    status_obj = prop_val.get("status", {})
                    if isinstance(status_obj, dict):
                        status = status_obj.get("name")
                        
        cmd = None
        if status in app_config.get("start_keywords", []): cmd = "start"
        elif status in app_config.get("stop_keywords", []): cmd = "stop"
        elif status in app_config.get("pause_keywords", []): cmd = "pause"
        elif status in app_config.get("resume_keywords", []): cmd = "resume"
        if cmd: command_queue.put({"cmd": cmd, "task": task})
    except: pass

# --- 4. GUI ---
class ExpandableFrame(ctk.CTkFrame):
    def __init__(self, master, title=""):
        super().__init__(master, fg_color="transparent"); self.is_expanded = False
        header = ctk.CTkFrame(self); header.pack(fill="x", expand=True)
        self.btn = ctk.CTkButton(header, text="▼", width=30, height=30, font=ctk.CTkFont(size=20), fg_color="transparent", hover_color=("gray70", "gray30"), command=self.toggle)
        self.btn.pack(side="left", padx=(5,0))
        ctk.CTkLabel(header, text=title, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5)
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
    def get_content_frame(self): return self.content_frame
    def set_text_content(self, text):
        for w in self.content_frame.winfo_children(): w.destroy()
        tb = ctk.CTkTextbox(self.content_frame, wrap="word", fg_color=("gray90", "gray13"), border_spacing=5, height=100)
        tb.pack(fill="x", expand=True, padx=5); tb.insert("1.0", text); tb.configure(state="disabled")
    def toggle(self):
        self.is_expanded = not self.is_expanded
        if self.is_expanded: self.btn.configure(text="▲"); self.content_frame.pack(fill="x", expand=True, pady=(0, 5))
        else: self.btn.configure(text="▼"); self.content_frame.pack_forget()

class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, master, config):
        super().__init__(master); self.master_app = master; self.config = config.copy()
        self.title("Settings"); self.geometry("500x700"); self.transient(master)
        self.attributes("-topmost", True)
        self.grid_rowconfigure(1, weight=1); self.grid_columnconfigure(0, weight=1)
        
        header = ctk.CTkFrame(self, corner_radius=0); header.grid(row=0, column=0, sticky="ew"); header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Settings", font=("Arial", 20, "bold")).grid(row=0, column=0, padx=20, pady=10, sticky="w")
        self.save_btn = ctk.CTkButton(header, text="Save & Close", command=self.save); self.save_btn.grid(row=0, column=1, padx=20, pady=10, sticky="e")
        
        body = ctk.CTkScrollableFrame(self); body.grid(row=1, column=0, sticky="nsew"); body.grid_columnconfigure(0, weight=1)
        
        # Connection
        self.add_section(body, "1. Connection")
        self.url = ctk.CTkEntry(body, state="readonly")
        self.url.pack(fill="x", padx=20, pady=5)
        self.url.configure(state="normal"); self.url.insert(0, f"https://ntfy.sh/{self.config['secret_channel_id']}"); self.url.configure(state="readonly")
        ctk.CTkButton(body, text="Copy URL", command=self.copy_url).pack(pady=5)
        
        instr = ExpandableFrame(body, title="How to Connect"); instr.pack(fill="x", padx=15, pady=10); i_cont = instr.get_content_frame()
        ExpandableFrame(i_cont, title="1. Copy URL").set_text_content("Click 'Copy URL' above. This is your personal link.")
        ExpandableFrame(i_cont, title="2. Notion Automation").set_text_content("1. Go to Notion DB -> Automations (Lightning Icon).\n2. Trigger: Status changes.\n3. Action: Send Webhook -> Paste the URL.")

        # Timers
        self.add_section(body, "2. Timers (Minutes)")
        self.lbl_p = ctk.CTkLabel(body, text=f"Pomodoro: {self.config['pomodoro_minutes']}")
        self.lbl_p.pack(anchor="w", padx=20)
        self.sl_p = ctk.CTkSlider(body, from_=1, to=90, number_of_steps=89, command=lambda v: self.lbl_p.configure(text=f"Pomodoro: {int(v)}"))
        self.sl_p.set(self.config['pomodoro_minutes']); self.sl_p.pack(fill="x", padx=20)
        try:
            self.sl_p._canvas.unbind("<MouseWheel>")
            self.sl_p._canvas.unbind("<Button-4>")
            self.sl_p._canvas.unbind("<Button-5>")
        except Exception:
            pass
        
        self.lbl_b = ctk.CTkLabel(body, text=f"Break: {self.config['break_minutes']}")
        self.lbl_b.pack(anchor="w", padx=20, pady=(10,0))
        self.sl_b = ctk.CTkSlider(body, from_=1, to=30, number_of_steps=29, command=lambda v: self.lbl_b.configure(text=f"Break: {int(v)}"))
        self.sl_b.set(self.config['break_minutes']); self.sl_b.pack(fill="x", padx=20)
        try:
            self.sl_b._canvas.unbind("<MouseWheel>")
            self.sl_b._canvas.unbind("<Button-4>")
            self.sl_b._canvas.unbind("<Button-5>")
        except Exception:
            pass
        
        self.add_section(body, "3. Theme")
        self.theme_menu = ctk.CTkOptionMenu(body, values=["dark", "light", "system"], command=self.master_app.change_theme)
        self.theme_menu.set(self.config["theme"]); self.theme_menu.pack(fill="x", padx=20, pady=5)

        # Keywords
        self.add_section(body, "4. Keywords (Comma separated)")
        self.kw_ui = {}
        for k, title in [("start_keywords", "Start"), ("stop_keywords", "Stop"), ("pause_keywords", "Pause"), ("resume_keywords", "Resume")]:
            self.kw_ui[k] = self.add_kw_group(body, title, k)

    def add_section(self, p, t): ctk.CTkLabel(p, text=t, font=("Arial", 14, "bold")).pack(anchor="w", padx=10, pady=(15,5))
    def add_kw_group(self, p, title, key):
        ctk.CTkLabel(p, text=f"{title}:").pack(anchor="w", padx=20)
        txt = ctk.CTkTextbox(p, height=50); txt.pack(fill="x", padx=20)
        txt.insert("1.0", ", ".join(self.config[key]))
        return txt
    def copy_url(self): self.clipboard_clear(); self.clipboard_append(self.url.get())
    def save(self):
        self.config["pomodoro_minutes"] = int(self.sl_p.get())
        self.config["break_minutes"] = int(self.sl_b.get())
        for k, widget in self.kw_ui.items():
            raw = widget.get("1.0", "end").strip()
            self.config[k] = [x.strip() for x in raw.split(",") if x.strip()]
        save_config(self.config); self.master_app.reload_settings(); self.destroy()

class PomodoroApp(ctk.CTk):
    def __init__(self, config):
        super().__init__()
        self.config = config
        
        self.is_minimizing = False
        if sys.platform.startswith("linux"):
            self.attributes('-type', 'splash')
        else:
            self.overrideredirect(True)
        
        # Load window position memory
        x = self.config.get("window_x", 100)
        y = self.config.get("window_y", 100)
        self.geometry(f"400x80+{x}+{y}")
        
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.92)  # Semi-transparent glassmorphism look
        
        ctk.set_appearance_mode(self.config.get("theme", "dark"))
        
        self._ox = 0; self._oy = 0
        self.pomo_state = "IDLE"
        self.editing_task = False
        self.editing_time = False
        self.last_user_task = "Ready"
        self.rem = 0; self.tot = 0; self.job = None
        self.stop_ev = threading.Event()

        self.grid_columnconfigure(0, weight=1)
        
        # TOP BAR
        top = ctk.CTkFrame(self, fg_color="transparent", height=30); top.grid(row=0, sticky="ew", padx=10, pady=(5,0))
        top.columnconfigure(0, weight=1)
        self.lbl_task = ctk.CTkLabel(top, text="Ready", font=("Arial", 14)); self.lbl_task.grid(row=0, column=0, sticky="w")
        
        btns = ctk.CTkFrame(top, fg_color="transparent"); btns.grid(row=0, column=1, sticky="e")
        ctk.CTkButton(btns, text="⚙", width=25, height=25, command=lambda: SettingsWindow(self, self.config)).pack(side="left")
        ctk.CTkButton(btns, text="−", width=25, height=25, command=self.mini).pack(side="left", padx=2)
        ctk.CTkButton(btns, text="✕", width=25, height=25, fg_color="red", command=self.close).pack(side="left", padx=2)

        # MAIN ROW
        mid = ctk.CTkFrame(self, fg_color="transparent"); mid.grid(row=1, sticky="ew", padx=10, pady=5)
        mid.columnconfigure(0, weight=1)

        self.prog = ctk.CTkProgressBar(mid, height=10); self.prog.grid(row=0, column=0, sticky="ew", padx=(0,10))
        self.prog.set(1)
        
        ctrl = ctk.CTkFrame(mid, fg_color="transparent"); ctrl.grid(row=0, column=1, sticky="e")
        self.lbl_time = ctk.CTkLabel(ctrl, text="25:00", font=("Arial", 30, "bold"), width=90); self.lbl_time.pack(side="left")
        
        self.btn_play = ctk.CTkButton(ctrl, text="▶", width=30, font=("Arial", 18), command=self.click_play); self.btn_play.pack(side="left", padx=2)
        self.btn_pause = ctk.CTkButton(ctrl, text="⏸", width=30, font=("Arial", 18), command=self.click_pause_resume, state="disabled", fg_color="gray"); self.btn_pause.pack(side="left", padx=2)

        self.ent_task = ctk.CTkEntry(top, height=24, font=("Arial", 12)); self.ent_time = ctk.CTkEntry(self)

        # BINDINGS
        for w in [self, top, mid, self.prog]:
            w.bind("<ButtonPress-1>", self.start_mv)
            w.bind("<B1-Motion>", self.do_mv)
            w.bind("<ButtonRelease-1>", self.save_position)
        
        self.lbl_task.bind("<Button-1>", self.edit_task)
        self.ent_task.bind("<Return>", self.save_task); self.ent_task.bind("<FocusOut>", self.save_task)
        self.ent_task.bind("<Escape>", self.cancel_edit_task)
        self.ent_task.bind("<Button-1>", lambda e: self.ent_task._entry.focus_force())
        self.ent_task._entry.bind("<Button-1>", lambda e: self.ent_task._entry.focus_force())
        self.lbl_time.bind("<Button-1>", self.edit_time)
        self.ent_time.bind("<Return>", self.save_time); self.ent_time.bind("<FocusOut>", self.save_time)
        self.ent_time.bind("<Escape>", self.cancel_edit_time)
        self.ent_time.bind("<Button-1>", lambda e: self.ent_time._entry.focus_force())
        self.ent_time._entry.bind("<Button-1>", lambda e: self.ent_time._entry.focus_force())
        self.bind_class("Entry", "<Button-1>", lambda event: event.widget.focus_force())
        self.bind("<Map>", self.restore)
        if sys.platform.startswith("linux"):
            self.bind("<Unmap>", self.on_unmap)

        self.reset_ui()
        threading.Thread(target=ntfy_listener, args=(self.stop_ev,), daemon=True).start()
        self.after(500, self.check_q)

    # --- LOGIC START ---

    def click_play(self):
        if self.editing_task: self.save_task(None)
        if self.editing_time: self.save_time(None)
        
        # Button 1: Starts new task OR Stops current
        if self.pomo_state == "IDLE":
            current_name = self.lbl_task.cget("text")
            if current_name == "Ready" or not current_name:
                current_name = "Manual Task"
            self.start_timer(current_name, self.config["pomodoro_minutes"], ticking=True)
        else:
            self.stop_timer()

    def click_pause_resume(self):
        if self.editing_task: self.save_task(None)
        if self.editing_time: self.save_time(None)
        
        # Button 2: Pauses or Resumes
        if self.pomo_state == "RUNNING": self.pause_timer()
        elif self.pomo_state == "PAUSED": self.resume_timer()

    def start_timer(self, task, mins, ticking=True):
        self.pomo_state = "RUNNING"
        self.lbl_task.configure(text=task)
        if "Break" not in task:
            self.last_user_task = task
        self.rem = int(float(mins) * 60); self.tot = self.rem
        
        self.update_buttons()
        self.tick()
        
        if ticking:
            audio.play(self.config["ticking_sound_path"], True)
        else:
            # Important: If we start a break silently, don't play sound, but don't stop existing finish sound
            pass

    def pause_timer(self):
        self.pomo_state = "PAUSED"
        self.update_buttons()
        audio.stop()
        if self.job: self.after_cancel(self.job)

    def resume_timer(self):
        self.pomo_state = "RUNNING"
        self.update_buttons()
        self.tick()
        # Only play ticking sound if it is NOT a break
        if "Break" not in self.lbl_task.cget("text"):
            audio.play(self.config["ticking_sound_path"], True)

    def stop_timer(self, kill_audio=True):
        self.pomo_state = "IDLE"
        self.reset_ui()
        if self.job: self.after_cancel(self.job)
        if kill_audio: audio.stop()

    def tick(self):
        if self.pomo_state != "RUNNING": return
        if self.rem > 0:
            self.rem -= 1
            m, s = divmod(self.rem, 60)
            self.lbl_time.configure(text=f"{m:02d}:{s:02d}")
            if self.tot > 0: self.prog.set(self.rem / self.tot)
            self.job = self.after(1000, self.tick)
        else:
            self.finish()

    def finish(self):
        audio.stop()
        self.rem = 0; self.prog.set(0)
        
        if "Break" in self.lbl_task.cget("text"):
            # Break Ended
            audio.play(self.config["break_finish_sound_path"], False)
            self.stop_timer(kill_audio=False) # Don't kill the break finish sound
        else:
            # Pomo Ended
            audio.play(self.config["finish_sound_path"], False)
            # Start break silently (no ticking)
            self.start_timer("Break Time!", self.config["break_minutes"], ticking=False)

    def reset_ui(self):
        if self.pomo_state == "IDLE":
            current = self.lbl_task.cget("text")
            if current == "Break Time!" or not current:
                self.lbl_task.configure(text=self.last_user_task)
        total_seconds = int(self.config["pomodoro_minutes"] * 60)
        m, s = divmod(total_seconds, 60)
        self.lbl_time.configure(text=f"{m:02d}:{s:02d}")
        self.prog.set(1)
        self.update_buttons()

    def update_buttons(self):
        if self.pomo_state == "IDLE":
            self.btn_play.configure(text="▶", fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"])
            self.btn_pause.configure(state="disabled", fg_color="gray", text="⏸")
        elif self.pomo_state == "RUNNING":
            self.btn_play.configure(text="■", fg_color="#C0392B")
            self.btn_pause.configure(state="normal", fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"], text="⏸")
        elif self.pomo_state == "PAUSED":
            self.btn_play.configure(text="■", fg_color="#C0392B")
            self.btn_pause.configure(state="normal", fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"], text="▶")
    
    def reload_settings(self):
        self.config = app_config
        if self.pomo_state == "IDLE": self.reset_ui()

    def check_q(self):
        try:
            msg = command_queue.get_nowait(); c = msg["cmd"]
            if c == "start": self.start_timer(msg["task"], self.config["pomodoro_minutes"])
            elif c == "stop": self.stop_timer()
            elif c == "pause" and self.pomo_state == "RUNNING": self.pause_timer()
            elif c == "resume" and self.pomo_state == "PAUSED": self.resume_timer()
        except: pass
        self.after(500, self.check_q)

    # Edit / Window
    def edit_task(self, e):
        if "Break" in self.lbl_task.cget("text"): return
        if self.editing_task: return
        self.editing_task = True
        self.lbl_task.grid_remove()
        self.ent_task.grid(row=0, column=0, sticky="ew")
        self.ent_task.delete(0, "end")
        self.ent_task.insert(0, self.lbl_task.cget("text"))
        self.ent_task.select_range(0, "end")
        self.ent_task.icursor("end")
        self.after(50, self.ent_task._entry.focus_force)

    def save_task(self, e):
        if not self.editing_task: return
        self.editing_task = False
        val = self.ent_task.get().strip()
        if val:
            self.lbl_task.configure(text=val)
            self.last_user_task = val
        else:
            if self.pomo_state == "IDLE":
                self.lbl_task.configure(text="Ready")
                self.last_user_task = "Ready"
        self.ent_task.delete(0, "end")
        self.ent_task.grid_remove()
        self.lbl_task.grid()

    def cancel_edit_task(self, e):
        if not self.editing_task: return
        self.editing_task = False
        self.ent_task.delete(0, "end")
        self.ent_task.grid_remove()
        self.lbl_task.grid()

    def edit_time(self, e):
        if self.pomo_state not in ["IDLE", "PAUSED"]: return
        if self.editing_time: return
        self.editing_time = True
        self.ent_time.place(in_=self.lbl_time, relx=0, rely=0, relwidth=1, relheight=1)
        self.ent_time.delete(0, "end")
        self.ent_time.insert(0, self.lbl_time.cget("text"))
        self.ent_time.select_range(0, "end")
        self.ent_time.icursor("end")
        self.after(50, self.ent_time._entry.focus_force)

    def save_time(self, e):
        if not self.editing_time: return
        self.editing_time = False
        try:
            val = self.ent_time.get().strip()
            if val:
                if ":" in val: m, s = map(int, val.split(":"))
                else: m, s = int(val), 0
                self.rem = m*60 + s; self.tot = self.rem; self.lbl_time.configure(text=f"{m:02d}:{s:02d}")
                self.config["pomodoro_minutes"] = m + s / 60.0
                save_config(self.config)
                self.config = app_config
        except: pass
        self.ent_time.delete(0, "end")
        self.ent_time.place_forget()

    def cancel_edit_time(self, e):
        if not self.editing_time: return
        self.editing_time = False
        self.ent_time.delete(0, "end")
        self.ent_time.place_forget()
    def save_position(self, e):
        self.config["window_x"] = self.winfo_x()
        self.config["window_y"] = self.winfo_y()
        save_config(self.config)
        self.config = app_config

    def start_mv(self, e): self.focus_force(); self._ox = e.x; self._oy = e.y
    def do_mv(self, e): self.geometry(f"+{self.winfo_x()+e.x-self._ox}+{self.winfo_y()+e.y-self._oy}")
    
    def mini(self):
        if sys.platform.startswith("linux"):
            self.is_minimizing = True
            self.attributes('-type', 'normal')
            self.after(100, self.iconify)
        else:
            self.overrideredirect(False)
            self.iconify()
            
    def on_unmap(self, e):
        if e.widget == self:
            self.is_minimizing = False
            
    def restore(self, e): 
        if e.widget == self and self.state() == "normal":
            if sys.platform.startswith("linux"):
                if self.is_minimizing:
                    return
                self.after(100, lambda: self.attributes('-type', 'splash'))
            else:
                self.after(10, lambda: self.overrideredirect(True))
                
    def change_theme(self, m): ctk.set_appearance_mode(m)
    def close(self): self.stop_ev.set(); audio.stop(); self.destroy(); sys.exit()

if __name__ == "__main__":
    config = load_config()
    app = PomodoroApp(config)
    app.mainloop()