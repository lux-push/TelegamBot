import asyncio
import subprocess
import sys
from pathlib import Path

async def run_bot(script_name: str):
    """Запускает бота в отдельном процессе"""
    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable, script_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        print(f"{script_name} завершился: {process.returncode}")
    except Exception as e:
        print(f"Ошибка запуска {script_name}: {e}")

async def main():
    print("🚀 Запуск всех ботов...")
    
    # Запуск всех ботов параллельно
    tasks = [
        run_bot("bot_a.py"),
        run_bot("bot_b.py")
    ]
    
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())