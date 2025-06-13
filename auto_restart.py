import os
import subprocess
import time

def restart_app():
    try:
        # Stop the running app
        print("Stopping app.py process...")
        subprocess.run(["pkill", "-f", "python3 app.py"], check=True)
    except subprocess.CalledProcessError:
        print("No process found to kill. Starting fresh.")

    # Start the app and show logs in real-time
    print("Starting app.py...")
    app_process = subprocess.Popen(
        ["python3", "app.py"],
        stdout=None,  # Send output directly to the terminal
        stderr=None  # Send error logs directly to the terminal
    )

    # Give the app time to initialize before sending the POST request
    time.sleep(5)

    # Send the curl POST request
    print("Sending start request...")
    subprocess.run(["curl", "-X", "POST", "http://localhost:5000/start"], check=True)

    print(f"App restarted successfully at {time.ctime()}\n")

if __name__ == "__main__":
    while True:
        restart_app()
        # Wait for 30 mins before restarting
        time.sleep(1800)
