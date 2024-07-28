import time, tkinter as tk
from pynput import keyboard
from threading import Thread
from queue import Queue
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume, ISimpleAudioVolume
# 初始化变量
initial_volume = 0  # 初始音量
shift_pressed = False  # 是否按下Shift键
monitoring = False  # 是否监控中
volume_changed = False  # 音量是否改变
initial_app_volumes = {}  # 应用初始音量
volume_increment_step = 5  # 默认音量增量步长（%）
# 初始化音量控制
devices = AudioUtilities.GetSpeakers()  # 获取扬声器设备
volume = cast(devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None), POINTER(IAudioEndpointVolume))
get_current_volume = lambda: int(volume.GetMasterVolumeLevelScalar() * 100)  # 获取当前音量（%）
set_volume = lambda vol: volume.SetMasterVolumeLevelScalar(vol / 100, None)  # 设置音量（%）
get_all_sessions = AudioUtilities.GetAllSessions  # 获取所有音频会话
# 获取所有应用的音量
def get_app_volumes(): return {s.Process.name(): s._ctl.QueryInterface(ISimpleAudioVolume).GetMasterVolume() * 100 for s in get_all_sessions() if s.Process and s.Process.name()}
# 设置所有应用的音量
def set_app_volumes(volumes): [s._ctl.QueryInterface(ISimpleAudioVolume).SetMasterVolume(volumes[s.Process.name()] / 100, None) for s in get_all_sessions() if s.Process and s.Process.name() in volumes]
initial_volume, initial_app_volumes = get_current_volume(), get_app_volumes()  # 初始化音量和应用音量
keyboard_controller = keyboard.Controller()  # 初始化键盘控制器
queue = Queue()  # 用于线程间通信的队列

# 定义时间变化窗口类
class TimeChangeWindow:
    def __init__(self, root): self.root, self.win = root, None  # 初始化根窗口和窗口变量
    def show(self):
        if self.win: return  # 若窗口已显示则返回
        self.win = tk.Toplevel(self.root); self.win.overrideredirect(True); self.win.attributes("-topmost", True)
        self.win.geometry(f"200x50+{self.win.winfo_screenwidth()//2-100}+{self.win.winfo_screenheight()-150}")
        self.label = tk.Label(self.win, text="", font=("Arial", 16), bg="black", fg="white"); self.label.pack(expand=True, fill=tk.BOTH)
        self.win.update_idletasks(); self.win.lift()  # 将窗口置顶
    def update(self, change): 
        if self.win: self.label.config(text=f"{'+' if change > 0 else ''}{change} 秒")  # 更新显示的时间变化

    def hide(self):
        if self.win: self.win.destroy(); self.win = None  # 隐藏并销毁窗口
time_change_window = TimeChangeWindow(tk.Tk()); time_change_window.root.withdraw()  # 初始化时间变化窗口并隐藏主窗口
# 处理队列中的命令
def process_queue():
    while not queue.empty():
        command, *args = queue.get()
        if command == "show": time_change_window.show()
        elif command == "update": time_change_window.update(*args)
        elif command == "hide": time_change_window.hide()
    time_change_window.root.after(100, process_queue)  # 每100毫秒处理一次队列
# 音量变化处理函数
def on_volume_change():
    global volume_changed
    if not volume_changed: return
    change = (get_current_volume() - initial_volume) * volume_increment_step
    queue.put(("update", change))  # 更新显示的时间变化
    for _ in range(abs(change)):
        key = keyboard.Key.right if change > 0 else keyboard.Key.left
        keyboard_controller.press(key); keyboard_controller.release(key)  # 模拟按键
    set_volume(initial_volume); set_app_volumes(initial_app_volumes); volume_changed = False
# 监控音量变化
def monitor_volume():
    global volume_changed
    prev_volume = get_current_volume()
    while shift_pressed:
        current_volume = get_current_volume()
        if current_volume != prev_volume:
            volume_changed = True
            change = (current_volume - initial_volume) * volume_increment_step
            queue.put(("update", change)); set_app_volumes(initial_app_volumes)  # 更新应用音量
        prev_volume = current_volume; time.sleep(0.1)  # 每0.1秒检测一次音量变化
# 按键按下事件处理
def on_press(key):
    global shift_pressed, initial_volume, volume_changed, initial_app_volumes
    if key == keyboard.Key.shift and not shift_pressed:
        shift_pressed, initial_volume, initial_app_volumes = True, get_current_volume(), get_app_volumes()
        queue.put(("show",)); Thread(target=monitor_volume, daemon=True).start()
# 按键释放事件处理
def on_release(key):
    global shift_pressed
    if key == keyboard.Key.shift:
        shift_pressed = False; on_volume_change(); queue.put(("hide",))
# 开始监控按键事件
def start_monitoring():
    listener = keyboard.Listener(on_press=on_press, on_release=on_release); listener.start(); listener.join()
# 切换监控状态
def toggle_monitoring():
    global monitoring
    if monitoring:
        monitoring = False; toggle_button.config(text="Start Monitoring")
    else:
        monitoring = True; Thread(target=start_monitoring, daemon=True).start(); toggle_button.config(text="Stop Monitoring")
# 初始化GUI
root = tk.Tk(); root.title("Volume Monitor")
tk.Label(root, text="Volume Increment Step (%):").pack(pady=5)
increment_step_entry = tk.Entry(root); increment_step_entry.pack(pady=5); increment_step_entry.insert(0, str(volume_increment_step))
# 更新音量步长
def update_increment_step():
    global volume_increment_step
    volume_increment_step = int(increment_step_entry.get())
# 更新按钮和监控切换按钮
update_button = tk.Button(root, text="Update Increment Step", command=update_increment_step)
update_button.pack(pady=10)
toggle_button = tk.Button(root, text="Start Monitoring", command=toggle_monitoring)
toggle_button.pack(pady=10)
tk.Button(root, text="Exit", command=root.quit).pack(pady=10)
root.after(100, process_queue)  # 定期处理队列中的命令
root.mainloop()
