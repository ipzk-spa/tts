"""Допоміжний скрипт для tools/setup_styletts2.ps1 — завантажує усі файли
стилів голосу (voices/*.pt) з HuggingFace Space patriotyk/styletts2-ukrainian
у models/styletts2/voices. Окремий файл замість inline python -c, щоб
уникнути проблем із кодуванням/квотуванням у PowerShell."""
import os
import shutil

from huggingface_hub import snapshot_download

path = snapshot_download(
    repo_id="patriotyk/styletts2-ukrainian",
    repo_type="space",
    allow_patterns=["voices/*.pt"],
)
src_dir = os.path.join(path, "voices")
dst_dir = os.path.join("models", "styletts2", "voices")
os.makedirs(dst_dir, exist_ok=True)

count = 0
for name in os.listdir(src_dir):
    shutil.copy2(os.path.join(src_dir, name), os.path.join(dst_dir, name))
    count += 1

print(f"Skopiovano {count} failiv stiliv u {dst_dir}")
