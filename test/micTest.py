import pyaudio
import wave
import numpy as np
import threading

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 48000
RECORD_SECONDS = 10

p = pyaudio.PyAudio()

# -------------------------------
# 列出所有输入设备
# -------------------------------
print("Available input devices:\n")
input_devices = []
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if info["maxInputChannels"] > 0:
        print(f"Index {i} — {info['name']}  (Channels: {info['maxInputChannels']})")
        input_devices.append(i)

# -------------------------------
# 选择两个设备
# -------------------------------
devA = int(input("\n请输入 Mic A 的设备 index: "))
devB = int(input("请输入 Mic B 的设备 index: "))

print(f"\n[INFO] Mic A 设备: {p.get_device_info_by_index(devA)['name']}")
print(f"[INFO] Mic B 设备: {p.get_device_info_by_index(devB)['name']}\n")

# -------------------------------
# 录音线程
# -------------------------------
def record_from_device(device_index, output_file):
    print(f"[START] Recording from device: {device_index}")

    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK,
        input_device_index=device_index
    )

    frames = []

    for _ in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)

        audio_np = np.frombuffer(data, dtype=np.int16)
        rms = np.sqrt(np.mean(audio_np**2))
        print(f"[Device {device_index}] RMS={rms:.2f}")

    stream.stop_stream()
    stream.close()

    # 保存 WAV 文件
    wf = wave.open(output_file, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()

    print(f"[SAVED] {output_file}")


# -------------------------------
# 同时启动两个录音线程
# -------------------------------
threadA = threading.Thread(target=record_from_device, args=(devA, "mic_A.wav"))
threadB = threading.Thread(target=record_from_device, args=(devB, "mic_B.wav"))

threadA.start()
threadB.start()

threadA.join()
threadB.join()

print("\n[DONE] 双麦克风录音完成！请检查 mic_A.wav 和 mic_B.wav 文件。\n")