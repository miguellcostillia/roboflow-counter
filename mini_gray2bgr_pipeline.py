#!/usr/bin/env python3
import argparse, cv2, time

# --- safe merge replacement ---
def gray_to_bgr_safe(d_gray):
    if d_gray.empty():
        raise RuntimeError("gray_to_bgr_safe: empty input")
    try:
        merged = cv2.cuda.merge([d_gray, d_gray, d_gray])
        # Ensure output is still GPU
        if isinstance(merged, cv2.cuda_GpuMat):
            return merged
        raise RuntimeError(f"merge returned wrong type: {type(merged)}")
    except Exception as e:
        raise RuntimeError(f"gray_to_bgr_safe failed: {e}")

p = argparse.ArgumentParser()
p.add_argument("--src", required=True, help="RTSP/RTSPS stream URL")
args = p.parse_args()

cap = cv2.VideoCapture(args.src, cv2.CAP_FFMPEG)
if not cap.isOpened():
    raise RuntimeError(f"Input open failed: {args.src}")

# Grab 1 frame
frame0 = None
for _ in range(30):
    ok, f = cap.read()
    if ok and f is not None and f.size>0:
        frame0 = f
        break
if frame0 is None:
    raise RuntimeError("No valid frame")

print("[INFO] frame ok", frame0.shape)

# Upload
d_bgr = cv2.cuda_GpuMat()
d_bgr.upload(frame0)

# Manual BGR→GRAY (fallback path)
b, g, r = cv2.cuda.split(d_bgr)
tmp  = cv2.cuda.addWeighted(b,0.114,g,0.587,0.0)
d_gray = cv2.cuda.addWeighted(tmp,1.0,r,0.299,0.0)

print("[INFO] gray:", type(d_gray), d_gray.size(), d_gray.type())

# Convert gray→BGR (GPU)
d_bgr3 = gray_to_bgr_safe(d_gray)
print("[INFO] merge ok:", type(d_bgr3), d_bgr3.size(), d_bgr3.type())

# sanity download
cpu = d_bgr3.download()
print("[OK] downloaded shape:", cpu.shape)
