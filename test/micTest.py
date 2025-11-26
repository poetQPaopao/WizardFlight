import pyaudio
import numpy as np
import threading
import time

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 48000

p = pyaudio.PyAudio()

# -------------------------------
# 列出所有输入设备
# -------------------------------
print("Available input devices:\n")
input_devices = []
for i in range(p.get_device_count()):
    try:
        info = p.get_device_info_by_index(i)
        if info["maxInputChannels"] > 0:
            print(f"Index {i} — {info['name']}  (Channels: {info['maxInputChannels']})")
            input_devices.append(i)
    except Exception:
        continue

# -------------------------------
# 选择模式
# -------------------------------
print("\nSelect Mode:")
print("1. Two separate devices (Dual Mono)")
print("2. Single device (Stereo Split - Left/Right)")
mode = input("Choice (1/2): ").strip()

running = True
threads = []

if mode == "2":
    # -------------------------------
    # 单设备立体声分轨模式
    # -------------------------------
    try:
        dev = int(input("\nEnter Stereo Device index: "))
    except ValueError:
        print("Invalid input.")
        exit(1)

    print(f"\n[INFO] Stereo Device: {p.get_device_info_by_index(dev)['name']}\n")

    def monitor_stereo(device_index):
        print(f"[START] Monitoring Stereo Device: {device_index}")
        try:
            stream = p.open(
                format=FORMAT,
                channels=2,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK,
                input_device_index=device_index
            )
        except Exception as e:
            print(f"[ERROR] Could not open stream: {e}")
            return

        while running:
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
                audio_np = np.frombuffer(data, dtype=np.int16)
                
                # Reshape to (samples, channels)
                stereo_data = audio_np.reshape(-1, 2)
                left_data = stereo_data[:, 0]
                right_data = stereo_data[:, 1]
                
                rms_l = np.sqrt(np.mean(left_data.astype(np.float64)**2)) if left_data.size else 0.0
                rms_r = np.sqrt(np.mean(right_data.astype(np.float64)**2)) if right_data.size else 0.0

                if not np.isfinite(rms_l):
                    rms_l = 0.0
                if not np.isfinite(rms_r):
                    rms_r = 0.0

                vol_l = int(rms_l / 100)
                vol_r = int(rms_r / 100)
                # Print side by side
                print(f"[L] {rms_l:6.2f} {'|'*vol_l:<20}  [R] {rms_r:6.2f} {'|'*vol_r}")
                
            except Exception as e:
                print(f"Error: {e}")
                break
        
        stream.stop_stream()
        stream.close()

    t = threading.Thread(target=monitor_stereo, args=(dev,))
    t.start()
    threads.append(t)

else:
    # -------------------------------
    # 双设备模式 (原逻辑)
    # -------------------------------
    try:
        devA = int(input("\nEnter Mic A index: "))
        devB = int(input("Enter Mic B index: "))
    except ValueError:
        print("Invalid input.")
        exit(1)

    print(f"\n[INFO] Mic A: {p.get_device_info_by_index(devA)['name']}")
    print(f"[INFO] Mic B: {p.get_device_info_by_index(devB)['name']}\n")

    def monitor_device(device_index, label):
        print(f"[START] Monitoring {label}: {device_index}")
        try:
            stream = p.open(
                format=FORMAT,
                channels=1,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK,
                input_device_index=device_index
            )
        except Exception as e:
            print(f"[ERROR] {label}: {e}")
            return

        while running:
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
                audio_np = np.frombuffer(data, dtype=np.int16)
                rms = np.sqrt(np.mean(audio_np**2))
                vol = int(rms / 100)
                print(f"[{label}] RMS={rms:6.2f} {'|'*vol}")
            except Exception as e:
                break
        stream.stop_stream()
        stream.close()

    tA = threading.Thread(target=monitor_device, args=(devA, "Mic A"))
    tB = threading.Thread(target=monitor_device, args=(devB, "Mic B"))
    tA.start()
    tB.start()
    threads.extend([tA, tB])

print("\n[INFO] 正在实时监听... 按 Ctrl+C 停止\n")

try:
    while True:
        time.sleep(0.1)
except KeyboardInterrupt:
    print("\n[INFO] Stopping...")
    running = False
    for t in threads:
        t.join()
    p.terminate()
    print("[DONE] Stopped.")