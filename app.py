import logging
from bot_main import run_bot
from flask import Flask, render_template, request
import threading
import atexit

# Setting up logging
logging.basicConfig(filename='app.log', filemode='a', format='%(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('my_application')

# Setting up Flask application
app = Flask(__name__)

# This will hold our thread object
thread = None

def stop_thread():
    if thread is not None:
        thread.stop()

atexit.register(stop_thread)

class MyThread(threading.Thread):
    def __init__(self):
        self._stop_event = threading.Event()
        super().__init__()

    def stop(self):
        self._stop_event.set()

    def run(self):
        while not self._stop_event.is_set():
            try:
                # Call your main function here
                run_bot()
            except Exception as e:
                logger.error("Error in main function", exc_info=True)

@app.route('/start', methods=['POST'])
def start_script():
    global thread
    if thread is not None and thread.is_alive():
        return "Script already running"
    thread = MyThread()
    thread.start()
    return "Script started"

@app.route('/stop', methods=['POST'])
def stop_script():
    global thread
    if thread is not None and thread.is_alive():
        thread.stop()
        thread = None
        return "Script stopped"
    return "Script not running"

@app.route('/logs', methods=['POST'])
def view_logs():
    with open('app.log', 'r') as log_file:
        content = log_file.read()
    return content

# add more routes for other features...

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
